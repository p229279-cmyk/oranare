"""
tests/test_openai_adapter.py

Tests for agent/adapters/openai/provider.py's OpenAIProvider - see
docs/learn/day-02/01-model-provider/ for the ModelProvider teaching
walkthrough (this adapter follows the exact same pattern as
AnthropicProvider).

Honesty note, per the project's standing testing standard: most of
these tests use a mocked SDK client, not a real network call, to
prove the TRANSLATION logic is correct. Both chat() and stream() were
ALSO verified with one real live call each against the actual OpenAI
API (gpt-5.6-luna) during development - see the Day 2 commit history;
the key itself was never written to any file in this repo.
"""

from unittest.mock import MagicMock, patch

from agent.adapters.openai.provider import OpenAIProvider
from agent.model_provider import Message, ProviderInvariantError


def _fake_openai_response(finish_reason="stop", prompt_tokens=10, completion_tokens=5):
    """Builds a MagicMock shaped like a real openai ChatCompletion -
    enough attributes for OpenAIProvider.chat() to read from."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "hello back"
    response.choices[0].finish_reason = finish_reason
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


def test_max_tokens_defaults_to_the_models_real_limit():
    """Unlike AnthropicProvider, OpenAI has no non-streaming-timeout
    restriction (verified against the real SDK) - so the default here
    is simply the model's real capability, not a capped-down value."""
    with patch("openai.OpenAI"):
        provider = OpenAIProvider(
            api_key="fake-key-for-mocked-test", model="gpt-5.6-luna"
        )
        assert provider._max_tokens == 128_000


def test_max_tokens_explicit_value_is_respected():
    with patch("openai.OpenAI"):
        provider = OpenAIProvider(
            api_key="fake-key-for-mocked-test",
            model="gpt-5.6-luna",
            max_tokens=100,
        )
        assert provider._max_tokens == 100


def test_chat_uses_max_completion_tokens_not_the_legacy_max_tokens_param():
    """Regression test for a real bug caught via a live API call:
    gpt-5.6 (and other current/reasoning-family models) reject the
    legacy max_tokens parameter outright with a 400
    ('Unsupported parameter: max_tokens is not supported with this
    model. Use max_completion_tokens instead.'). Verified against the
    real API, not assumed - see the Day 2 commit history."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_openai_response()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test", max_tokens=50)
        provider.chat(
            messages=[Message(role="user", content="hi")],
            system="be helpful",
            tools=[],
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_completion_tokens"] == 50
        assert "max_tokens" not in call_kwargs


def test_chat_prepends_system_as_a_message_not_a_separate_param():
    """OpenAI's Chat Completions API has no top-level `system`
    parameter (unlike Anthropic) - the system prompt must be the
    first message in the list, with role="system". Verified against
    the real SDK's create() signature, not assumed."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_openai_response()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        provider.chat(
            messages=[Message(role="user", content="hi")],
            system="be helpful",
            tools=[],
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"][0] == {"role": "system", "content": "be helpful"}
        assert call_kwargs["messages"][1] == {"role": "user", "content": "hi"}


def test_chat_translates_openai_response_into_our_model_response():
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            finish_reason="stop", prompt_tokens=42, completion_tokens=7
        )
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        result = provider.chat(
            messages=[Message(role="user", content="hi")],
            system="be helpful",
            tools=[],
        )

        assert result.content == "hello back"
        assert result.stop_reason == "end_turn"
        assert result.input_tokens == 42
        assert result.output_tokens == 7


def test_chat_maps_tool_calls_finish_reason_to_tool_use():
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            finish_reason="tool_calls"
        )
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        result = provider.chat(
            messages=[Message(role="user", content="hi")], system="be helpful", tools=[]
        )
        assert result.stop_reason == "tool_use"


def test_chat_raises_loudly_on_unrecognized_finish_reason():
    """Proves the fail-loud discipline carries over from the Anthropic
    adapter: an unrecognized finish_reason must not silently pass
    through our ModelResponse.stop_reason contract."""
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_openai_response(
            finish_reason="some_future_value_we_dont_know_about"
        )
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        try:
            provider.chat(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
            assert False, "expected ProviderInvariantError to be raised"
        except ProviderInvariantError as e:
            assert "finish_reason" in str(e)


def test_chat_raises_loudly_on_missing_usage():
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        response = _fake_openai_response()
        response.usage = None
        mock_client.chat.completions.create.return_value = response
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        try:
            provider.chat(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
            assert False, "expected ProviderInvariantError to be raised"
        except ProviderInvariantError as e:
            assert "usage" in str(e)


def test_stream_yields_text_delta_events_as_they_arrive():
    def _fake_chunks():
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk2.choices[0].finish_reason = "stop"
        chunk2.usage = None

        # Final usage-only chunk (stream_options={"include_usage": True})
        final = MagicMock()
        final.choices = []
        final.usage = MagicMock()
        final.usage.prompt_tokens = 10
        final.usage.completion_tokens = 2

        return iter([chunk1, chunk2, final])

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_chunks()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(api_key="fake-key-for-mocked-test")
        events = list(
            provider.stream(
                messages=[Message(role="user", content="hi")],
                system="be helpful",
                tools=[],
            )
        )

        text_events = [e for e in events if e.type == "text_delta"]
        assert [e.data for e in text_events] == ["Hello", " world"]

        final_events = [e for e in events if e.type == "message_stop"]
        assert len(final_events) == 1
        assert final_events[0].data.stop_reason == "end_turn"
        assert final_events[0].data.input_tokens == 10
        assert final_events[0].data.output_tokens == 2
