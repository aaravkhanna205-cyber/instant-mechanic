"""Password recovery with one-use, expiring tokens and optional SMTP delivery.

Configure SMTP variables to enable recovery. Without SMTP, requests return 503
rather than claim a message was sent. Never log or return reset tokens.
"""
import hashlib
import json
import os
import secrets
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.schema import User
from app.security.dependencies import get_db, get_redis
from app.security.passwords import hash_password

router=APIRouter(prefix='/api/auth', tags=['Authentication'])


class ResetRequest(BaseModel):
    email:EmailStr


class ResetConfirm(BaseModel):
    token:str=Field(min_length=32,max_length=256)
    password:str=Field(min_length=12,max_length=128)


def send_reset(email:str, token:str):
    host=os.getenv('SMTP_HOST','')
    sender=os.getenv('SMTP_FROM','')
    base=os.getenv('RESET_URL_BASE','')
    if not host or not sender or not base or not base.startswith('https://'):
        raise HTTPException(503,'Password reset email is not configured')
    port=int(os.getenv('SMTP_PORT','587'))
    username=os.getenv('SMTP_USER','')
    password=os.getenv('SMTP_PASSWORD','')
    msg=EmailMessage()
    msg['From']=sender
    msg['To']=email
    msg['Subject']='Instant Mechanic Hire — password reset'
    msg.set_content('Use this one-time link within 30 minutes:\n'+base.rstrip('/')+'?token='+quote(token))
    # STARTTLS with certificate verification. No plaintext fallback.
    with smtplib.SMTP(host,port,timeout=8) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if username:smtp.login(username,password)
        smtp.send_message(msg)


@router.post('/password-reset/request')
def request_reset(body:ResetRequest,request:Request,db:Session=Depends(get_db),cache:Redis=Depends(get_redis)):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.allowed_origins:
        raise HTTPException(403,'Origin not allowed')
    email=str(body.email).lower()
    key='imhire:resetlimit:'+hashlib.sha256(email.encode()).hexdigest()
    count=cache.incr(key)
    if count==1:cache.expire(key,3600)
    if count>5:raise HTTPException(429,'Too many reset requests')
    # Fail closed when email cannot be delivered.
    if not all([os.getenv('SMTP_HOST'),os.getenv('SMTP_FROM'),os.getenv('RESET_URL_BASE')]):
        raise HTTPException(503,'Password reset email is not configured')
    user=db.scalar(select(User).where(User.email==email,User.active.is_(True)))
    if user:
        token=secrets.token_urlsafe(48)
        digest=hashlib.sha256(token.encode()).hexdigest()
        ident=uuid.uuid4()
        expiry=datetime.now(timezone.utc)+timedelta(minutes=30)
        db.execute(text('INSERT INTO password_reset_requests(id,user_id,token_digest,expires_at) VALUES (:id,:uid,:digest,:exp)'),{'id':ident,'uid':user.id,'digest':digest,'exp':expiry})
        try:
            send_reset(email,token)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(503,'Password reset email delivery failed')
    return {'message':'If this account exists, a recovery email will be sent.'}


@router.post('/password-reset/confirm')
def confirm_reset(body:ResetConfirm, request:Request, db:Session=Depends(get_db),cache:Redis=Depends(get_redis)):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') not in settings.allowed_origins:raise HTTPException(403,'Origin not allowed')
    digest=hashlib.sha256(body.token.encode()).hexdigest()
    row=db.execute(text('SELECT id,user_id,expires_at,used_at FROM password_reset_requests WHERE token_digest=:d FOR UPDATE'),{'d':digest}).first()
    if not row or row[3] is not None or row[2].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400,'Invalid or expired reset token')
    user=db.get(User,row[1]);
    if not user or not user.active:raise HTTPException(400,'Invalid or expired reset token')
    user.password_hash=hash_password(body.password)
    db.execute(text('UPDATE password_reset_requests SET used_at=NOW() WHERE id=:id'),{'id':row[0]})
    # Revoke existing browser sessions for the reset account. This uses SCAN
    # because the original Phase 3 session storage had no per-user index.
    # For large deployments, replace with an indexed per-user session registry.
    for key in cache.scan_iter(match="imhire:sess:*",count=100):
        raw=cache.get(key)
        if raw:
            try:
                if json.loads(raw).get("user_id") == str(user.id): cache.delete(key)
            except (ValueError,TypeError): pass
    db.commit()
    return {'message':'Password updated. Sign in again.'}
