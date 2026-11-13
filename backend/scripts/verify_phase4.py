from sqlalchemy import create_engine,text
from app.core.config import settings

def main():
    engine=create_engine(settings.database_url,pool_pre_ping=True)
    with engine.connect() as conn:
        revision=conn.execute(text('select version_num from alembic_version')).scalar_one()
        tables=set(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
        required={'phase4_documents','phase4_chunks','phase4_reviews'}
        extension=conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")).scalar_one()
    print('Revision:',revision,'Phase 4 tables:',len(required & tables),'/',len(required),'pgvector:',extension)
    if revision not in ('0004_phase4_ai','0005_interview_studio','0006_phase6_agents') or not required.issubset(tables) or not extension:
        raise SystemExit('PHASE 4 SCHEMA NOT READY')
    print('PHASE 4 SCHEMA READY')
if __name__=='__main__':main()
