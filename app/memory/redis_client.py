import redis

from app.config import REDIS_DB, REDIS_HOST, REDIS_PORT


def get_redis() -> redis.Redis:
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )

    client.ping()

    return client
