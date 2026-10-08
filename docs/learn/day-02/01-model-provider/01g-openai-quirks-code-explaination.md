## 1. `OPENAI_MAX_OUTPUT_TOKENS` — real numbers, not guesses

```python
OPENAI_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "gpt-5.6-sol": 128_000,
    "gpt-5.6-terra": 128_000,
    "gpt-5.6-luna": 128_000,
    "gpt-5.6": 128_000,  # alias that routes to gpt-5.6-sol
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "gpt-4-turbo": 4_096,
}
```

**Why all three `gpt-5.6` tiers (Sol, Terra, Luna) share the exact same number:** this isn't a shortcut or an approximation — OpenAI's own documentation states all three really do share the identical 128,000 max-output limit; only their price and raw intelligence differ between tiers, not this particular number.

**Why `"gpt-5.6"` (with no tier name) is its own separate entry, even though it points to the same number as `"gpt-5.6-sol"`:** `"gpt-5.6"` is a plain ALIAS that OpenAI's API itself resolves to the Sol tier automatically — someone using our code might reasonably pass either name, and both need to resolve to a correct answer, not just whichever one we happened to think of first.

## 2. `get_max_output_tokens(model)` — the lookup

```python
def get_max_output_tokens(model: str) -> int:
    return OPENAI_MAX_OUTPUT_TOKENS.get(model, _SAFE_DEFAULT_MAX_OUTPUT_TOKENS)
```

**Why the fallback (4,096) stays low, same reasoning as the Anthropic version:** if someone passes in a model name we haven't added to our table yet, guessing a SMALL number is the safe mistake — worst case, we just don't use quite as much capacity as we actually could have. Guessing a LARGE number is the dangerous mistake — if the real model's actual limit happens to be smaller, the API call fails outright instead of just working a little less efficiently.

## 3. `get_default_max_tokens(model)` — a function that currently does "nothing extra," and why that's still correct

```python
def get_default_max_tokens(model: str) -> int:
    return get_max_output_tokens(model)
```

**Why this exists as its own separate function when it's currently just forwarding the exact same value:** this mirrors `AnthropicProvider`'s shape on purpose. For Anthropic, this exact function name does REAL extra work — it caps the model's raw capability down to a smaller, SDK-safe number. For OpenAI, checking the real SDK directly showed that no equivalent restriction exists, so there's genuinely nothing extra to do right now.

**Why we didn't just delete this function and call `get_max_output_tokens` directly from `provider.py` instead, since right now they'd behave identically:** keeping this as its own named function means that if OpenAI ever DOES introduce a similar real restriction in the future — vendors do change their APIs over time — there's already an obvious, correctly-named place to add that new logic, without having to first go find every place in `provider.py` that calls `get_max_output_tokens` directly and change it. The function's EXISTENCE is the real design decision here, even though its current body is trivial.
