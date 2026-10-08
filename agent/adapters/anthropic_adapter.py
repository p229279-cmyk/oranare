"""
agent/adapters/anthropic_adapter.py

The ModelProvider adapter that actually talks to Anthropic's real API.
This is the ONE place in the whole engine allowed to know Anthropic's
specific wire format — see docs/engine/02-MODEL-PROVIDER.md.

Kept as its own separate file, not folded into model_provider.py,
matching Hermes's own real pattern of one file per provider adapter
(anthropic_adapter.py, bedrock_adapter.py, vertex_adapter.py,
gemini_native_adapter.py, codex_responses_adapter.py,
azure_identity_adapter.py — never merged into one shared module).

One deliberate difference from Hermes: Hermes keeps these files flat
directly in agent/, with no dedicated subfolder. We group ours under
agent/adapters/ instead — a conscious choice anticipating more adapters
being added over time, keeping agent/ itself from accumulating many
individual provider files as the engine grows. A future second provider
for this engine gets its own new file here too, e.g.
agent/adapters/openai_adapter.py — zero changes to model_provider.py or
to this file when that happens.
"""

from __future__ import annotations

from typing import Iterator

from agent.model_provider import Message, ModelResponse, StreamEvent


class AnthropicProvider:
    """Satisfies the ModelProvider Protocol structurally (see
    model_provider.py) — note there is no
    `class AnthropicProvider(ModelProvider):` inheritance; having the
    right methods is enough.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5", max_tokens: int = 4096):
        # Imported here, not at module level, so model_provider.py's
        # generic pieces (and anything that imports from it) stay usable
        # even in a context where the anthropic package isn't installed.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def chat(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> ModelResponse:
        """Send a full request, get one complete response back.

        Translates our engine's vendor-agnostic Message/tools shape
        into Anthropic's exact wire format, sends it, and translates
        the real response back into our engine's ModelResponse shape.
        """
        anthropic_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=anthropic_messages,
            tools=tools,
        )

        # The SDK types stop_reason as Optional — None only happens on
        # an incomplete/streaming-in-progress response, which this
        # non-streaming call should never produce. We fail loudly with
        # a clear message rather than let a None silently violate our
        # own ModelResponse.stop_reason contract (which requires one of
        # the 7 real values, never None) or crash with a cryptic
        # dataclass type error two layers away from the real cause.
        if response.stop_reason is None:
            raise ValueError(
                "Anthropic API returned stop_reason=None on a "
                "non-streaming response — this should be impossible; "
                "treat as a provider-side anomaly, not a retryable error."
            )

        return ModelResponse(
            content=response.content,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> Iterator[StreamEvent]:
        """Send a full request, get the response back piece by piece.

        Uses the real SDK's `messages.stream()` context manager and
        translates its raw stream events into our engine's StreamEvent
        shape. We deliberately translate only the event types a caller
        actually needs to react to incrementally (text arriving, the
        stream ending) rather than exposing every raw SDK event type —
        same "ask what the caller needs" principle as the rest of this
        file. A caller that needs the complete final message (e.g. to
        know the final stop_reason or token counts) reads it from the
        "message_stop" event's data, built the same way chat() builds
        a ModelResponse.
        """
        anthropic_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=anthropic_messages,
            tools=tools,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield StreamEvent(type="text_delta", data=event.delta.text)
                elif event.type == "message_stop":
                    final = stream.get_final_message()
                    if final.stop_reason is None:
                        raise ValueError(
                            "Anthropic API returned stop_reason=None at "
                            "the end of a completed stream — this should "
                            "be impossible; treat as a provider-side "
                            "anomaly, not a retryable error."
                        )
                    yield StreamEvent(
                        type="message_stop",
                        data=ModelResponse(
                            content=final.content,
                            stop_reason=final.stop_reason,
                            input_tokens=final.usage.input_tokens,
                            output_tokens=final.usage.output_tokens,
                        ),
                    )
