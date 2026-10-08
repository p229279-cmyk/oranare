"""
agent/adapters/anthropic/quirks.py

Facts specific to individual Claude models — things that differ model
by model, that the rest of the engine should never have to know or
care about. See docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md
"Part 2, category C" for the full reasoning behind why this file
exists.

UPDATED per explicit instruction: this table covers ALL real Claude
model families (Fable, Sonnet 5, Opus 4.x, Sonnet 4.x, Haiku 4.5,
Claude 4, Claude 3.7, Claude 3.5, Claude 3), not just the specific
models we currently call — give the engine access to every model
Anthropic actually offers, not a narrowed-down list. This mirrors
Hermes's real _ANTHROPIC_OUTPUT_LIMITS table
(/home/ubuntu/.hermes/hermes-agent/agent/anthropic_adapter.py) closely,
intentionally: real per-model values, cross-checked against Hermes's
own table rather than guessed, since Hermes has already done the real
research here. The one deliberate omission: Hermes's third-party
Anthropic-COMPATIBLE entries (minimax, qwen3) are NOT carried, because
those aren't Claude models at all — they're a different vendor's API
that happens to speak Anthropic's wire format (category B, which this
project does not need — see 01c-ornare-vs-hermes.md).

As more model-specific facts become relevant (e.g. whether a model
supports extended "thinking" mode, or a specific effort level), they
belong in THIS file too — this package (agent/adapters/anthropic/) is
the deliberate, scoped home for all such Anthropic-specific knowledge,
kept separate from provider.py's request/response logic so neither
file has to grow to accommodate the other's concerns.
"""

from __future__ import annotations

# Real max output token limits for every real Claude model family,
# cross-checked against Hermes's own real table
# (/home/ubuntu/.hermes/hermes-agent/agent/anthropic_adapter.py,
# _ANTHROPIC_OUTPUT_LIMITS) rather than guessed. Covers the full
# Claude lineup, not just the specific models this project currently
# calls, per explicit instruction.
ANTHROPIC_MAX_OUTPUT_TOKENS: dict[str, int] = {
    # Mythos-class named models (claude-fable-5, ...) — 1M context, reasoning
    "claude-fable": 128_000,
    # Claude Sonnet 5
    "claude-sonnet-5": 128_000,
    # Claude 4.8
    "claude-opus-4-8": 128_000,
    # Claude 4.7
    "claude-opus-4-7": 128_000,
    # Claude 4.6
    "claude-opus-4-6": 128_000,
    "claude-sonnet-4-6": 64_000,
    # Claude 4.5
    "claude-opus-4-5": 64_000,
    "claude-sonnet-4-5": 64_000,
    "claude-haiku-4-5": 64_000,
    # Claude 4
    "claude-opus-4": 32_000,
    "claude-sonnet-4": 64_000,
    # Claude 3.7
    "claude-3-7-sonnet": 128_000,
    # Claude 3.5
    "claude-3-5-sonnet": 8_192,
    "claude-3-5-haiku": 8_192,
    # Claude 3
    "claude-3-opus": 4_096,
    "claude-3-sonnet": 4_096,
    "claude-3-haiku": 4_096,
}

# If we're ever given a model name not in the table above (e.g. a
# typo, or a brand-new model we haven't added yet), fall back to a
# SAFE, CONSERVATIVE default rather than guessing high. Guessing high
# risks an API error if the real model's limit is lower; guessing low
# only risks under-using capacity, which is safe and visible rather
# than a hard failure. 4096 matches the oldest, lowest real Claude 3.x
# limit in the table above, so it is a value we know some real Claude
# model genuinely supports.
_SAFE_DEFAULT_MAX_OUTPUT_TOKENS = 4_096

# The Anthropic Python SDK refuses a NON-STREAMING call if max_tokens is
# large enough that the request could plausibly take over 10 minutes —
# verified against the SDK's own real logic
# (anthropic.Anthropic._calculate_nonstreaming_timeout): it computes
# `expected_time = 3600 * max_tokens / 128_000` and raises ValueError if
# that exceeds 600 seconds, i.e. whenever max_tokens > ~21_333. This is
# NOT a model capability limit (the model itself can genuinely produce
# more) — it's an SDK-level safety rail specific to the non-streaming
# chat() path, discovered by actually running a live call rather than
# assumed. We keep some margin below the exact threshold.
_ANTHROPIC_NONSTREAMING_SAFE_CEILING = 20_000


def get_max_output_tokens(model: str) -> int:
    """Look up the real max output token limit for a specific Claude
    model — the model's true capability, usable by a caller who
    knowingly wants to request a large value for a STREAMING call
    (stream() has no non-streaming-timeout restriction).

    Deliberately simpler than Hermes's _get_anthropic_max_output():
    Hermes needs substring matching because it also has to handle
    date-stamped model IDs (claude-sonnet-4-5-20250929) and variant
    suffixes (:1m, :fast). We carry the same real per-model VALUES as
    Hermes now, but our own model names don't currently arrive in
    either of those messier shapes, so an exact-match lookup is honest
    and sufficient — this function should be upgraded to substring
    matching the moment we actually pass a model name in one of those
    shapes, not before.
    """
    return ANTHROPIC_MAX_OUTPUT_TOKENS.get(model, _SAFE_DEFAULT_MAX_OUTPUT_TOKENS)


def get_default_max_tokens(model: str) -> int:
    """The value AnthropicProvider actually uses when max_tokens isn't
    given explicitly — safe for BOTH chat() and stream() out of the
    box, unlike get_max_output_tokens() alone.

    Returns the smaller of (a) the model's real output limit and (b)
    the non-streaming-safe ceiling discovered above. A caller who
    explicitly wants a larger value (e.g. for a long STREAMED answer)
    passes max_tokens=get_max_output_tokens(model) themselves — an
    informed, explicit choice — rather than this default silently
    picking a value that would break the common chat() case.
    """
    return min(get_max_output_tokens(model), _ANTHROPIC_NONSTREAMING_SAFE_CEILING)
