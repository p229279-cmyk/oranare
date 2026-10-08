"""
agent/adapters/openai/quirks.py

Facts specific to individual OpenAI models - things that differ model
by model, that the rest of the engine should never have to know or
care about. Mirrors agent/adapters/anthropic/quirks.py's shape
exactly (table + lookup functions), for the same reasoning - see
docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md category C.

Real per-model values verified via current OpenAI API documentation
(developers.openai.com/api/docs/models/*), not guessed:
- gpt-5.6 family (Sol/Terra/Luna): 1,050,000 context window,
  128,000 max output tokens - confirmed identical across all 3 tiers.
- gpt-4o: 128,000 context window, 16,384 max output tokens.
- gpt-4o-mini: 128,000 context window, 16,384 max output tokens.
- gpt-4-turbo: 128,000 context window, 4,096 max output tokens
  (OpenAI's own docs note this is an older model, superseded by gpt-4o).

Deliberately NOT exhaustive of every OpenAI model ever released (o1,
o3, gpt-3.5-turbo, etc.) - covers the models relevant to this
project's actual testing/use today. Add entries as real need arises,
same YAGNI discipline as the Anthropic table (which WAS later
expanded to the full lineup on explicit instruction - if the same
instruction applies here, extend this table the same way).
"""

from __future__ import annotations

OPENAI_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "gpt-5.6-sol": 128_000,
    "gpt-5.6-terra": 128_000,
    "gpt-5.6-luna": 128_000,
    "gpt-5.6": 128_000,  # alias that routes to gpt-5.6-sol
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "gpt-4-turbo": 4_096,
}

# If we're ever given a model name not in the table above, fall back
# to a SAFE, CONSERVATIVE default rather than guessing high - same
# reasoning as the Anthropic table: guessing low under-uses capacity
# (safe, visible); guessing high risks a hard API error.
_SAFE_DEFAULT_MAX_OUTPUT_TOKENS = 4_096


def get_max_output_tokens(model: str) -> int:
    """Look up the real max output token limit for a specific OpenAI
    model - the model's true capability.

    Exact-match lookup, same reasoning as the Anthropic equivalent:
    our own model names don't currently arrive with date-stamp or
    variant-suffix noise, so substring matching isn't needed yet.
    """
    return OPENAI_MAX_OUTPUT_TOKENS.get(model, _SAFE_DEFAULT_MAX_OUTPUT_TOKENS)


def get_default_max_tokens(model: str) -> int:
    """The value OpenAIProvider actually uses when max_tokens isn't
    given explicitly.

    Unlike Anthropic's adapter, this does NOT apply a separate
    non-streaming-safe ceiling: verified directly against the
    installed OpenAI Python SDK (openai==3.26.1) that it has no
    equivalent to Anthropic's _calculate_nonstreaming_timeout
    restriction - inspect.getsource() on the client find no such
    method, and no ValueError was raised using the model's full real
    limit in a live non-streaming call (see the Day 2 commit history
    for that verification). Kept as its own function anyway, matching
    the Anthropic adapter's shape, so a future real OpenAI-side
    restriction (if one appears) has an obvious place to be added
    without changing every caller.
    """
    return get_max_output_tokens(model)
