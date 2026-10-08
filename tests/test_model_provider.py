"""
tests/test_model_provider.py

Tests for agent/model_provider.py's classify_error() — see
docs/learn/day-02/01-model-provider/01a-model-provider.md Step 3 for
the reasoning.

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
    result = classify_error(FakeAPIError(400, message="missing required field 'model'"))
    assert result.failure_type == "bad_request"
    assert result.should_retry is False


def test_context_overflow_is_retryable_despite_being_a_400():
    """A context-overflow is a 400 just like a malformed request, but
    needs a DIFFERENT classification (and a different real fix - shrink
    the input - though that shrinking logic itself is not built yet).
    Must be distinguished by message text, verified against Anthropic's
    real documented error shape, before falling through to the generic
    bad_request bucket."""
    for message in (
        "prompt is too long: 250000 tokens > 200000 maximum",
        "messages: context length exceeded for this model",
        "context_length_exceeded",
    ):
        result = classify_error(FakeAPIError(400, message=message))
        assert result.failure_type == "context_overflow", message
        assert result.should_retry is True


def test_timeout_is_retryable():
    result = classify_error(TimeoutError("connection timed out"))
    assert result.failure_type == "timeout"
    assert result.should_retry is True


def test_real_anthropic_timeout_error_is_classified_correctly():
    """Guards against a real bug we found: anthropic.APITimeoutError is
    NOT a subclass of TimeoutError/OSError, so classify_error() must
    detect it by type name, not just isinstance(). This test uses the
    REAL SDK exception class, not a fake stand-in, specifically to catch
    a regression here."""
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com")
    real_timeout = anthropic.APITimeoutError(request=request)
    result = classify_error(real_timeout)
    assert result.failure_type == "timeout"
    assert result.should_retry is True


def test_real_anthropic_rate_limit_error_is_classified_correctly():
    """Same idea, but for the status-code path: proves classify_error()
    works against the SDK's real RateLimitError, not just our
    FakeAPIError stand-in."""
    import anthropic
    import httpx2

    response = httpx2.Response(
        429, request=httpx2.Request("POST", "https://api.anthropic.com")
    )
    real_error = anthropic.RateLimitError(
        "rate limited", response=response, body=None
    )
    result = classify_error(real_error)
    assert result.failure_type == "rate_limit"
    assert result.should_retry is True


def test_unrecognized_error_defaults_to_retryable_unknown():
    result = classify_error(ValueError("something we've never seen"))
    assert result.failure_type == "unknown"
    assert result.should_retry is True


def test_provider_invariant_error_is_never_retried():
    """Regression test for a real bug caught by a test running slower
    than expected (a real sleep burned retrying this): an internal
    invariant violation (ProviderInvariantError, raised when a
    provider adapter detects a condition its own code asserts should
    be impossible) must be non-retryable - retrying can't make an
    impossible condition any less impossible. Must NOT be confused
    with a generic ValueError from unrelated code, which should still
    be "unknown, retryable" (see the test above)."""
    from agent.model_provider import ProviderInvariantError

    result = classify_error(ProviderInvariantError("stop_reason=None, impossible"))
    assert result.failure_type == "bad_request"
    assert result.should_retry is False
