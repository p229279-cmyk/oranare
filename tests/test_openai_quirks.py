"""
tests/test_openai_quirks.py

Tests for agent/adapters/openai/quirks.py - mirrors
tests/test_anthropic_quirks.py's structure for the OpenAI equivalent.
"""

from agent.adapters.openai.quirks import (
    OPENAI_MAX_OUTPUT_TOKENS,
    get_default_max_tokens,
    get_max_output_tokens,
)


def test_known_models_return_their_real_limit():
    assert get_max_output_tokens("gpt-5.6-luna") == 128_000
    assert get_max_output_tokens("gpt-5.6-sol") == 128_000
    assert get_max_output_tokens("gpt-4o") == 16_384
    assert get_max_output_tokens("gpt-4o-mini") == 16_384
    assert get_max_output_tokens("gpt-4-turbo") == 4_096


def test_unknown_model_falls_back_to_safe_conservative_default():
    result = get_max_output_tokens("gpt-some-future-model-we-dont-know-yet")
    assert result == 4_096
    assert result <= min(OPENAI_MAX_OUTPUT_TOKENS.values())


def test_default_max_tokens_equals_real_limit_no_separate_ceiling():
    """Unlike Anthropic's get_default_max_tokens, OpenAI's SDK has no
    non-streaming-timeout restriction (verified directly against the
    installed SDK, not assumed) - so the default here is simply the
    model's real capability."""
    assert get_default_max_tokens("gpt-4-turbo") == get_max_output_tokens(
        "gpt-4-turbo"
    )
    assert get_default_max_tokens("gpt-5.6-luna") == 128_000
