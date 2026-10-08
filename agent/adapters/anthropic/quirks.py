"""
agent/adapters/anthropic/quirks.py

Facts specific to individual Claude models — things that differ model
by model, that the rest of the engine should never have to know or
care about. See docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md
"Part 2, category C" for the full reasoning behind why this file
exists and why it's scoped the way it is.

This is a SMALL, SCOPED version of what Hermes's real
agent/anthropic_adapter.py does with its _ANTHROPIC_OUTPUT_LIMITS table
and _get_anthropic_max_output() function — same idea (a table + a
lookup function), but covering only the handful of models we ourselves
actually use, not Hermes's full cross-vendor, many-model-family table.

As more model-specific facts become relevant to us (e.g. whether a
model supports extended "thinking" mode, or a specific effort level),
they belong in THIS file too — this package (agent/adapters/anthropic/)
is the deliberate, scoped home for all such Anthropic-specific
knowledge, kept separate from provider.py's request/response logic so
neither file has to grow to accommodate the other's concerns.
"""

from __future__ import annotations

# Real max output token limits for the specific Claude models we
# ourselves actually use, confirmed against Anthropic's own current
# documentation and cross-checked against Hermes's own real table
# (/home/ubuntu/.hermes/hermes-agent/agent/anthropic_adapter.py,
# _ANTHROPIC_OUTPUT_LIMITS) rather than guessed.
#
# Deliberately NOT Hermes's full table: we don't carry entries for
# model families we don't use (Opus, older Claude 3.x generations,
# third-party Anthropic-compatible endpoints like MiniMax/Qwen) —
# adding those now would be speculative, matching the project's
# standing YAGNI discipline.
ANTHROPIC_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "claude-sonnet-4-5": 64_000,
    "claude-haiku-4-5": 64_000,
}

# If we're ever given a model name not in the table above (e.g. a
# typo, or a brand-new model we haven't added yet), fall back to a
# SAFE, CONSERVATIVE default rather than guessing high. Guessing high
# risks an API error if the real model's limit is lower; guessing low
# only risks under-using capacity, which is safe and visible rather
# than a hard failure. 4096 matches the oldest, lowest real Claude 3.x
# limit Hermes's own table carries, so it is a value we know some real
# Claude model genuinely supports.
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
    Hermes needs substring matching because it has to handle
    date-stamped model IDs (claude-sonnet-4-5-20250929) and variant
    suffixes (:1m, :fast) across many model families. Our own model
    names don't currently include either of those, so an exact-match
    lookup is honest and sufficient — this function should be upgraded
    to substring matching the moment we actually pass a model name in
    one of those shapes, not before.
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
