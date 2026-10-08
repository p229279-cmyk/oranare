# Day 2, Component 1e — Retry & Backoff (agent/retry.py)

This is "category E" from `01c-ornare-vs-hermes.md`, finally built. See
that file first for the full Hermes-comparison reasoning (jittered
backoff, Hermes's real `retry_utils.py` and `TurnRetryState`); this doc
covers the component itself, same fixed teaching order as every other
component.

## Whole

`agent/retry.py` is the piece that makes a RETRYABLE failure (per
`classify_error()` in `model_provider.py`) actually get retried,
instead of just being correctly labeled and then failing anyway.
Before this file existed, `classify_error()` could tell you a 503 was
worth retrying — but nothing in the codebase acted on that fact.

## Boundaries

What's INSIDE this component:
- Computing a jittered backoff delay for a given retry attempt.
- Calling a function, catching a retryable failure, waiting, and
  trying again — up to a fixed ceiling.

What's OUTSIDE this component (owned elsewhere):
- Deciding WHETHER a failure is retryable at all — that's
  `classify_error()` in `model_provider.py`. This file trusts that
  decision completely; it never re-implements failure classification.
- Deciding WHEN to apply retry at all — that's each caller's choice
  (`AnthropicProvider.chat`/`stream`), not baked into every call
  silently.
- Tracking MULTIPLE distinct recovery strategies per request (Hermes's
  `TurnRetryState` — see "Underlying principles" below for why that's
  explicitly not needed yet).

## Parts

- **`jittered_backoff(attempt, ...)`** — computes one delay, given a
  1-based attempt number. Pure function, no side effects, easy to test
  exactly.
- **`call_with_retry(fn, ...)`** — the actual retry loop. Takes any
  zero-argument callable, calls it, and on a retryable failure sleeps
  (using `jittered_backoff`) and tries again, up to `max_retries`.
- **`DEFAULT_MAX_RETRIES`** — a small, fixed ceiling (3), not yet
  configurable per call — no real need for per-call tuning exists yet.

## Relationships

```
AnthropicProvider.chat()  --wraps its real API call in-->  call_with_retry
AnthropicProvider.stream()  --wraps OPENING the connection in-->  call_with_retry
call_with_retry  --asks-->  classify_error()  --lives in-->  model_provider.py
call_with_retry  --waits using-->  jittered_backoff()
```

`call_with_retry` never duplicates `classify_error`'s logic — it's a
pure consumer of that decision.

## Mechanisms

Two real mechanisms:

1. **Exponential growth with randomness ("jitter").** Each retry waits
   LONGER than the last (doubling), but with a random amount added so
   multiple callers retrying at once don't all retry at the exact same
   instant and collide again (the "thundering herd" problem — see
   `01c-ornare-vs-hermes.md`'s KNOWLEDGE section for the full
   explanation with Hermes's real numbers).
2. **A bounded loop that re-raises the ORIGINAL exception.**
   `call_with_retry` never wraps the real exception in a new type — a
   caller's `except SomeRealErrorType` still works exactly as if no
   retry logic existed, it just might fire a bit later.

## Underlying principles

- **"Retry logic is a separate concern from classification logic, and
  mixing them makes both harder to test."** `classify_error()` is
  tested completely without ever sleeping or looping — it's pure
  input→output. `call_with_retry` is tested completely without ever
  needing a real network call — it's tested with fake functions and a
  fake `sleep_fn`. Neither test needs the other's complexity.
- **"A single counter is enough until there's a real second recovery
  strategy — don't build the bookkeeping object before you need it."**
  Hermes's `TurnRetryState` exists because Hermes tries MANY different
  specific fixes per failed request (OAuth refresh, image shrinking, a
  llama.cpp-specific workaround...), each needing its own one-shot
  guard. We have exactly ONE recovery strategy right now (retry with
  backoff) — a single attempt counter inside the loop is suffficient.
  The moment a second distinct recovery strategy is needed (e.g.
  "shrink the input on context_overflow, then retry" — not yet built),
  that's the real trigger to revisit this, not before.
- **"Retry must never re-raise a DIFFERENT exception than what
  actually happened."** Wrapping the real error in a custom
  `RetryExhaustedError` would be more "elegant" on paper, but it breaks
  every caller's existing `except SpecificRealError` handling. Keeping
  the original exception type, just delayed, costs nothing and
  preserves every caller's existing error-handling code unchanged.

## Deeper levels — a real bug this retry logic itself caused, caught by a slow test

This is worth a full walkthrough, same honesty standard as every other
component in this project: a real mistake was made and caught, not
assumed away.

**What happened:** once `call_with_retry` was wired into `chat()`,
the EXISTING test for the defensive "stop_reason=None, this should be
impossible" check (written back when category C was built) suddenly
started taking **3.5 seconds** instead of a few milliseconds.

**Why:** that defensive check raises a bare `ValueError`. Before retry
existed, a bare exception just propagated immediately — nothing
noticed or cared that it wasn't classified. Once `classify_error()` was
consulted (inside `call_with_retry`), a bare `ValueError` with no
`status_code` fell all the way through to the generic `"unknown"`
bucket — which is marked `should_retry=True`. So the test was actually
retrying a condition that is, by definition, impossible to fix by
retrying — burning 3 real sleep cycles before finally giving up and
raising.

**The first fix attempt was ALSO wrong, and caught immediately:**
checking `isinstance(error, ValueError)` directly and marking it
non-retryable seemed right — until a DIFFERENT existing test
(`test_unrecognized_error_defaults_to_retryable_unknown`, which
deliberately raises a plain `ValueError("something we've never
seen")` to prove random unknown errors stay retryable) started
failing. The fix was too broad: it silently reclassified EVERY plain
`ValueError` as non-retryable, not just the ONE specific internal
invariant violation it was meant to catch.

**The real fix — a dedicated exception type, not a guess by base
class:** a new exception, `ProviderInvariantError` (in
`model_provider.py`, alongside `classify_error` since it's part of the
same classification contract), replaces the bare `ValueError` the
adapter raises for its "this should be impossible" checks.
`classify_error()` checks for this SPECIFIC type name — a generic
`ValueError` from anywhere else in the codebase still correctly falls
through to `"unknown, retryable"`, exactly as before.

**The one-sentence rule underneath this section:** *when you need to
tell "my own code's internal invariant broke" apart from "literally
any other error that happens to share a common base class," reach for
a dedicated exception type — guessing from `isinstance` against a
broad built-in type is a trap that looks right until the next
legitimate use of that same built-in type collides with it.*

## Coding

Built in this order:

1. `agent/retry.py` — `jittered_backoff()`, then `call_with_retry()`,
   then `DEFAULT_MAX_RETRIES`.
2. `model_provider.py` — added the `"context_overflow"` failure type
   and the small `_CONTEXT_OVERFLOW_PATTERNS` tuple, wired into
   `classify_error()`'s existing 400-handling branch (checked BEFORE
   falling through to the generic `bad_request` bucket).
3. `AnthropicProvider.chat()` wrapped in `call_with_retry`.
4. `AnthropicProvider.stream()` wrapped more carefully — only the
   connection-opening step (`__enter__`) is retried, never the
   iteration itself, so a caller never sees duplicated text.
5. The `stop_reason=None` bug found and fixed:
   `ProviderInvariantError` added to `model_provider.py`, both raise
   sites in `provider.py` switched from `ValueError` to it,
   `classify_error()` updated to check for this specific type.

## Code understanding

Full function-by-function explanation lives in
[`01e-retry-code-explaination.md`](01e-retry-code-explaination.md).
