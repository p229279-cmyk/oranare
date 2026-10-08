"""
tests/test_anthropic_quirks.py

Tests for agent/adapters/anthropic/quirks.py — see
docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md category C.
"""

from agent.adapters.anthropic.quirks import (
    ANTHROPIC_MAX_OUTPUT_TOKENS,
    get_default_max_tokens,
    get_max_output_tokens,
)


def test_known_models_return_their_real_limit():
    assert get_max_output_tokens("claude-sonnet-4-5") == 64_000
    assert get_max_output_tokens("claude-haiku-4-5") == 64_000
    assert get_max_output_tokens("claude-opus-4-5") == 64_000
    assert get_max_output_tokens("claude-opus-4-6") == 128_000
    assert get_max_output_tokens("claude-sonnet-5") == 128_000
    assert get_max_output_tokens("claude-fable") == 128_000
    assert get_max_output_tokens("claude-3-5-sonnet") == 8_192
    assert get_max_output_tokens("claude-3-opus") == 4_096


def test_unknown_model_falls_back_to_safe_conservative_default():
    """A typo or a brand-new model we haven't added yet must not guess
    high and risk an API error — it should fall back to a value we
    know some real Claude model genuinely supports."""
    result = get_max_output_tokens("claude-some-future-model-we-dont-know-yet")
    assert result == 4_096
    # The default must never exceed the smallest real limit we track -
    # otherwise "safe" wouldn't actually be safe.
    assert result <= min(ANTHROPIC_MAX_OUTPUT_TOKENS.values())


def test_table_covers_the_full_claude_lineup_not_just_our_own_models():
    """Per explicit instruction: this table gives access to every real
    Claude model family (Fable, Sonnet 5, Opus 4.x, Sonnet 4.x, Haiku
    4.5, Claude 4, Claude 3.7, Claude 3.5, Claude 3) - not narrowed
    down to only the specific models this project currently calls."""
    expected_families = {
        "claude-fable", "claude-sonnet-5",
        "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6",
        "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
        "claude-opus-4", "claude-sonnet-4",
        "claude-3-7-sonnet",
        "claude-3-5-sonnet", "claude-3-5-haiku",
        "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    }
    assert set(ANTHROPIC_MAX_OUTPUT_TOKENS.keys()) == expected_families


def test_default_max_tokens_stays_under_the_nonstreaming_safe_ceiling():
    """Regression test for a real bug caught via a live API call: using
    get_max_output_tokens()'s raw 64_000 as AnthropicProvider's default
    broke every non-streaming chat() call, because the Anthropic SDK
    itself refuses max_tokens values large enough to risk a >10-minute
    response (its own _calculate_nonstreaming_timeout check). The
    DEFAULT must stay safely under that boundary even though the
    model's true capability is higher."""
    default = get_default_max_tokens("claude-sonnet-4-5")
    assert default < 21_333  # the SDK's real computed threshold
    assert default == 20_000


def test_default_max_tokens_never_exceeds_the_models_real_capability():
    """For a model whose real limit is SMALLER than our non-streaming
    ceiling, the default must respect the model's own real limit, not
    just the ceiling — now directly testable since the table includes
    older Claude 3.x models with genuinely lower real limits."""
    assert get_default_max_tokens("claude-haiku-4-5") <= get_max_output_tokens(
        "claude-haiku-4-5"
    )
    # claude-3-opus's real limit (4_096) is BELOW the 20_000 ceiling -
    # the default must be the model's real limit, not the ceiling.
    assert get_default_max_tokens("claude-3-opus") == 4_096
