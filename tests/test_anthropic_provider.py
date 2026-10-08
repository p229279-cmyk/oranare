"""
tests/test_anthropic_provider.py

Tests for agent/model_provider.py's AnthropicProvider — see
docs/learn/day-02/01-model-provider.md Step 4.

Honesty note, per the project's standing testing standard: there is NO
live ANTHROPIC_API_KEY in this environment. These tests prove the
TRANSLATION logic (our Message/tools shapes -> Anthropic's wire format,
and Anthropic's response -> our ModelResponse shape) is correct, using a
mocked SDK client — not a real network call. What remains genuinely
UNVERIFIED without a live key: that a real Anthropic API response
actually has the exact shape we're assuming (we verified this against
the SDK's own type definitions in model_provider.py's comments, but a
live call is the only way to see a REAL response, not just the type
contract).
"""

from unittest.mock import MagicMock, patch

from agent.model_provider import AnthropicProvider, Message


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
