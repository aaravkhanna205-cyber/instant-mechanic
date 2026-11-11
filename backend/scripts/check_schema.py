"""Read-only database verification. Run after Alembic upgrade head."""
from sqlalchemy import create_engine, inspect, text
from app.core.config import settings
from app.models.schema import Base


def main():
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            names = set(inspect(connection).get_table_names(schema="public"))
            expected = set(Base.metadata.tables)
            missing = expected - names
            vector = connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")).scalar_one()
            print(f"Application tables: {len(expected - missing)}/{len(expected)}")
            print(f"pgvector enabled: {vector}")
            print(f"Alembic version: {connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()}")
            if missing or not vector:
                raise SystemExit("Schema not ready: " + ', '.join(sorted(missing)))
            print("SCHEMA READY")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
