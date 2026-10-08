"""
agent/model_provider.py

See docs/engine/02-MODEL-PROVIDER.md for the full spec, and
docs/learn/day-02/01-model-provider.md for the teaching walkthrough.

Step 1 of 5: the shared, vendor-agnostic vocabulary every provider
speaks. Nothing in this file yet knows Anthropic exists.
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
    decision is actually based on.
    """

    content: Any
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]
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


FailureType = Literal[
    "rate_limit",
    "server_error",
    "auth",
    "bad_request",
    "timeout",
    "unknown",
]


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
    """Classify a raw exception from the Anthropic SDK into a
    ClassifiedError, per the failure table in
    docs/learn/day-02/01-model-provider.md's "Deeper levels" section.

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
        return ClassifiedError("bad_request", should_retry=False, message=str(error))

    # No status code at all is the signature of a network-level failure
    # (connection error, read timeout) rather than an API-level one.
    if status_code is None and isinstance(error, (TimeoutError, OSError)):
        return ClassifiedError("timeout", should_retry=True, message=str(error))

    return ClassifiedError("unknown", should_retry=True, message=str(error))
