"""
agent/adapters/openai/provider.py

The ModelProvider adapter that actually talks to OpenAI's real API
(Chat Completions). This is the ONE place in the whole engine allowed
to know OpenAI's specific wire format - see docs/engine/02-MODEL-PROVIDER.md.

Lives inside its own dedicated package, agent/adapters/openai/,
mirroring agent/adapters/anthropic/'s exact shape (provider.py +
quirks.py) - the test this project set for itself in
docs/engine/00-OVERVIEW.md: adding a second provider should require
ZERO changes to model_provider.py, the loop, or AnthropicProvider.
This file is the proof that held: nothing outside this new package
was touched to add OpenAI support.

Grounded in Hermes's real OpenAI-compatible transport
(/home/ubuntu/.hermes/hermes-agent/agent/transports/chat_completions.py,
1,042 lines) for the general shape of what a Chat Completions adapter
needs to handle - but, same scoping discipline as the Anthropic
adapter, NOT copying Hermes's full generality (Gemini-via-OpenAI-compat
quirks, reasoning-effort config per model family, prompt-cache-key
injection) since none of that is a real need for this project today.
"""

from __future__ import annotations

from typing import Iterator, Literal

from agent.adapters.openai.quirks import get_default_max_tokens
from agent.model_provider import (
    Message,
    ModelResponse,
    ProviderInvariantError,
    StreamEvent,
)
from agent.retry import call_with_retry

# OpenAI's Chat Completions finish_reason values map onto our engine's
# stop_reason vocabulary. Verified against the real SDK's type
# (openai.types.chat.chat_completion.Choice.finish_reason): "stop",
# "length", "tool_calls", "content_filter", "function_call" (the last
# is the deprecated pre-tool-calling name, kept for completeness).
_StopReason = Literal[
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "pause_turn",
    "refusal",
    "model_context_window_exceeded",
]

_FINISH_REASON_MAP: dict[str, _StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "refusal",
}


def _map_finish_reason(finish_reason: str) -> _StopReason:
    """Translate OpenAI's finish_reason into our engine's stop_reason
    vocabulary. Raises ProviderInvariantError on an unrecognized value
    rather than silently passing through a string our ModelResponse
    contract doesn't expect - same "fail loud, not silent" discipline
    as the Anthropic adapter's stop_reason=None check.
    """
    mapped = _FINISH_REASON_MAP.get(finish_reason)
    if mapped is None:
        raise ProviderInvariantError(
            f"OpenAI API returned an unrecognized finish_reason "
            f"'{finish_reason}' - this should be impossible; treat as "
            f"a provider-side anomaly, not a retryable error."
        )
    return mapped


class OpenAIProvider:
    """Satisfies the ModelProvider Protocol structurally (see
    model_provider.py) - same structural-typing pattern as
    AnthropicProvider, no inheritance.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-luna",
        max_tokens: int | None = None,
    ):
        """
        max_tokens: if omitted (None), uses the model's real max
        output limit (agent/adapters/openai/quirks.py
        get_default_max_tokens) - unlike AnthropicProvider, this is
        NOT capped below the model's true capability, because the
        installed OpenAI SDK has no non-streaming-timeout restriction
        equivalent to Anthropic's (verified directly, not assumed -
        see quirks.py's docstring and the Day 2 commit history for the
        live-call verification).
        """
        # Imported here, not at module level, so model_provider.py's
        # generic pieces stay usable even where the openai package
        # isn't installed - same reasoning as AnthropicProvider.
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = (
            max_tokens if max_tokens is not None else get_default_max_tokens(model)
        )

    def chat(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> ModelResponse:
        """Send a full request, get one complete response back.

        Translates our engine's vendor-agnostic Message/tools shape
        into OpenAI's exact wire format (a system message prepended to
        the messages list - OpenAI has no separate top-level `system`
        parameter, unlike Anthropic), sends it, and translates the
        real response back into our engine's ModelResponse shape.

        Wrapped in call_with_retry (agent/retry.py), same as
        AnthropicProvider.chat() - the SAME retry/classification logic
        is reused unchanged, proving classify_error() genuinely is
        vendor-agnostic, not secretly Anthropic-shaped.
        """

        def _do_chat() -> ModelResponse:
            openai_messages = [{"role": "system", "content": system}] + [
                {"role": m.role, "content": m.content} for m in messages
            ]

            response = self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=self._max_tokens,
                messages=openai_messages,
                tools=tools if tools else None,
            )

            choice = response.choices[0]
            stop_reason = _map_finish_reason(choice.finish_reason)

            # The SDK types usage as Optional - verified against the
            # real type (ChatCompletion.usage: CompletionUsage | None)
            # rather than assumed. A non-streaming chat() call should
            # always include usage; if it's ever missing, that's a
            # provider-side anomaly worth failing loudly on, same
            # "fail loud, not silent" discipline as the Anthropic
            # adapter's stop_reason=None check.
            if response.usage is None:
                raise ProviderInvariantError(
                    "OpenAI API returned no usage data on a "
                    "non-streaming response - this should be "
                    "impossible; treat as a provider-side anomaly, "
                    "not a retryable error."
                )

            return ModelResponse(
                content=choice.message.content,
                stop_reason=stop_reason,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        return call_with_retry(_do_chat)

    def stream(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> Iterator[StreamEvent]:
        """Send a full request, get the response back piece by piece.

        Uses the real SDK's stream=True Chat Completions call and
        translates its raw chunk events into our engine's StreamEvent
        shape - same "ask what the caller needs" principle as the
        Anthropic adapter: only text-arriving and stream-ending are
        translated, nothing else.

        Retry is scoped the same careful way as AnthropicProvider.stream():
        only the call that OPENS the stream is retried; once any text
        has reached the caller, a failure is raised as-is, never
        retried, to avoid duplicated text.
        """
        openai_messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

        def _open_stream():
            return self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=self._max_tokens,
                messages=openai_messages,
                tools=tools if tools else None,
                stream=True,
                stream_options={"include_usage": True},
            )

        stream = call_with_retry(_open_stream)

        final_finish_reason: str | None = None
        final_input_tokens = 0
        final_output_tokens = 0

        for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is not None and choice.delta.content:
                yield StreamEvent(type="text_delta", data=choice.delta.content)
            if choice is not None and choice.finish_reason is not None:
                final_finish_reason = choice.finish_reason
            # The final chunk (after stream_options={"include_usage": True})
            # carries usage with an EMPTY choices list - verified against
            # the real SDK's streaming chunk shape, not assumed.
            if chunk.usage is not None:
                final_input_tokens = chunk.usage.prompt_tokens
                final_output_tokens = chunk.usage.completion_tokens

        if final_finish_reason is None:
            raise ProviderInvariantError(
                "OpenAI API stream ended without ever sending a "
                "finish_reason - this should be impossible; treat as "
                "a provider-side anomaly, not a retryable error."
            )

        yield StreamEvent(
            type="message_stop",
            data=ModelResponse(
                content=None,
                stop_reason=_map_finish_reason(final_finish_reason),
                input_tokens=final_input_tokens,
                output_tokens=final_output_tokens,
            ),
        )
