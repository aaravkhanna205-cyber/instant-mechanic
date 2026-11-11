"""Read-only verification of the complete Phase 3 schema and services."""
from sqlalchemy import create_engine, inspect, text
from redis import Redis
from app.core.config import settings
from app.models.schema import Base


def main():
    expected=set(Base.metadata.tables) | {'app_settings','import_batches','import_rows','password_reset_requests','data_deletion_requests','feature_flags'}
    engine=create_engine(settings.database_url,connect_args={'connect_timeout':5},pool_pre_ping=True)
    with engine.connect() as connection:
        existing=set(inspect(connection).get_table_names(schema='public'))
        missing=expected-existing
        rev=connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        vector=connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")).scalar_one()
        print(f'Application tables: {len(expected-missing)}/{len(expected)}')
        print('Alembic revision:',rev)
        print('pgvector:',bool(vector))
    engine.dispose()
    client=Redis.from_url(settings.redis_url,socket_timeout=3)
    try:
        pong=client.ping()
        print('Redis:',bool(pong))
    finally:client.close()
    if missing or rev!='0003_phase3_completion' or not vector or not pong:
        raise SystemExit('INCOMPLETE: '+', '.join(sorted(missing)))
    print('PHASE 3 DATABASE READY')

if __name__=='__main__':main()
