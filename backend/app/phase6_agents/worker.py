"""Free Phase 6 worker. Outbox by default; SMTP only when explicitly configured.
Run as a separate process. PostgreSQL is the durable job queue; Redis holds worker lock.
"""
import os
import time
import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from redis import Redis
from app.core.config import settings
from app.models.schema import User
from .models import AgentProposal, AgentDelivery
from .service import log_event
from .policy import safe_recipient

log=logging.getLogger('phase6.worker')

def deliver(recipient:str, subject:str, message:str, mode:str)->tuple[str,str|None]:
    """Outbox mode is a rehearsal, NOT an email delivery."""
    if not safe_recipient(recipient):raise ValueError('Invalid destination address')
    if mode=='outbox':return 'outbox','stored in database only; nothing sent'
    if mode!='smtp':raise ValueError('PHASE6_DELIVERY_MODE must be outbox or smtp')
    host=os.getenv('PHASE6_SMTP_HOST','')
    username=os.getenv('PHASE6_SMTP_USER','')
    password=os.getenv('PHASE6_SMTP_PASSWORD','')
    sender=os.getenv('PHASE6_SMTP_FROM','')
    port=int(os.getenv('PHASE6_SMTP_PORT','587'))
    if not (host and username and password and safe_recipient(sender)):
        raise RuntimeError('SMTP configuration missing; no message sent')
    if port not in (465,587): raise ValueError('SMTP port must be 465 or 587')
    msg=EmailMessage()
    msg['From']=sender;msg['To']=recipient;msg['Subject']=subject[:180]
    msg.set_content(message)
    if port==465:
        with smtplib.SMTP_SSL(host,port,timeout=15,context=ssl.create_default_context()) as smtp:
            smtp.login(username,password);smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=15) as smtp:
            smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
            smtp.login(username,password);smtp.send_message(msg)
    # SMTP acceptance is not proof the recipient opened the mail.
    return 'smtp_accepted',None

def process_one(db:Session,mode='outbox')->bool:
    now=datetime.now(timezone.utc)
    q=select(AgentProposal).where(AgentProposal.state=='queued').where((AgentProposal.next_attempt_at.is_(None)) | (AgentProposal.next_attempt_at<=now)).order_by(AgentProposal.created_at).limit(1).with_for_update(skip_locked=True)
    row=db.scalar(q)
    if row is None:return False
    if row.reviewed_by_id is None or row.reviewed_at is None:
        row.state='cancelled';log_event(db,row.organization_id,None,'delivery.blocked_missing_approval',row.id);db.commit();return True
    # One delivery row per proposal prevents accidental duplicate deliveries.
    previous=db.scalar(select(AgentDelivery).where(AgentDelivery.proposal_id==row.id))
    if previous and previous.status in ('smtp_accepted','outbox'):
        row.state='delivered' if previous.status=='smtp_accepted' else 'outbox';db.commit();return True
    user=db.get(User,row.recipient_user_id) if row.recipient_user_id else None
    if user is None or not user.active or not safe_recipient(user.email):
        row.state='failed';row.last_error='Recipient missing or inactive';row.attempts=5
        log_event(db,row.organization_id,None,'delivery.failed_invalid_recipient',row.id);db.commit();return True
    # Claim before making any outside network request.
    row.state='processing';row.attempts+=1;db.commit()
    try:
        status,detail=deliver(user.email,row.title,row.draft,mode)
        row=db.get(AgentProposal,row.id)
        row.state='delivered' if status=='smtp_accepted' else 'outbox';row.last_error=None
        db.add(AgentDelivery(proposal_id=row.id,organization_id=row.organization_id,recipient_email=user.email,mode=mode,status=status,reference=detail))
        log_event(db,row.organization_id,None,'delivery.'+status,row.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        row=db.get(AgentProposal,row.id)
        # Ambiguous SMTP failure can happen after server accepted message. No automatic retry
        # of a potentially delivered email: require manual review to avoid duplicates.
        row.state='failed';row.last_error=type(exc).__name__+': '+str(exc)[:300]
        row.next_attempt_at=None
        log_event(db,row.organization_id,None,'delivery.failed_review_required',row.id,{'attempts':row.attempts})
        db.commit();log.exception('Delivery failed: %s',row.id)
    return True

def run():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from dotenv import load_dotenv
    load_dotenv(override=False)  # private backend/.env, never committed
    mode=os.getenv('PHASE6_DELIVERY_MODE','outbox').strip().lower()
    if mode not in ('outbox','smtp'):raise SystemExit('PHASE6_DELIVERY_MODE must be outbox or smtp')
    if mode=='smtp' and os.getenv('PHASE6_SMTP_ENABLED')!='YES':raise SystemExit('Set PHASE6_SMTP_ENABLED=YES to enable actual email delivery')
    engine=create_engine(settings.database_url,pool_pre_ping=True,connect_args={'connect_timeout':5})
    cache=Redis.from_url(settings.redis_url,socket_connect_timeout=3)
    log.info('Phase 6 worker active. Delivery mode: %s',mode)
    while True:
        try:
            # Short Redis lease prevents simultaneous worker instances on the same host.
            if cache.set('imhire:p6:worker-lease',os.getpid(),nx=True,ex=25):
                try:
                    with Session(engine) as db:
                        while process_one(db,mode):pass
                finally:
                    # Do not delete a lease belonging to another worker.
                    lua='if redis.call("get",KEYS[1]) == ARGV[1] then return redis.call("del",KEYS[1]) else return 0 end'
                    cache.eval(lua,1,'imhire:p6:worker-lease',str(os.getpid()))
        except KeyboardInterrupt: break
        except Exception:log.exception('Worker loop failed')
        time.sleep(5)
if __name__=='__main__':run()
