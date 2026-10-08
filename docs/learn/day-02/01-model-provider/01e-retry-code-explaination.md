## 1. `jittered_backoff(attempt)` — why we wait longer each time, with randomness added

```python
def jittered_backoff(attempt, *, base_delay=1.0, max_delay=30.0, jitter_ratio=0.5):
    exponent = max(0, attempt - 1)
    delay = min(base_delay * (2 ** exponent), max_delay)
    jitter = random.uniform(0, jitter_ratio * delay)
    return delay + jitter
```

**Why delay doubles each attempt:** if the first retry didn't work, trying again immediately is unlikely to work either — the problem (server overloaded, rate limited) probably hasn't gone away yet. Waiting longer each time gives the real problem more time to actually resolve.

**Why we add randomness on top:** imagine 10 of our calls all fail at the same moment and all wait the exact same fixed delay — they'd all retry at the exact same moment again, and likely collide and fail again, together. Adding a small random amount spreads retries out so they don't all land on the same instant.

**Why there's a `max_delay` cap:** without a ceiling, delay would keep doubling forever (2s, 4s, 8s, 16s, 32s, 64s...) until a failing call waits an absurd amount of time. Capping it at 30 seconds keeps a stuck pipeline failing visibly within a reasonable time.

## 2. `call_with_retry(fn)` — the actual retry loop

```python
def call_with_retry(fn, *, max_retries=3, sleep_fn=time.sleep):
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as error:
            classified = classify_error(error)
            if not classified.should_retry:
                raise
            if attempt == max_retries:
                raise
            sleep_fn(jittered_backoff(attempt))
```

**Why it asks `classify_error()` instead of retrying everything:** not every failure is worth retrying. A 503 (overloaded) might succeed on retry; a 401 (bad credentials) never will — retrying it just wastes time reproducing the exact same failure. `classify_error()` already knows which is which, so this function trusts that decision completely instead of guessing itself.

**Why it re-raises the ORIGINAL exception, not a new one:** if we wrapped the real error in some new custom exception, any code calling this function that does `except SomeRealAPIError:` would stop working — it would never see that real exception type anymore, just our wrapper. Keeping the original exception means nothing downstream has to change.

**Why it gives up after a fixed number of tries (`max_retries=3`):** without a limit, a persistently broken call would retry forever, which just hangs the whole program. Giving up after 3 tries means a genuinely broken situation fails loudly and visibly, instead of silently hanging.

## 3. `context_overflow` detection — why we have to read the error MESSAGE, not just a status code

```python
_CONTEXT_OVERFLOW_PATTERNS = (
    "prompt is too long",
    "context length",
    "context_length_exceeded",
)

if status_code == 400:
    error_text = str(error).lower()
    if any(p in error_text for p in _CONTEXT_OVERFLOW_PATTERNS):
        return ClassifiedError("context_overflow", should_retry=True, message=str(error))
    return ClassifiedError("bad_request", should_retry=False, message=str(error))
```

**Why this needs checking the message text, when nothing else in this file does:** every OTHER failure type here (rate limit, server error, auth) has its own distinct status code — easy to tell apart. A "the conversation is too big" failure, though, comes back as the SAME status code (400) as a generic "you sent a malformed request" failure. The only way to tell them apart is reading what Anthropic's error message actually SAYS.

**Why this is marked retryable even though it's a 400 (and every other 400 is NOT retryable):** a generic bad request will fail the exact same way if you resend it unchanged — there's nothing to gain from retrying. But a context-overflow failure genuinely CAN be fixed by sending something different (a shorter conversation) — so even though we don't yet have code that actually shrinks the input, marking it retryable keeps the door open for that fix to be added later, rather than permanently treating it like an un-fixable error.

## 4. `ProviderInvariantError` — why a bare `ValueError` wasn't good enough

```python
class ProviderInvariantError(Exception):
    """Raised when a provider adapter detects a condition its own code
    asserts should be impossible."""
```

**The real story behind why this exists:** our code has a defensive check — "if the API ever returns an impossible value, stop immediately instead of continuing with bad data." That check originally raised a plain `ValueError`. Once retry logic got added, a plain `ValueError` looked, to the retry system, exactly like any other unrecognized error — so it got automatically retried 3 times, wasting real time, even though **retrying can never fix an "impossible" condition** — if it was impossible once, it's still impossible the second and third time.

**Why we didn't just check `isinstance(error, ValueError)` instead of making a whole new class:** we tried that first, and it broke something else — a plain `ValueError` raised by completely unrelated code is NOT the same situation; that one SHOULD still be retried as an unknown error, since we don't actually know what caused it. Giving our specific internal check its own dedicated exception type means we can recognize "this exact situation" precisely, without accidentally also catching every unrelated `ValueError` anyone else's code might raise.
