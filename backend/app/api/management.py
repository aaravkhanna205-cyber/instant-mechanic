"""Phase 3 self-registration, administrator controls, and reviewed job imports.

Import is jobs-only: preview is read-only; commit creates DRAFT jobs; undo is
restricted to jobs from the import that have no applications.
"""
import csv
import hashlib
import hmac
import io
import json
import re
import uuid
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.schema import User, Organization, OrganizationMembership, AuditLog, Job, JobCategory, Application
from app.security.passwords import hash_password
from app.security.dependencies import get_db, get_current_user, get_redis, get_session_record, require_platform_admin, require_recruiter_for_org
from app.security.sessions import SessionRecord
from redis import Redis

router = APIRouter(prefix='/api/admin-v3', tags=['Admin Phase 3'])
reg = APIRouter(prefix='/api/auth', tags=['Authentication'])


class RegisterInput(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)


class MembershipInput(BaseModel):
    email: EmailStr
    organization_id: UUID
    role: str


class SettingInput(BaseModel):
    value: dict | list | str | bool | int | float | None


def csrf(request: Request, record: SessionRecord = Depends(get_session_record)):
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.allowed_origins:
        raise HTTPException(403, 'Origin not allowed')
    if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), record.csrf):
        raise HTTPException(403, 'Invalid CSRF token')


def log(db, actor, action, org=None, target=None, extra=None):
    db.add(AuditLog(actor_id=actor, organization_id=org, action=action, target_type='phase3', target_id=str(target) if target else None, context=extra or {}))


@reg.post('/register', status_code=201)
def register(payload: RegisterInput, request: Request, db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.allowed_origins:
        raise HTTPException(403, 'Origin not allowed')
    email = str(payload.email).lower().strip()
    # Simple IP-limited public registration, never grants recruiter/admin status.
    source = (request.client.host if request.client else 'unknown')
    key = 'imhire:register:' + hashlib.sha256(source.encode()).hexdigest()
    count = cache.incr(key)
    if count == 1:
        cache.expire(key, 3600)
    if count > 10:
        raise HTTPException(429, 'Registration temporarily limited')
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, 'Account already registered')
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=password_hash, active=True, is_platform_admin=False)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Account already registered')
    return {'message':'Account created; sign in to continue'}


@router.get('/users')
def users(_: User = Depends(require_platform_admin), db: Session = Depends(get_db), limit: int = 100):
    items = db.scalars(select(User).order_by(User.created_at.desc()).limit(min(max(1,limit),200))).all()
    return [{'id':str(u.id),'email':u.email,'full_name':u.full_name,'active':u.active,'is_platform_admin':u.is_platform_admin} for u in items]


@router.post('/memberships', status_code=201)
def grant_membership(body: MembershipInput, _: None = Depends(csrf), admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    if body.role not in ('owner','admin','recruiter','interviewer','candidate'):
        raise HTTPException(422,'Invalid organization role')
    target = db.scalar(select(User).where(User.email == str(body.email).lower()))
    org = db.get(Organization, body.organization_id)
    if not target or not org or not org.active:
        raise HTTPException(404,'Account or organization not found')
    member = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id==target.id,OrganizationMembership.organization_id==org.id))
    if member:
        member.role = body.role
    else:
        db.add(OrganizationMembership(user_id=target.id, organization_id=org.id, role=body.role))
    log(db,admin.id,'membership.update',org.id,target.id,{'role':body.role})
    db.commit()
    return {'ok':True}


@router.get('/settings')
def settings_list(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.execute(text('SELECT key, value FROM app_settings ORDER BY key')).all()
    return [{'key':r[0],'value':r[1]} for r in rows]


@router.put('/settings/{key}')
def settings_update(key: str, payload: SettingInput, _: None = Depends(csrf), admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,79}',key):
        raise HTTPException(422,'Invalid setting key')
    # Never store secret tokens or credentials in this general-purpose settings API.
    if re.search(r'(password|secret|token|api_key|credential)',key,re.I):
        raise HTTPException(422,'Secret settings must use the secret manager')
    db.execute(text('INSERT INTO app_settings(key,value) VALUES (:k, CAST(:v AS JSON)) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()'),{'k':key,'v':json.dumps(payload.value)})
    log(db,admin.id,'settings.update',extra={'key':key})
    db.commit()
    return {'key':key,'value':payload.value}


async def parse_file(upload: UploadFile):
    data = await upload.read(2_000_001)
    if len(data) > 2_000_000:
        raise HTTPException(413,'Maximum import size is 2 MB')
    name = upload.filename or ''
    if name.lower().endswith('.csv'):
        try:
            content=data.decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(content)))
        except (UnicodeError,csv.Error) as exc:
            raise HTTPException(422,'Invalid UTF-8 CSV') from exc
    elif name.lower().endswith('.xlsx'):
        from openpyxl import load_workbook
        try:
            sheet=load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
            values=sheet.iter_rows(values_only=True)
            headers=[str(x or '').strip() for x in next(values)]
            rows=[dict(zip(headers,values_row)) for values_row in values]
        except Exception as exc:
            raise HTTPException(422,'Invalid XLSX file') from exc
    else:
        raise HTTPException(422,'Only .csv and .xlsx supported')
    if len(rows)>1000:
        raise HTTPException(413,'Maximum 1000 rows')
    return name,rows


def validate_rows(rows, categories):
    valid=[];errors=[]
    for i,row in enumerate(rows,start=2):
        title=str(row.get('title') or '').strip()
        category=str(row.get('category_slug') or '').strip()
        description=str(row.get('description') or '').strip()
        location=str(row.get('location') or '').strip()
        problem=[]
        if not 3<=len(title)<=200: problem.append('title must be 3-200 chars')
        if category not in categories: problem.append('unknown category_slug')
        if len(description)>12000: problem.append('description too long')
        if len(location)>150: problem.append('location too long')
        if problem: errors.append({'row':i,'errors':problem})
        else: valid.append({'row':i,'title':title,'category_slug':category,'description':description,'location':location})
    return valid,errors


async def upload_validated(upload, org_id, db):
    name,rows=await parse_file(upload)
    categories=set(db.scalars(select(JobCategory.slug)).all())
    good,bad=validate_rows(rows,categories)
    return name,good,bad


@router.post('/organizations/{organization_id}/imports/preview')
async def preview(organization_id:UUID, file: UploadFile = File(...), _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    name,valid,errors=await upload_validated(file,organization_id,db)
    return {'filename':name,'valid_count':len(valid),'errors':errors,'sample':valid[:10]}


@router.post('/organizations/{organization_id}/imports/commit',status_code=201)
async def commit_import(organization_id:UUID, request:Request, file:UploadFile=File(...), _:None=Depends(csrf), actor:User=Depends(require_recruiter_for_org), db:Session=Depends(get_db)):
    org=db.get(Organization,organization_id)
    if not org or not org.active: raise HTTPException(404,'Organization not found')
    name,good,bad=await upload_validated(file,organization_id,db)
    if bad or not good: raise HTTPException(422,{'message':'Correct every row before importing','errors':bad})
    batch_id=uuid.uuid4()
    db.execute(text('INSERT INTO import_batches(id,organization_id,created_by_id,filename,kind,status) VALUES (:id,:org,:actor,:name,\'jobs\',\'applied\')'),{'id':batch_id,'org':organization_id,'actor':actor.id,'name':name})
    for item in good:
        job=Job(organization_id=organization_id,created_by_id=actor.id,title=item['title'],category_slug=item['category_slug'],description=item['description'],location=item['location'],status='draft')
        db.add(job); db.flush()
        db.execute(text('INSERT INTO import_rows(id,batch_id,row_number,job_id,data) VALUES (:id,:bid,:row,:jid,CAST(:data AS JSON))'),{'id':uuid.uuid4(),'bid':batch_id,'row':item['row'],'jid':job.id,'data':json.dumps(item)})
    log(db,actor.id,'import.create',organization_id,batch_id,{'rows':len(good)})
    db.commit()
    return {'batch_id':str(batch_id),'created':len(good),'status':'applied','jobs_status':'draft'}


@router.get('/organizations/{organization_id}/imports')
def imports(organization_id:UUID, _:User=Depends(require_recruiter_for_org), db:Session=Depends(get_db)):
    records=db.execute(text('SELECT id,filename,status,created_at FROM import_batches WHERE organization_id=:org ORDER BY created_at DESC LIMIT 100'),{'org':organization_id}).all()
    return [{'id':str(r[0]),'filename':r[1],'status':r[2],'created_at':r[3].isoformat()} for r in records]


@router.post('/organizations/{organization_id}/imports/{batch_id}/undo')
def undo(organization_id:UUID,batch_id:UUID,_:None=Depends(csrf),actor:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    row=db.execute(text('SELECT status FROM import_batches WHERE id=:id AND organization_id=:org FOR UPDATE'),{'id':batch_id,'org':organization_id}).first()
    if row is None: raise HTTPException(404,'Batch not found')
    if row[0]!='applied': raise HTTPException(409,'Batch already undone')
    job_ids=[r[0] for r in db.execute(text('SELECT job_id FROM import_rows WHERE batch_id=:id AND job_id IS NOT NULL'),{'id':batch_id}).all()]
    for jid in job_ids:
        job=db.get(Job,jid)
        if not job or job.organization_id!=organization_id or job.status!='draft' or db.scalar(select(Application.id).where(Application.job_id==jid).limit(1)):
            raise HTTPException(409,'Cannot undo: job changed or has applications')
    for jid in job_ids:
        db.delete(db.get(Job,jid))
    db.execute(text("UPDATE import_batches SET status='undone' WHERE id=:id"),{'id':batch_id})
    log(db,actor.id,'import.undo',organization_id,batch_id,{'removed_jobs':len(job_ids)})
    db.commit()
    return {'undone':len(job_ids)}


@router.get('/audit')
def audit(org_id:UUID|None=None, _:User=Depends(require_platform_admin),db:Session=Depends(get_db)):
    query=select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
    if org_id:query=query.where(AuditLog.organization_id==org_id)
    logs=db.scalars(query).all()
    return [{'action':x.action,'actor_id':str(x.actor_id) if x.actor_id else None,'created_at':x.created_at.isoformat() if x.created_at else None,'context':x.context} for x in logs]
