"""Redis sliding window rate limiter for delivery providers."""

import time
import uuid

from redis import Redis

from delivery_worker.config import RateLimitConfig

# Lua script for atomic rate limiting.
# Trims expired entries, checks count, and conditionally adds a new member —
# all within a single Redis EVAL call (no race conditions).
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return 1
"""


class RateLimiter:
    """Per-channel rate limiter using Redis sorted sets (sliding window).

    Each delivery attempt is recorded as a member in a sorted set keyed
    by channel name.  The score is the UNIX timestamp.  Before allowing
    a new attempt the window is trimmed and the current count compared
    against the configured limit.

    Uses a Lua script to make the check-and-set operation atomic across
    concurrent Celery workers.
    """

    KEY_PREFIX = "ratelimit"

    def __init__(self, redis_client: Redis, config: RateLimitConfig) -> None:
        self._redis = redis_client
        self._config = config
        self._script = self._redis.register_script(_RATE_LIMIT_LUA)

    def acquire(self, channel: str) -> bool:
        """Try to acquire a rate limit slot for *channel*.

        Returns True if the request is allowed, False if the limit
        has been reached.
        """
        key = f"{self.KEY_PREFIX}:{channel}"
        now = time.time()
        window_start = now - self._config.window_seconds
        limit = self._config.limit_for_channel(channel)
        ttl = self._config.window_seconds + 1

        result = self._script(
            keys=[key],
            args=[window_start, limit, now, str(uuid.uuid4()), ttl],
        )
        return bool(result)
