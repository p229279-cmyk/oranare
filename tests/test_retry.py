"""
tests/test_retry.py

Tests for agent/retry.py — see
docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md category E
and docs/learn/day-02/01-model-provider/01e-retry.md.
"""

from unittest.mock import MagicMock

import pytest

from agent.retry import DEFAULT_MAX_RETRIES, call_with_retry, jittered_backoff


class _FakeAPIError(Exception):
    """Mirrors the real Anthropic SDK's exception shape (a status_code
    attribute) without needing the real SDK installed or a live call."""

    def __init__(self, status_code, message="fake error"):
        self.status_code = status_code
        super().__init__(message)


def test_jittered_backoff_grows_with_attempt_number():
    # Use a fixed seed-free check: later attempts should produce a
    # LARGER base delay on average. We check the deterministic lower
    # bound (jitter is always >= 0) since the random component makes
    # an exact equality check flaky.
    assert jittered_backoff(1, jitter_ratio=0) == 1.0  # base_delay * 2^0
    assert jittered_backoff(2, jitter_ratio=0) == 2.0  # base_delay * 2^1
    assert jittered_backoff(3, jitter_ratio=0) == 4.0  # base_delay * 2^2


def test_jittered_backoff_respects_max_delay_cap():
    huge_attempt_delay = jittered_backoff(50, max_delay=30.0, jitter_ratio=0)
    assert huge_attempt_delay == 30.0


def test_call_with_retry_succeeds_without_retrying_on_first_try():
    fn = MagicMock(return_value="ok")
    result = call_with_retry(fn, sleep_fn=MagicMock())
    assert result == "ok"
    assert fn.call_count == 1


def test_call_with_retry_retries_a_retryable_failure_then_succeeds():
    fn = MagicMock(
        side_effect=[_FakeAPIError(503), _FakeAPIError(503), "ok"]
    )
    sleep_fn = MagicMock()
    result = call_with_retry(fn, sleep_fn=sleep_fn)
    assert result == "ok"
    assert fn.call_count == 3
    # Slept once per failed attempt before succeeding - never on the
    # final successful call.
    assert sleep_fn.call_count == 2


def test_call_with_retry_does_not_retry_a_non_retryable_failure():
    """A 401 (auth) is classified as non-retryable - retrying it would
    just burn time reproducing the identical failure."""
    fn = MagicMock(side_effect=_FakeAPIError(401))
    sleep_fn = MagicMock()
    with pytest.raises(_FakeAPIError):
        call_with_retry(fn, sleep_fn=sleep_fn)
    assert fn.call_count == 1
    sleep_fn.assert_not_called()


def test_call_with_retry_gives_up_after_max_retries_and_raises_the_real_error():
    """A persistently retryable failure (e.g. provider stays overloaded
    for the whole window) must still eventually give up - it does not
    retry forever - and the ORIGINAL exception type must surface, not
    a wrapped one, so a caller's except block still works."""
    always_fails = MagicMock(side_effect=_FakeAPIError(503))
    sleep_fn = MagicMock()
    with pytest.raises(_FakeAPIError):
        call_with_retry(always_fails, max_retries=3, sleep_fn=sleep_fn)
    assert always_fails.call_count == 3
    assert sleep_fn.call_count == 2  # slept between attempts, not after the last


def test_default_max_retries_is_small_and_bounded():
    """Guards against this silently growing unbounded - a stuck call
    must give up in a reasonable, fixed number of attempts."""
    assert DEFAULT_MAX_RETRIES == 3
