"""
agent/adapters/anthropic/provider.py

The ModelProvider adapter that actually talks to Anthropic's real API.
This is the ONE place in the whole engine allowed to know Anthropic's
specific wire format — see docs/engine/02-MODEL-PROVIDER.md.

Lives inside its own dedicated package, agent/adapters/anthropic/, not
a single flat file — matching Hermes's own real pattern of one file per
provider adapter (anthropic_adapter.py, bedrock_adapter.py, etc. —
never merged into one shared module), but going one step further: this
package separates the REQUEST/RESPONSE logic (this file) from
ANTHROPIC-SPECIFIC KNOWLEDGE like per-model token limits (quirks.py,
alongside this file), so that knowledge has room to grow without this
file ballooning the way Hermes's single 3,284-line anthropic_adapter.py
has.

Two deliberate differences from Hermes, both documented in
docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md: (1) Hermes
keeps its adapter files flat directly in agent/, we group ours under
agent/adapters/; (2) Hermes keeps everything about one provider in ONE
file, we split "how to call the API" (this file) from "facts about
specific models" (quirks.py) inside a per-provider package. A future
second provider for this engine gets its own new package here too,
e.g. agent/adapters/openai/ — zero changes to model_provider.py or to
this package when that happens.
"""

from __future__ import annotations

from typing import Iterator

from agent.adapters.anthropic.quirks import get_default_max_tokens
from agent.model_provider import (
    Message,
    ModelResponse,
    ProviderInvariantError,
    StreamEvent,
)
from agent.retry import call_with_retry


class AnthropicProvider:
    """Satisfies the ModelProvider Protocol structurally (see
    model_provider.py) — note there is no
    `class AnthropicProvider(ModelProvider):` inheritance; having the
    right methods is enough.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        max_tokens: int | None = None,
    ):
        """
        max_tokens: if omitted (None), uses a safe default that works
        for BOTH chat() and stream() (agent/adapters/anthropic/quirks.py
        get_default_max_tokens) rather than a single hardcoded number —
        see docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md
        category C for why this exists. This default is deliberately
        NOT the model's full real output capacity: the Anthropic SDK
        refuses a non-streaming chat() call above ~21_333 tokens (its
        own 10-minute-timeout safety rail), so the default stays under
        that ceiling. Pass an explicit larger value (up to
        quirks.get_max_output_tokens(model)) only when you know you're
        using stream(), which has no such restriction.
        """
        # Imported here, not at module level, so model_provider.py's
        # generic pieces (and anything that imports from it) stay usable
        # even in a context where the anthropic package isn't installed.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = (
            max_tokens if max_tokens is not None else get_default_max_tokens(model)
        )

    def chat(
        self, messages: list[Message], system: str, tools: list[dict]
    ) -> ModelResponse:
        """Send a full request, get one complete response back.

        Translates our engine's vendor-agnostic Message/tools shape
        into Anthropic's exact wire format, sends it, and translates
        the real response back into our engine's ModelResponse shape.

        Wrapped in call_with_retry (agent/retry.py): a retryable
        failure (rate limit, server error, timeout, context overflow)
        is retried with jittered backoff automatically, up to
        DEFAULT_MAX_RETRIES times, rather than failing outright on the
        first transient error — see
        docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md
        category E for why this was a real gap before.
        """

        def _do_chat() -> ModelResponse:
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

            # The SDK types stop_reason as Optional — None only happens
            # on an incomplete/streaming-in-progress response, which
            # this non-streaming call should never produce. We fail
            # loudly with a clear message rather than let a None
            # silently violate our own ModelResponse.stop_reason
            # contract (which requires one of the 7 real values, never
            # None) or crash with a cryptic dataclass type error two
            # layers away from the real cause.
            if response.stop_reason is None:
                raise ProviderInvariantError(
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

        return call_with_retry(_do_chat)

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

        Retry is scoped more carefully here than in chat(): we only
        retry a failure that happens BEFORE any event has reached the
        caller (opening the connection, or the very first chunk
        erroring). Once real text has already been yielded, retrying
        would mean the caller sees the same words twice — far worse
        than surfacing the error and letting the caller decide what to
        do, so from that point on a failure is raised as-is, never
        retried silently. Verified against the real SDK
        (anthropic.MessageStreamManager.__enter__): calling
        .stream(...) itself is lazy and never touches the network —
        the actual HTTP connection happens on __enter__, so retry must
        wrap THAT call, not the .stream(...) call itself.
        """
        anthropic_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]
        yielded_anything = False

        stream_manager = self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=anthropic_messages,
            tools=tools,
        )

        def _enter():
            return stream_manager.__enter__()

        stream = call_with_retry(_enter)
        try:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yielded_anything = True
                    yield StreamEvent(type="text_delta", data=event.delta.text)
                elif event.type == "message_stop":
                    final = stream.get_final_message()
                    if final.stop_reason is None:
                        raise ProviderInvariantError(
                            "Anthropic API returned stop_reason=None at "
                            "the end of a completed stream — this should "
                            "be impossible; treat as a provider-side "
                            "anomaly, not a retryable error."
                        )
                    yielded_anything = True
                    yield StreamEvent(
                        type="message_stop",
                        data=ModelResponse(
                            content=final.content,
                            stop_reason=final.stop_reason,
                            input_tokens=final.usage.input_tokens,
                            output_tokens=final.usage.output_tokens,
                        ),
                    )
        except Exception:
            # yielded_anything isn't actually usable for a different
            # decision here (chat()-style "retry before, raise after"
            # already happened above — iteration failures past the
            # first event are never retried, by construction, since
            # we only retried entering the stream, never the iteration
            # itself). Re-raised as-is either way; kept explicit so a
            # future reader doesn't wonder why iteration isn't wrapped
            # in call_with_retry too.
            raise
        finally:
            stream_manager.__exit__(None, None, None)
