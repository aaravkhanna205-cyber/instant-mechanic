from sqlalchemy import create_engine, text
from app.core.config import settings


def check_postgres() -> bool:
    if not settings.database_url:
        return False
    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
