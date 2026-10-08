"""
tests/test_model_provider.py

Tests for agent/model_provider.py's classify_error() — see
docs/learn/day-02/01-model-provider.md Step 3 for the reasoning.

These tests use fabricated fake exceptions, not a real API call —
proving the classification logic is correct needs no network, no API
key, and is not flaky.
"""

from agent.model_provider import classify_error


class FakeAPIError(Exception):
    """A minimal stand-in for anthropic's real error classes — only
    needs a status_code attribute, since that's all classify_error()
    reads from it."""

    def __init__(self, status_code: int | None, message: str = "fake error"):
        super().__init__(message)
        self.status_code = status_code


def test_rate_limit_is_retryable():
    result = classify_error(FakeAPIError(429))
    assert result.failure_type == "rate_limit"
    assert result.should_retry is True


def test_server_error_is_retryable():
    for code in (500, 502, 503, 529):
        result = classify_error(FakeAPIError(code))
        assert result.failure_type == "server_error"
        assert result.should_retry is True


def test_auth_failure_is_not_retryable():
    result = classify_error(FakeAPIError(401))
    assert result.failure_type == "auth"
    assert result.should_retry is False


def test_bad_request_is_not_retryable():
    result = classify_error(FakeAPIError(400))
    assert result.failure_type == "bad_request"
    assert result.should_retry is False


def test_timeout_is_retryable():
    result = classify_error(TimeoutError("connection timed out"))
    assert result.failure_type == "timeout"
    assert result.should_retry is True


def test_unrecognized_error_defaults_to_retryable_unknown():
    result = classify_error(ValueError("something we've never seen"))
    assert result.failure_type == "unknown"
    assert result.should_retry is True
