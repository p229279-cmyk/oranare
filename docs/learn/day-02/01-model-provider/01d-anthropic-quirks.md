# Day 2, Component 1d — Anthropic Quirks (agent/adapters/anthropic/quirks.py)

This is the dedicated home for facts specific to individual Claude
models — the "category C" piece from `01c-ornare-vs-hermes.md`. See
that file first for the full Hermes-comparison reasoning; this doc
covers the component itself, same fixed teaching order as every other
component in this folder.

## Whole

`quirks.py` is the one file in the engine that knows facts like "how
many output tokens can THIS specific Claude model actually produce."
Nothing else in the engine should ever need to know this — not the
Agent Loop, not `provider.py`'s request/response logic — they just ask
this file for a number and use it.

In one sentence: **`quirks.py` is where "Anthropic model X is different
from Anthropic model Y" lives, so nowhere else has to care.**

## Boundaries

What's INSIDE this component's responsibility:
- Mapping a Claude model name to its real maximum output token limit.
- Deciding a SAFE value to fall back to when a model isn't recognized.
- Deciding a SAFE DEFAULT that works for both `chat()` and `stream()`
  out of the box, accounting for a real constraint the Anthropic SDK
  itself enforces (see "Deeper levels" below).

What's OUTSIDE this component's responsibility (owned elsewhere):
- Actually making the API call — that's `provider.py`.
- Deciding whether a call should be retried after a failure — that's
  `classify_error()` in `model_provider.py` (and the retry logic itself,
  not yet built — category E).
- Anything about a NON-Claude model — if we ever add a second provider,
  it gets its OWN `quirks.py` inside its OWN adapter package, never
  added here.

## Parts

Two real table-driven functions, plus the data they read from:

- **`ANTHROPIC_MAX_OUTPUT_TOKENS`** — a dictionary mapping model name →
  real max output tokens, covering the full Claude lineup (Fable,
  Sonnet 5, Opus 4.x, Sonnet 4.x, Haiku 4.5, Claude 4, Claude 3.7,
  Claude 3.5, Claude 3).
- **`get_max_output_tokens(model)`** — looks up a model's TRUE
  capability. Used when a caller knowingly wants the model's full real
  limit (only safe for `stream()`, see below).
- **`get_default_max_tokens(model)`** — the value `AnthropicProvider`
  actually uses when nothing explicit is passed. Safe for BOTH
  `chat()` and `stream()`.

## Relationships

```
AnthropicProvider.__init__  --calls-->  get_default_max_tokens(model)  --reads-->  ANTHROPIC_MAX_OUTPUT_TOKENS
AnthropicProvider (caller who wants more, for stream())  --calls-->  get_max_output_tokens(model)  --reads-->  ANTHROPIC_MAX_OUTPUT_TOKENS
```

`provider.py` is the only real caller of this file today. It never
reads `ANTHROPIC_MAX_OUTPUT_TOKENS` directly — always through one of
the two functions, so the table's exact shape (and any future columns
added to it) stays this file's own concern.

## Mechanisms

Two real mechanisms:

1. **Exact-match lookup, with a safe fallback.** `get_max_output_tokens`
   checks the dictionary for the EXACT model name given. If it's not
   there (a typo, or a brand-new model not yet added), it returns a
   conservative, known-safe number (4,096) rather than guessing high.
2. **Capping the default below an SDK-enforced ceiling.**
   `get_default_max_tokens` takes the model's real limit AND a second,
   separate ceiling (20,000) — a number that has nothing to do with the
   model's capability and everything to do with a rule the Anthropic
   SDK itself enforces — and returns whichever is SMALLER.

## Underlying principles

- **"A model's maximum capability and a safe default are two different
  numbers, and conflating them is a real bug, not a simplification."**
  This is the single most important idea in this file, and it's the one
  this component was ACTUALLY caught making a mistake on — see "Deeper
  levels" below for exactly what happened.
- **"When in doubt, fail safely visible, not silently broken."** The
  fallback for an unrecognized model is LOW (4,096), not high — using a
  smaller limit than necessary just slightly under-uses capacity (safe,
  visible if it matters); guessing high risks a hard API error.
- **"Give the engine access to the real range of options, not a
  narrowed-down guess of what we think we'll need."** The table covers
  every real Claude model family Anthropic offers, not just the 2
  models this project happens to call today — a deliberate choice, since
  Hermes has already done the real research on these per-model values
  and narrowing the list down would just mean re-adding entries later
  for no real benefit.

## Deeper levels — the bug this file actually caused, and how it was found

This is worth walking through in full, because it's a real example of
"assumed vs. verified" costing something concrete, caught only because
a LIVE call was made instead of trusting the logic on paper.

**What happened:** the first version of this file had only
`get_max_output_tokens()`, and `AnthropicProvider.__init__` used it
directly as the default. On paper this looked correct — "use the
model's real limit instead of a made-up number" sounds like a strict
improvement over the old hardcoded `4096`.

**What a real, live API call revealed:** using `claude-sonnet-4-5`'s
real limit (64,000) as the default broke EVERY non-streaming `chat()`
call outright, with this exact error from Anthropic's own SDK:

```
ValueError: Streaming is required for operations that may take longer
than 10 minutes.
```

**Why this happens — the real mechanism, read from the SDK's own
source** (`anthropic.Anthropic._calculate_nonstreaming_timeout`):

```python
def _calculate_nonstreaming_timeout(self, max_tokens, max_nonstreaming_tokens):
    maximum_time = 60 * 60
    default_time = 60 * 10
    expected_time = maximum_time * max_tokens / 128_000
    if expected_time > default_time or (...):
        raise ValueError("Streaming is required for operations that may take longer than 10 minutes. ...")
```

In plain words: the SDK estimates how long a non-streaming call MIGHT
take based on how many tokens you're asking for, and if that estimate
crosses 10 minutes, it refuses to even try — because a non-streaming
call gives you nothing until it's completely done, and the SDK doesn't
want you silently hanging for a long time with zero feedback. Doing the
math: `3600 * max_tokens / 128_000 > 600` solves to `max_tokens >
~21,333`. Our new "correct" default of 64,000 was almost 3x over that
line.

**The fix — two different numbers for two different questions:**

| Question being asked | Function | What it returns |
|---|---|---|
| "What can this model theoretically produce?" | `get_max_output_tokens(model)` | The model's TRUE capability (e.g. 64,000 for Sonnet 4.5) |
| "What should `AnthropicProvider` actually default to?" | `get_default_max_tokens(model)` | `min(model's real limit, 20,000)` — safe for `chat()` AND `stream()` |

A caller who deliberately wants the model's full real capacity for a
long STREAMED answer can still get it — by explicitly passing
`max_tokens=get_max_output_tokens(model)` to `AnthropicProvider`. The
DEFAULT just never silently picks a value that breaks the common case.

**The one-sentence rule underneath this whole section:** *a model's
real capability is a FACT about the model; a safe default is a DECISION
about how this code should behave by default — never assume they're the
same number just because one of them is easy to look up.*

## Coding

Built in `agent/adapters/anthropic/quirks.py`, in this order:

1. `ANTHROPIC_MAX_OUTPUT_TOKENS` — the table itself, originally scoped
   to just our 2 models, later expanded to the full Claude lineup.
2. `get_max_output_tokens(model)` — the lookup function, with a safe
   fallback for unrecognized models.
3. `get_default_max_tokens(model)` — added AFTER the live-call bug was
   found, capping the default below the SDK's real non-streaming
   ceiling.
4. `AnthropicProvider.__init__` wired to call `get_default_max_tokens`
   when `max_tokens` isn't given explicitly.

## Code understanding

Full function-by-function explanation lives in
[`01d-anthropic-quirks-code-explaination.md`](01d-anthropic-quirks-code-explaination.md).
