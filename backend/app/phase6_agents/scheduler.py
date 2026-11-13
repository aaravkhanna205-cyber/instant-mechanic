"""Idempotent scanner; only drafts proposals, never sends or changes hiring stage."""
import logging,time,os
from datetime import datetime,timedelta,timezone
from uuid import UUID
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.schema import Job, Application, Interview
from .service import create_proposal

log=logging.getLogger('phase6.scheduler')
def _safe(db,org,kind,target_type,target_id,key,stats)->int:
    """Draft one proposal. A record that cannot be drafted is skipped so the rest of the scan continues."""
    try:
        _,created=create_proposal(db,org,None,kind,target_type,target_id,key=key)
        return int(created)
    except Exception as exc:
        db.rollback();stats['skipped']+=1
        log.warning('Skipped %s %s: %s',target_type,target_id,getattr(exc,'detail',exc))
        return 0
def scan(db:Session)->dict:
    now=datetime.now(timezone.utc)
    stats={'interview_proposals':0,'followup_proposals':0,'skipped':0}
    rows=db.execute(select(Interview.id,Job.organization_id,Interview.scheduled_at).join(Application,Application.id==Interview.application_id).join(Job,Job.id==Application.job_id).where(Interview.status=='scheduled',Interview.scheduled_at>=now,Interview.scheduled_at<=now+timedelta(hours=24)).limit(200)).all()
    for interview_id,org,scheduled_at in rows:
        # Keyed by the interview's own date: one reminder per interview, a new one only if it is rescheduled.
        stats['interview_proposals']+=_safe(db,org,'interview_reminder','interview',interview_id,f'reminder:{interview_id}:{scheduled_at.date()}',stats)
    # Follow-up scanner is advisory only, no automatic messaging.
    rows=db.execute(select(Application.id,Job.organization_id).join(Job,Job.id==Application.job_id).where(Application.stage.in_(['applied','screening']),Application.applied_at<now-timedelta(days=3)).limit(200)).all()
    week='%d-W%02d' % now.isocalendar()[:2]
    for application_id,org in rows:
        # At most one follow-up draft per application per week.
        stats['followup_proposals']+=_safe(db,org,'application_followup','application',application_id,f'followup:{application_id}:{week}',stats)
    return stats

def run():
    logging.basicConfig(level=logging.INFO)
    engine=create_engine(settings.database_url,pool_pre_ping=True)
    log.info('Phase 6 scheduler: drafts only, approval required')
    while True:
        try:
            with Session(engine) as db:log.info('Scan: %s',scan(db))
        except KeyboardInterrupt:break
        except Exception:log.exception('Scheduler scan failed')
        time.sleep(300)
if __name__=='__main__':run()
