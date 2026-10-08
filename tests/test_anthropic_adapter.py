"""
tests/test_anthropic_adapter.py

Tests for agent/anthropic_adapter.py's AnthropicProvider — see
docs/learn/day-02/01-model-provider.md Steps 4 and 5.

Honesty note, per the project's standing testing standard: most of these
tests use a mocked SDK client, not a real network call, to prove the
TRANSLATION logic (our Message/tools shapes -> Anthropic's wire format,
and Anthropic's response -> our ModelResponse/StreamEvent shapes) is
correct. Both chat() and stream() were ALSO verified with one real live
call each against the actual Anthropic API (cheap model, Haiku) during
development — see the Day 2 commit history for that verification; the
key itself was never written to any file in this repo.
"""

from unittest.mock import MagicMock, patch

from agent.anthropic_adapter import AnthropicProvider
from agent.model_provider import Message


def _fake_anthropic_response(
    stop_reason: str | None = "end_turn", input_tokens=10, output_tokens=5
):
    """Builds a MagicMock shaped like a real anthropic.types.Message —
    enough attributes for AnthropicProvider.chat() to read from."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text="hello back")]
    response.stop_reason = stop_reason
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def test_chat_translates_our_messages_into_anthropic_wire_format():
    """Proves the request-side translation: our Message objects become
    the exact dict shape messages.create() expects."""
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _fake_anthropic_response()
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        provider.chat(
            messages=[Message(role="user", content="hi")],
            system="be helpful",
            tools=[],
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
        assert call_kwargs["system"] == "be helpful"
        assert call_kwargs["tools"] == []


def test_chat_translates_anthropic_response_into_our_model_response():
    """Proves the response-side translation: Anthropic's response shape
    becomes our engine's ModelResponse shape correctly."""
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _fake_anthropic_response(
            stop_reason="tool_use", input_tokens=42, output_tokens=17
        )
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        result = provider.chat(
            messages=[Message(role="user", content="hi")],
            system="be helpful",
            tools=[],
        )

        assert result.stop_reason == "tool_use"
        assert result.input_tokens == 42
        assert result.output_tokens == 17


def test_chat_raises_loudly_on_impossible_none_stop_reason():
    """Proves our defensive check actually fires — a None stop_reason
    (which the SDK's own type allows but a non-streaming call should
    never produce) must raise clearly, not silently violate our
    ModelResponse contract or crash with a confusing error two layers
    away from the real cause."""
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _fake_anthropic_response(
            stop_reason=None
        )
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        try:
            provider.chat(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
            assert False, "expected ValueError to be raised"
        except ValueError as e:
            assert "stop_reason=None" in str(e)


def _fake_stream_context_manager(events, final_message):
    """Builds a MagicMock shaped like the real SDK's
    MessageStreamManager: usable as `with client.messages.stream(...) as
    stream:`, iterable (yields the given fake events), and supports
    get_final_message()."""
    stream_obj = MagicMock()
    stream_obj.__iter__.return_value = iter(events)
    stream_obj.get_final_message.return_value = final_message

    context_manager = MagicMock()
    context_manager.__enter__.return_value = stream_obj
    context_manager.__exit__.return_value = False
    return context_manager


def _fake_text_delta_event(text):
    event = MagicMock()
    event.type = "content_block_delta"
    event.delta.type = "text_delta"
    event.delta.text = text
    return event


def _fake_message_stop_event():
    event = MagicMock()
    event.type = "message_stop"
    return event


def test_stream_yields_text_delta_events_as_they_arrive():
    """Proves stream() translates the SDK's raw content_block_delta
    events into our engine's StreamEvent("text_delta", ...) shape, one
    per chunk of text — the whole point of streaming over chat()."""
    events = [_fake_text_delta_event("Hel"), _fake_text_delta_event("lo")]
    final_message = _fake_anthropic_response(stop_reason="end_turn")

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = _fake_stream_context_manager(
            events + [_fake_message_stop_event()], final_message
        )
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        results = list(
            provider.stream(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
        )

        text_events = [r for r in results if r.type == "text_delta"]
        assert [e.data for e in text_events] == ["Hel", "lo"]


def test_stream_yields_final_model_response_on_message_stop():
    """Proves stream() yields a final StreamEvent("message_stop", ...)
    carrying a complete ModelResponse — built from get_final_message(),
    the same way chat() builds one — once the stream ends."""
    final_message = _fake_anthropic_response(
        stop_reason="tool_use", input_tokens=30, output_tokens=12
    )

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = _fake_stream_context_manager(
            [_fake_message_stop_event()], final_message
        )
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        results = list(
            provider.stream(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
        )

        stop_events = [r for r in results if r.type == "message_stop"]
        assert len(stop_events) == 1
        final_response = stop_events[0].data
        assert final_response.stop_reason == "tool_use"
        assert final_response.input_tokens == 30
        assert final_response.output_tokens == 12


def test_stream_raises_loudly_on_impossible_none_stop_reason():
    """Same defensive guard as chat(), applied at the end of a stream:
    a None stop_reason on the final message must raise clearly."""
    final_message = _fake_anthropic_response(stop_reason=None)

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = _fake_stream_context_manager(
            [_fake_message_stop_event()], final_message
        )
        mock_anthropic_cls.return_value = mock_client

        provider = AnthropicProvider(api_key="fake-key-for-mocked-test")
        try:
            list(
                provider.stream(
                    messages=[Message(role="user", content="hi")],
                    system="be helpful",
                    tools=[],
                )
            )
            assert False, "expected ValueError to be raised"
        except ValueError as e:
            assert "stop_reason=None" in str(e)
