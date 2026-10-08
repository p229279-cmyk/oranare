## 1. `ANTHROPIC_MAX_OUTPUT_TOKENS` — what it is and why

A plain dictionary mapping a model name to a number — nothing fancy. **Why we need it:** without this, the code would have no way to know how much a specific Claude model can actually produce, so it has to either guess (risky) or ask Anthropic every time (slow, unnecessary network call for a fact that basically never changes).

```python
ANTHROPIC_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "claude-opus-4-6": 128_000,
    "claude-sonnet-4-5": 64_000,
    "claude-3-opus": 4_096,
    ...
}
```

**Why it covers the WHOLE Claude lineup, not just our 2 models:** adding every real model costs nothing (it's just more dictionary entries) and means we never have to come back and add a new line the day we decide to use a different model. Hermes already did the hard research on these exact numbers, so copying real, correct values here is free accuracy.

## 2. `get_max_output_tokens(model)` — the lookup, with a safety net

```python
def get_max_output_tokens(model: str) -> int:
    return ANTHROPIC_MAX_OUTPUT_TOKENS.get(model, _SAFE_DEFAULT_MAX_OUTPUT_TOKENS)
```

**Why the fallback value is LOW (4,096), not high:** if we ever get asked about a model not in our table (a typo, or a brand-new model we haven't added yet), guessing a SMALL number is safe — the worst that happens is we use less capacity than we could have. Guessing a LARGE number is dangerous — if the real model's actual limit is smaller, the API call fails outright. Always fail toward "a bit less, but it works," never toward "guessed too much, now it's broken."

## 3. `get_default_max_tokens(model)` — the one that actually matters, and why it exists at all

```python
def get_default_max_tokens(model: str) -> int:
    return min(get_max_output_tokens(model), _ANTHROPIC_NONSTREAMING_SAFE_CEILING)
```

**Why this function exists separately from #2 — the real story:** at first, it seemed obviously correct to just use a model's TRUE capability as the default everywhere. That turned out to be wrong, discovered only by actually running a real API call: Anthropic's own SDK **refuses** a non-streaming call if you ask for too many tokens, because a non-streaming call makes you wait with zero feedback until it's completely done — and the SDK doesn't want you waiting potentially over 10 minutes with nothing happening. Our "correct" default of 64,000 was almost 3x past that line, so every normal `chat()` call started failing.

**The fix, in plain words:** keep two separate numbers for two separate questions — "what CAN this model do" (#2) vs. "what SHOULD we actually default to so nothing breaks" (#3, always capped at 20,000). If someone genuinely wants the model's full power for a long answer, they can still ask for it explicitly — just not as a silent default that breaks the common case.
