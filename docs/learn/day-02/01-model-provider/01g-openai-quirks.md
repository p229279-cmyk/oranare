# Day 2, Component 1g — OpenAI Quirks (agent/adapters/openai/quirks.py)

This is the OpenAI equivalent of `01d-anthropic-quirks.md`, same "category C" idea applied to the second vendor. Same fixed teaching order.

## Whole

`quirks.py` is the one file in the OpenAI adapter package that knows facts like "how many output tokens can THIS specific OpenAI model actually produce." Nothing else — not `provider.py`, not the loop — needs to know this; they just ask this file for a number.

## Boundaries

INSIDE this component: mapping an OpenAI model name to its real max output token limit, and deciding a safe fallback for an unrecognized model.

OUTSIDE this component: actually making the API call (`provider.py`), deciding whether a FAILED call should be retried (`classify_error()` in `model_provider.py`, shared with Anthropic unchanged), anything about a non-OpenAI model (Anthropic's `quirks.py` is a separate, unrelated file).

## Parts

- **`OPENAI_MAX_OUTPUT_TOKENS`** — a dictionary of real per-model limits: `gpt-5.6-sol`/`gpt-5.6-terra`/`gpt-5.6-luna`/`gpt-5.6` (the alias) all at 128,000; `gpt-4o` and `gpt-4o-mini` at 16,384; `gpt-4-turbo` at 4,096.
- **`get_max_output_tokens(model)`** — the lookup, with a safe low fallback (4,096) for an unrecognized model name.
- **`get_default_max_tokens(model)`** — what `OpenAIProvider` actually defaults to when `max_tokens` isn't given explicitly.

## Relationships

```
OpenAIProvider.__init__  --calls-->  get_default_max_tokens(model)  --reads-->  OPENAI_MAX_OUTPUT_TOKENS
```

Exactly one real caller today, same as the Anthropic equivalent's relationship to its own `provider.py`.

## Mechanisms

Same two mechanisms as the Anthropic version: an exact-match dictionary lookup with a safe fallback, and a second function that decides what the DEFAULT should actually be (as opposed to the model's raw theoretical capability).

## Underlying principles

- **"Mirror a working pattern exactly when the underlying problem is the same shape — don't invent a new structure just because the vendor changed."** This file's shape is a direct, deliberate copy of `anthropic/quirks.py`'s shape, because the problem being solved ("look up a real per-model fact, with a safe fallback") is identical in both cases. The only thing that's actually different is the real numbers inside the table and one real mechanical detail (see below).
- **"Don't assume a quirk discovered for one vendor applies to a different vendor — verify each one independently."** Anthropic's adapter needed a SEPARATE `get_default_max_tokens` ceiling because Anthropic's SDK has a real non-streaming-timeout restriction. It would have been easy — and WRONG — to assume OpenAI's SDK has the exact same restriction just because it solves a similar-looking problem. It was checked directly against the installed OpenAI SDK's source, found to have no such restriction, and the function was written to reflect that real finding, not an assumption carried over from the other vendor.

## Deeper levels — the one real difference from the Anthropic version, and how it was confirmed, not assumed

This is worth calling out explicitly, because getting it wrong in either direction would be a real, if quiet, bug:

**The question:** does OpenAI's Python SDK, like Anthropic's, refuse a non-streaming call when `max_tokens` is set high enough that the response could plausibly take a long time to generate?

**How this was actually checked, not guessed:**

```python
import inspect, openai
src = inspect.getsource(openai.OpenAI)
print('_calculate_nonstreaming' in src)
# -> raised OSError: could not find class definition (openai.OpenAI
#    is itself a thin re-export; had to inspect differently)

print([m for m in dir(openai.OpenAI) if 'timeout' in m.lower() or 'stream' in m.lower()])
# -> ['_calculate_retry_timeout', '_default_stream_cls',
#     '_should_stream_response_body', 'with_streaming_response']
# No '_calculate_nonstreaming_timeout' equivalent exists.
```

And then confirmed with a REAL live call: `OpenAIProvider.chat()` was called against the real API using the model's full real limit (128,000 for `gpt-5.6-luna`) as `max_tokens`, with NO separate ceiling applied — and it succeeded. If OpenAI's SDK had the same restriction Anthropic's does, that exact call would have failed the same way the Anthropic one did before its fix.

**The conclusion, and why `get_default_max_tokens` looks the way it does:**

```python
def get_default_max_tokens(model: str) -> int:
    """... Kept as its own function anyway, matching the Anthropic
    adapter's shape, so a future real OpenAI-side restriction (if one
    appears) has an obvious place to be added..."""
    return get_max_output_tokens(model)
```

It's just a pass-through today — no separate ceiling, because none was found to exist. But it's still its OWN function, not simply calling `get_max_output_tokens` directly from `provider.py`. **Why keep a function that currently does nothing extra?** Because if OpenAI ever DOES introduce a similar restriction later (vendors change their APIs over time), there's already an obvious, named place for that logic to go, without having to go back and restructure `provider.py` itself — the same shape-first discipline used throughout this project.

**The one-sentence rule underneath this section:** *a vendor-specific quirk discovered for one provider is a hypothesis about that ONE provider, not a general fact about "how model APIs work" — every provider's real behavior gets checked independently, never assumed by analogy.*

## Coding

Built in this order: `OPENAI_MAX_OUTPUT_TOKENS` (the table, real values from current OpenAI documentation) → `get_max_output_tokens()` → checked the SDK directly for a non-streaming restriction (none found) → `get_default_max_tokens()` written as a pass-through, with the reasoning for why it's still its own function documented directly in its docstring.

## Code understanding

Full function-by-function explanation lives in [`01g-openai-quirks-code-explaination.md`](01g-openai-quirks-code-explaination.md).
