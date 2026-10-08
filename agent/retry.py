"""
agent/retry.py

Jittered backoff + a retry ceiling for recovering from classified,
retryable failures (agent/model_provider.py's classify_error). See
docs/standards/RELIABILITY.md §1 and
docs/learn/day-02/01-model-provider/01e-retry.md for the full reasoning.

A SMALL, SCOPED version of what Hermes's real agent/retry_utils.py and
agent/turn_retry_state.py do (/home/ubuntu/.hermes/hermes-agent/agent/):
same core idea (jittered exponential backoff, a bounded retry loop),
without Hermes's multi-vendor-specific pieces (the Z.AI Coding Plan
overload handling) or its 16-flag per-request recovery-strategy
bookkeeping (TurnRetryState) — we only have ONE recovery strategy
right now (retry with backoff), so a single counter is enough; see
docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md category E
for the full comparison and why TurnRetryState's pattern isn't needed
yet.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from agent.model_provider import ClassifiedError, classify_error

T = TypeVar("T")

# How many times to retry a classified-retryable failure before giving
# up and raising. Small and fixed, not configurable yet — this project
# has no real need for a per-call override until a concrete use case
# says otherwise (YAGNI, per the project's standing discipline).
DEFAULT_MAX_RETRIES = 3


def jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_ratio: float = 0.5,
) -> float:
    """Compute a jittered exponential backoff delay, in seconds.

    attempt: 1-based retry attempt number.

    Same core formula as Hermes's real jittered_backoff()
    (agent/retry_utils.py): delay doubles each attempt, capped at
    max_delay, plus a random amount so concurrent retries don't all
    collide on the same instant (the "thundering herd" problem — see
    01c-ornare-vs-hermes.md's KNOWLEDGE section for the full
    explanation). Defaults are smaller than Hermes's (base_delay=1.0 vs
    5.0, max_delay=30.0 vs 120.0) because our pipelines are short,
    bounded jobs, not long-lived interactive chat sessions — a shorter
    cap keeps a failing pipeline run failing visibly in a reasonable
    time rather than sitting silent for minutes.
    """
    exponent = max(0, attempt - 1)
    delay = min(base_delay * (2**exponent), max_delay)
    jitter = random.uniform(0, jitter_ratio * delay)
    return delay + jitter


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Call fn(), retrying with jittered backoff if it raises an
    exception that classify_error() says is worth retrying.

    Deliberately NOT a decorator and NOT baked into AnthropicProvider
    itself: this wraps any zero-argument callable, so a caller (e.g.
    AnthropicProvider.chat/stream, or a future second provider) decides
    WHEN to apply retry logic, rather than it being silently forced on
    every single call. See docs/engine/02-MODEL-PROVIDER.md's sequence
    diagram — "retry/backoff lives inside the adapter, never in the
    loop" — this is the piece an adapter calls to satisfy that rule.

    Raises the ORIGINAL exception (not a wrapped one) once retries are
    exhausted or the failure is classified as non-retryable — a caller
    catching the real exception type still works exactly as before.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as error:
            classified: ClassifiedError = classify_error(error)
            last_error = error
            if not classified.should_retry:
                raise
            if attempt == max_retries:
                raise
            sleep_fn(jittered_backoff(attempt))
    # Unreachable in practice (the loop always returns or raises), but
    # keeps the type checker honest about the function's real contract.
    assert last_error is not None
    raise last_error
