"""Phase 4 advisory recruitment API.

No automated candidate rejection, ranking, sensitive-attribute inference or employment decisions.
"""
import hashlib
import json
import logging
import uuid
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from redis import Redis
from app.models.schema import Application, CandidateProfile, Job, JobRequirement, User
from app.security.dependencies import get_db, get_redis, get_current_user, require_recruiter_for_org
from app.api.recruitment import require_csrf
from app.phase4_ai.documents import validate_file, InvalidResume, interview_prompts, MAX_BYTES
from app.phase4_ai.storage import save_bytes, path_for
from app.phase4_ai.scanner import scan_bytes, scanner_configured, InfectedFile, ScanUnavailable
from app.phase4_ai.worker import QUEUE
from app.phase4_ai.vectors import embed
from app.core.config import settings

log=logging.getLogger(__name__)
router=APIRouter(prefix='/api/phase4',tags=['Phase 4 AI Assistance'])

class ReviewInput(BaseModel):
    note: str=Field(min_length=4,max_length=2000)

def document_out(row):
    return {'id':str(row.id),'filename':row.filename,'status':row.status,'skills':row.skills or [],
            'uploaded_at':row.created_at.isoformat() if row.created_at else None,'error':row.error}

def get_document(db,document_id):
    row=db.execute(text('SELECT id,candidate_id,user_id,filename,file_ext,status,skills,error,created_at FROM phase4_documents WHERE id=:id'),{'id':document_id}).mappings().first()
    if not row: raise HTTPException(404,'Resume document not found')
    return row

def candidate_profile(db,user):
    profile=db.scalar(select(CandidateProfile).where(CandidateProfile.user_id==user.id))
    if profile is None:
        profile=CandidateProfile(user_id=user.id,skills={});db.add(profile);db.flush()
    return profile

@router.post('/resumes',status_code=202)
async def upload_resume(request:Request, file:UploadFile=File(...), consent:bool=Form(...),
                        _:None=Depends(require_csrf),user:User=Depends(get_current_user),
                        db:Session=Depends(get_db),cache:Redis=Depends(get_redis)):
    if settings.app_env.lower() in ('prod','production') and not scanner_configured():
        raise HTTPException(503,'Production uploads require a configured malware scanner')
    if not consent: raise HTTPException(422,'Candidate consent required for resume processing')
    data=await file.read(MAX_BYTES+1)
    try: mime=validate_file(file.filename or '',data)
    except InvalidResume as e: raise HTTPException(422,str(e)) from e
    # Scan before anything is written to disk. Any scanner problem rejects the upload.
    try: scan_bytes(data)
    except InfectedFile as e: raise HTTPException(422,'File rejected by malware scan') from e
    except ScanUnavailable as e:
        log.error('Malware scanner unavailable; upload refused')
        raise HTTPException(503,'Malware scanner unavailable; try again later') from e
    if Path(file.filename).suffix.lower() not in ('.pdf','.docx'):
        raise HTTPException(422,'Invalid format')
    # Prevent platform administrators from uploading on behalf of other people implicitly.
    profile=candidate_profile(db,user)
    document_id=uuid.uuid4();ext=Path(file.filename).suffix.lower()[1:]
    try:
        save_bytes(document_id,ext,data)
        db.execute(text("""INSERT INTO phase4_documents(id,candidate_id,user_id,filename,file_ext,sha256,size_bytes,consented,status,skills)
            VALUES (:id,:candidate,:user,:filename,:ext,:sha,:size,true,'queued',CAST('[]' AS jsonb))"""),
            {'id':document_id,'candidate':profile.id,'user':user.id,'filename':file.filename[:255],
             'ext':ext,'sha':hashlib.sha256(data).hexdigest(),'size':len(data)})
        db.commit()
        cache.lpush(QUEUE,json.dumps({'id':str(document_id),'attempt':0}))
    except Exception:
        db.rollback()
        # If Redis is unavailable, no misleading 'success' response.
        log.exception('Unable to queue resume processing')
        raise HTTPException(503,'Upload could not be queued; try again later')
    return {'id':str(document_id),'status':'queued','note':'Resume will be processed by the local Phase 4 worker'}

@router.get('/resumes/mine')
def my_resumes(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.execute(text('SELECT id,filename,status,skills,error,created_at FROM phase4_documents WHERE user_id=:id ORDER BY created_at DESC LIMIT 30'),{'id':user.id}).mappings().all()
    return [document_out(r) for r in rows]

@router.delete('/resumes/{document_id}')
def delete_mine(document_id:UUID,_:None=Depends(require_csrf),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=get_document(db,document_id)
    if row.user_id!=user.id: raise HTTPException(404,'Resume document not found')
    db.execute(text('DELETE FROM phase4_documents WHERE id=:id'),{'id':document_id})
    db.commit()
    for ext in (row.file_ext,'txt'):
        path_for(document_id,ext).unlink(missing_ok=True)
    return {'deleted':True}

@router.get('/organizations/{organization_id}/applications/{application_id}/evidence')
def evidence(organization_id:UUID,application_id:UUID,
             _:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    app=db.get(Application,application_id)
    if not app:raise HTTPException(404,'Application not found')
    job=db.get(Job,app.job_id)
    if not job or job.organization_id!=organization_id:raise HTTPException(404,'Application not found')
    # Document belongs to the same applicant. Never fetch unrelated resumes.
    doc=db.execute(text("""SELECT id,status,skills FROM phase4_documents WHERE candidate_id=:cid AND consented=true
                      ORDER BY created_at DESC LIMIT 1"""),{'cid':app.candidate_id}).mappings().first()
    requirements=db.scalars(select(JobRequirement).where(JobRequirement.job_id==job.id)).all()
    if doc is None:return {'status':'no_resume','requirements':[r.label for r in requirements],'evidence':[]}
    if doc.status!='ready':return {'status':doc.status,'requirements':[r.label for r in requirements],'evidence':[]}
    # Evidence is not a score. Similarity is used internally to retrieve relevant excerpts only.
    query=(' '.join(r.label for r in requirements) or job.description or job.title)[:4000]
    try:
        vector=embed([query])[0]
    except Exception:
        raise HTTPException(503,'Local embedding model unavailable; install AI dependencies')
    hits=db.execute(text("""SELECT excerpt FROM phase4_chunks WHERE document_id=:id
        ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 5"""),{'id':doc.id,'vector':'['+','.join(map(str,vector))+']'}).all()
    return {'status':'ready','requirements':[r.label for r in requirements],
            'evidence':[h[0][:700] for h in hits], 'skills_to_verify':doc.skills,
            'disclaimer':'Unverified resume claims; recruiter must review. No automated hiring decision or ranking.'}

@router.get('/organizations/{organization_id}/jobs/{job_id}/interview-questions')
def questions(organization_id:UUID,job_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    job=db.get(Job,job_id)
    if not job or job.organization_id!=organization_id:raise HTTPException(404,'Job not found')
    req=db.scalars(select(JobRequirement).where(JobRequirement.job_id==job_id)).all()
    return {'questions':interview_prompts(job.title,[r.label for r in req]),'source':'rule-based structured prompts; review before use'}

@router.post('/organizations/{organization_id}/applications/{application_id}/reviews',status_code=201)
def review(organization_id:UUID,application_id:UUID,body:ReviewInput,
           _:None=Depends(require_csrf),actor:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    app=db.get(Application,application_id)
    if not app:raise HTTPException(404,'Application not found')
    job=db.get(Job,app.job_id)
    if not job or job.organization_id!=organization_id:raise HTTPException(404,'Application not found')
    review_id=uuid.uuid4()
    db.execute(text('INSERT INTO phase4_reviews(id,actor_id,organization_id,application_id,note) VALUES (:id,:actor,:org,:app,:note)'),
                {'id':review_id,'actor':actor.id,'org':organization_id,'app':application_id,'note':body.note})
    db.commit()
    return {'id':str(review_id),'status':'saved','note':'Human review recorded; application stage unchanged'}
