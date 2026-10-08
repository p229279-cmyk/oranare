"""
agent/model_provider.py

See docs/engine/02-MODEL-PROVIDER.md for the full spec, and
docs/learn/day-02/01-model-provider.md for the teaching walkthrough.

Step 1 of 5: the shared, vendor-agnostic vocabulary every provider
speaks. Nothing in this file yet knows Anthropic exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


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
