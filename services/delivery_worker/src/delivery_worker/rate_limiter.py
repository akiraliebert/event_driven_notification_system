"""Redis sliding window rate limiter for delivery providers."""

import time
import uuid

from redis import Redis

from delivery_worker.config import RateLimitConfig


class RateLimiter:
    """Per-channel rate limiter using Redis sorted sets (sliding window).

    Each delivery attempt is recorded as a member in a sorted set keyed
    by channel name.  The score is the UNIX timestamp.  Before allowing
    a new attempt the window is trimmed and the current count compared
    against the configured limit.
    """

    KEY_PREFIX = "ratelimit"

    def __init__(self, redis_client: Redis, config: RateLimitConfig) -> None:
        self._redis = redis_client
        self._config = config

    def acquire(self, channel: str) -> bool:
        """Try to acquire a rate limit slot for *channel*.

        Returns True if the request is allowed, False if the limit
        has been reached.
        """
        key = f"{self.KEY_PREFIX}:{channel}"
        now = time.time()
        window_start = now - self._config.window_seconds
        limit = self._config.limit_for_channel(channel)

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        results = pipe.execute()
        current_count: int = results[1]

        if current_count >= limit:
            return False

        self._redis.zadd(key, {str(uuid.uuid4()): now})
        self._redis.expire(key, self._config.window_seconds + 1)
        return True
