"""Redis client settings shared by the app and the integration tests.

Retries a command 3 times with exponential backoff when the connection drops, and checks idle
pooled connections every 30 seconds. See api/app.py for why retrying is safe.
"""

from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError


def build_redis_client(url: str) -> Redis:
    return Redis.from_url(
        url,
        retry=Retry(ExponentialBackoff(), retries=3),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
        health_check_interval=30,
    )
