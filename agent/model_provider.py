"""
agent/model_provider.py

See docs/engine/02-MODEL-PROVIDER.md for the full spec, and
docs/learn/day-02/01-model-provider/01a-model-provider.md for the
teaching walkthrough.

This file holds ONLY the vendor-agnostic pieces: the shared data shapes,
the ModelProvider interface itself, and the failure classifier. No
vendor-specific code lives here — that's what
agent/adapters/anthropic/ (and any future provider's own
file) is for. This split matches Hermes's own real pattern of one file
per provider adapter — Hermes itself keeps these flat directly in
agent/ (anthropic_adapter.py, bedrock_adapter.py, vertex_adapter.py,
etc.), without a dedicated subfolder; we chose to group ours under
agent/adapters/ as a deliberate, named variation, anticipating more
adapters being added over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol


@dataclass
class Message:
    """One message in a conversation, in our engine's own shape —
    never a vendor's wire format directly.

    `content` is deliberately typed as `Any` at this layer: a message
    can be plain text (str) or a list of content blocks (text, tool
    use, tool result) depending on what happened in that turn. The
    ModelProvider adapter is responsible for translating this into
    whatever shape the real vendor API expects.
    """

    role: Literal["user", "assistant"]
    content: Any


@dataclass
class ModelResponse:
    """What comes back from a model call, in our engine's own shape.

    `stop_reason` tells the Agent Loop WHY the model stopped generating
    — this is what the loop's step-3 "tool call or final answer?"
    decision is actually based on. The full set of values matches
    Anthropic's real API (verified against the installed SDK, not
    guessed): "end_turn", "max_tokens", "stop_sequence", "tool_use",
    "pause_turn", "refusal", "model_context_window_exceeded".
    """

    content: Any
    stop_reason: Literal[
        "end_turn",
        "max_tokens",
        "stop_sequence",
        "tool_use",
        "pause_turn",
        "refusal",
        "model_context_window_exceeded",
    ]
    input_tokens: int
    output_tokens: int


@dataclass
class StreamEvent:
    """One piece of a streamed response. `type` tells the caller what
    KIND of event this is (a text delta, a tool-call starting, the
    stream ending) so they can react differently to each."""

    type: str
    data: Any = field(default=None)


class ModelProvider(Protocol):
    """The contract every model-vendor adapter must satisfy.

    This is a Protocol (structural typing), not an abstract base class:
    a class satisfies this interface just by having these two methods
    with these shapes — no explicit inheritance required. See
    docs/engine/02-MODEL-PROVIDER.md for the full spec and the reasoning
    behind this interface's exact shape.
    """

    def chat(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> ModelResponse:
        """Send a full request, get one complete response back."""
        ...

    def stream(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> Iterator[StreamEvent]:
        """Send a full request, get the response back piece by piece."""
        ...


class ProviderInvariantError(Exception):
    """Raised when a provider adapter detects a condition its own code
    asserts should be impossible (e.g. a non-streaming response with
    stop_reason=None) — see agent/adapters/anthropic/provider.py.

    Deliberately its OWN exception type, not a bare ValueError: this
    lets classify_error() tell "an internal invariant was violated" (==
    never worth retrying, since retrying can't change an impossible
    condition) apart from an ordinary ValueError raised by unrelated
    code (which should still fall through to the generic "unknown,
    retryable" bucket). A real bug was caught by this exact
    distinction: an earlier version checked isinstance(error,
    ValueError) directly, which misclassified a plain
    ValueError("something we've never seen") as non-retryable too.
    """


FailureType = Literal[
    "rate_limit",
    "server_error",
    "context_overflow",
    "auth",
    "bad_request",
    "timeout",
    "unknown",
]

# Patterns that identify a context-overflow 400, verified against
# Anthropic's own documented error shape (invalid_request_error whose
# message contains this kind of phrasing). A small, scoped subset of
# Hermes's real _CONTEXT_OVERFLOW_PATTERNS
# (/home/ubuntu/.hermes/hermes-agent/agent/error_classifier.py) — Hermes
# needs a longer list because it also talks to OpenAI-shaped, vLLM, and
# other local-inference-server error text; we only ever talk to
# Anthropic directly, so we only need the phrasing Anthropic itself
# actually uses.
_CONTEXT_OVERFLOW_PATTERNS = (
    "prompt is too long",
    "context length",
    "context_length_exceeded",
)


@dataclass
class ClassifiedError:
    """The result of classify_error(): what kind of failure this was,
    and whether retrying has any real chance of succeeding.

    See docs/standards/RELIABILITY.md §1 for the full recovery table
    this classification feeds into.
    """

    failure_type: FailureType
    should_retry: bool
    message: str


def classify_error(error: Exception) -> ClassifiedError:
    """Classify a raw exception from a model provider's SDK into a
    ClassifiedError, per the failure table in
    docs/learn/day-02/01-model-provider/01a-model-provider.md's "Deeper
    levels" section.

    Built and tested standalone (see tests/) — no live API call needed
    to prove this logic is correct, per the project's standing honesty
    rule on testing without a live key.
    """
    status_code = getattr(error, "status_code", None)

    if status_code == 429:
        return ClassifiedError("rate_limit", should_retry=True, message=str(error))
    if status_code in (500, 502, 503, 529):
        return ClassifiedError("server_error", should_retry=True, message=str(error))
    if status_code == 401:
        return ClassifiedError("auth", should_retry=False, message=str(error))
    if status_code == 400:
        # A 400 can mean several different real problems depending on the
        # message text — we check for the one that needs a DIFFERENT fix
        # (shrink the input, don't just retry unchanged) before falling
        # through to the generic "malformed request" bucket. Verified
        # against Anthropic's real documented error shape: context
        # overflow surfaces as a 400 invalid_request_error whose message
        # contains phrasing like "prompt is too long" or "context length"
        # — not a distinct status code of its own, which is why text
        # inspection is genuinely necessary here, not a shortcut.
        error_text = str(error).lower()
        if any(p in error_text for p in _CONTEXT_OVERFLOW_PATTERNS):
            return ClassifiedError(
                "context_overflow", should_retry=True, message=str(error)
            )
        return ClassifiedError("bad_request", should_retry=False, message=str(error))

    # Timeouts/connection failures have NO status_code (nothing ever
    # responded), unlike every case above where a status_code is always
    # present. We check by exception TYPE NAME rather than importing any
    # specific SDK's exception classes directly, so this file stays
    # usable even if no provider SDK is installed (e.g. during a pure
    # unit-test run) — a real adapter file is free to import its SDK
    # directly, but this shared classifier does not need to.
    error_type_names = {t.__name__ for t in type(error).__mro__}
    if status_code is None and (
        isinstance(error, (TimeoutError, OSError))
        or "APITimeoutError" in error_type_names
        or "APIConnectionError" in error_type_names
    ):
        return ClassifiedError("timeout", should_retry=True, message=str(error))

    # An internal invariant violation (ProviderInvariantError) is never
    # a real API/network failure — retrying it is pointless: nothing
    # about retrying the same call makes an "impossible" condition any
    # less impossible. Checked by a dedicated exception TYPE, not by
    # guessing from a bare ValueError (a generic ValueError from
    # unrelated code must still fall through to "unknown" below, so a
    # type-name check — not an isinstance(error, ValueError) check —
    # is the correct boundary here). Caught by a real test running
    # slower than expected (a real sleep burned retrying this), not
    # assumed in advance.
    if "ProviderInvariantError" in error_type_names:
        return ClassifiedError("bad_request", should_retry=False, message=str(error))

    return ClassifiedError("unknown", should_retry=True, message=str(error))
