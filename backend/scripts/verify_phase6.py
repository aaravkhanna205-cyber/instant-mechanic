"""Read-only verification: migration, table names and connectivity; no migration applied."""
from sqlalchemy import create_engine,inspect,text
from app.core.config import settings
from app.phase6_agents.models import AgentProposal
from redis import Redis
engine=create_engine(settings.database_url,pool_pre_ping=True,connect_args={'connect_timeout':5})
with engine.connect() as c:
    tables=set(inspect(c).get_table_names())
    required={'phase6_proposals','phase6_events','phase6_tasks','phase6_knowledge','phase6_deliveries'}
    missing=required-tables
    if missing: raise SystemExit(f'ERROR: Missing Phase 6 tables: {sorted(missing)}')
    revision=c.execute(text('SELECT version_num FROM alembic_version')).scalar()
    if revision not in ('0006_phase6_agents','0007_phase6_email_tracking'):raise SystemExit(f'ERROR: Unexpected Alembic revision {revision}')
cache=Redis.from_url(settings.redis_url,socket_connect_timeout=3)
assert cache.ping() is True
print('PHASE 6 READY: database tables, migration and Redis verified')
