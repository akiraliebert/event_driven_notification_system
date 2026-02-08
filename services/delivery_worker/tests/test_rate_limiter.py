"""Tests for the Redis sliding window rate limiter."""

from unittest.mock import MagicMock

from delivery_worker.config import RateLimitConfig
from delivery_worker.rate_limiter import RateLimiter


def _make_limiter(lua_result: int) -> tuple[RateLimiter, MagicMock]:
    """Create a RateLimiter with a mocked Redis client.

    *lua_result* controls what the Lua script returns:
    1 = request allowed, 0 = rate limited.
    """
    config = RateLimitConfig(
        email_per_minute=10,
        sms_per_minute=5,
        push_per_minute=20,
        window_seconds=60,
    )
    redis_mock = MagicMock()
    script_mock = MagicMock(return_value=lua_result)
    redis_mock.register_script.return_value = script_mock

    limiter = RateLimiter(redis_mock, config)
    return limiter, script_mock


class TestRateLimiter:
    def test_acquire_allowed_when_under_limit(self) -> None:
        limiter, script_mock = _make_limiter(lua_result=1)

        result = limiter.acquire("email")

        assert result is True
        script_mock.assert_called_once()

    def test_acquire_denied_when_at_limit(self) -> None:
        limiter, script_mock = _make_limiter(lua_result=0)

        result = limiter.acquire("email")

        assert result is False
        script_mock.assert_called_once()

    def test_lua_script_called_with_correct_keys(self) -> None:
        limiter, script_mock = _make_limiter(lua_result=1)

        limiter.acquire("sms")

        call_kwargs = script_mock.call_args
        assert call_kwargs.kwargs["keys"] == ["ratelimit:sms"]

    def test_lua_script_receives_correct_limit(self) -> None:
        limiter, script_mock = _make_limiter(lua_result=1)

        limiter.acquire("push")

        call_kwargs = script_mock.call_args
        args = call_kwargs.kwargs["args"]
        # args = [window_start, limit, now, uuid, ttl]
        assert args[1] == 20  # push_per_minute

    def test_lua_script_receives_ttl(self) -> None:
        limiter, script_mock = _make_limiter(lua_result=1)

        limiter.acquire("email")

        call_kwargs = script_mock.call_args
        args = call_kwargs.kwargs["args"]
        # ttl = window_seconds + 1 = 61
        assert args[4] == 61
