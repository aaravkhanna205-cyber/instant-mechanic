import logging
import redis

from app.core.config import settings
from app.core.database import check_postgres

logger = logging.getLogger(__name__)


def check_redis() -> bool:
    if not settings.redis_url:
        return False
    client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
    try:
        return bool(client.ping())
    finally:
        client.close()


def check_dependencies() -> dict[str, bool]:
    results: dict[str, bool] = {}
    for name, probe in (("postgres", check_postgres), ("redis", check_redis)):
        try:
            results[name] = probe()
        except Exception as exc:
            logger.warning("Dependency %s unavailable (%s)", name, type(exc).__name__)
            results[name] = False
    return results
