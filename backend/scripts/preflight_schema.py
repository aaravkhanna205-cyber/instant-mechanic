"""Read-only safety check used before installing initial migration files."""
from sqlalchemy import create_engine, inspect, text
from app.core.config import settings


def main():
    if not settings.database_url:
        raise SystemExit('DATABASE_URL is empty; refuse to install migration.')
    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            if connection.dialect.name != 'postgresql':
                raise SystemExit('Expected PostgreSQL, not another database.')
            existing = set(inspect(connection).get_table_names(schema='public'))
            if existing:
                print('Existing public tables: ' + ', '.join(sorted(existing)))
                raise SystemExit('STOP: database is not empty. No migration files installed. Do not delete existing tables.')
            role = connection.execute(text('SELECT current_user')).scalar_one()
            database = connection.execute(text('SELECT current_database()')).scalar_one()
            print(f'Preflight passed: empty public schema in {database}; connected as {role}.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
