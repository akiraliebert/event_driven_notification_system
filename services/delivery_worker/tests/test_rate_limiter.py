"""Tests for the Redis sliding window rate limiter."""

from unittest.mock import MagicMock, call

from delivery_worker.config import RateLimitConfig
from delivery_worker.rate_limiter import RateLimiter


def _make_limiter(pipeline_zcard_result: int) -> tuple[RateLimiter, MagicMock]:
    """Create a RateLimiter with a mocked Redis client.

    *pipeline_zcard_result* controls what ZCARD returns so we can
    simulate "under limit" vs "over limit" scenarios.
    """
    config = RateLimitConfig(
        email_per_minute=10,
        sms_per_minute=5,
        push_per_minute=20,
        window_seconds=60,
    )
    redis_mock = MagicMock()
    pipe_mock = MagicMock()
    # pipeline().execute() returns [zremrangebyscore_result, zcard_result]
    pipe_mock.execute.return_value = [0, pipeline_zcard_result]
    redis_mock.pipeline.return_value = pipe_mock

    return RateLimiter(redis_mock, config), redis_mock


class TestRateLimiter:
    def test_acquire_allowed_when_under_limit(self) -> None:
        limiter, redis_mock = _make_limiter(pipeline_zcard_result=5)

        result = limiter.acquire("email")

        assert result is True
        redis_mock.zadd.assert_called_once()
        redis_mock.expire.assert_called_once()

    def test_acquire_denied_when_at_limit(self) -> None:
        limiter, redis_mock = _make_limiter(pipeline_zcard_result=10)

        result = limiter.acquire("email")

        assert result is False
        redis_mock.zadd.assert_not_called()

    def test_acquire_denied_when_over_limit(self) -> None:
        limiter, redis_mock = _make_limiter(pipeline_zcard_result=15)

        result = limiter.acquire("email")

        assert result is False

    def test_pipeline_trims_expired_entries(self) -> None:
        limiter, redis_mock = _make_limiter(pipeline_zcard_result=0)
        pipe_mock = redis_mock.pipeline.return_value

        limiter.acquire("sms")

        # First call on pipeline should be zremrangebyscore
        pipe_mock.zremrangebyscore.assert_called_once()
        args = pipe_mock.zremrangebyscore.call_args
        assert args[0][0] == "ratelimit:sms"
