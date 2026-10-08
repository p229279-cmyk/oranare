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


def test_unknown_model_falls_back_to_safe_conservative_default():
    """A typo or a brand-new model we haven't added yet must not guess
    high and risk an API error — it should fall back to a value we
    know some real Claude model genuinely supports."""
    result = get_max_output_tokens("claude-some-future-model-we-dont-know-yet")
    assert result == 4_096
    # The default must never exceed the smallest real limit we track -
    # otherwise "safe" wouldn't actually be safe.
    assert result <= min(ANTHROPIC_MAX_OUTPUT_TOKENS.values())


def test_table_only_contains_models_we_actually_use():
    """Guards against silently growing this into Hermes's full
    many-model-family table - this project's models should be the only
    keys here per the project's YAGNI discipline (see category C)."""
    assert set(ANTHROPIC_MAX_OUTPUT_TOKENS.keys()) == {
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    }


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
    """For a hypothetical model whose real limit were SMALLER than our
    non-streaming ceiling, the default must still respect the model's
    own real limit, not just the ceiling."""
    # claude-haiku-4-5's real limit (64_000) is above the ceiling, so
    # this mainly documents the min() behavior rather than exercising
    # a model below the ceiling (we don't have one in our small table
    # today) - still a meaningful assertion on the actual function.
    assert get_default_max_tokens("claude-haiku-4-5") <= get_max_output_tokens(
        "claude-haiku-4-5"
    )
