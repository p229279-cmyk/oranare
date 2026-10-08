# Day 2, Component 1f — OpenAIProvider (agent/adapters/openai/provider.py)

This is the SECOND concrete adapter for `ModelProvider` — built to
prove, not just assert, the engine's own design guarantee
(`docs/engine/00-OVERVIEW.md`): adding a new provider should require
zero changes to the generic interface, the loop, or any existing
adapter. See `01b-anthropic-adapter.md` for the first adapter's full
walkthrough; this doc focuses on what's genuinely DIFFERENT here, same
fixed teaching order as every other component.

## Whole

`OpenAIProvider` is the class that actually talks to OpenAI's real
API, the exact same role `AnthropicProvider` plays for Anthropic. In
one sentence: **it's proof that the `ModelProvider` interface really
is vendor-agnostic, built by implementing it a second time against a
genuinely different vendor and confirming nothing upstream had to
change.**

## Boundaries

What's INSIDE this component's responsibility — identical boundaries
to `AnthropicProvider`, just pointed at a different vendor:
- Translating our engine's `Message`/tools shape into OpenAI's exact
  wire format.
- Making the real HTTP call to OpenAI's Chat Completions API.
- Translating OpenAI's response back into our engine's `ModelResponse`
  shape.

What's OUTSIDE this component's responsibility — same boundaries,
reused completely unchanged from the first adapter:
- Deciding whether a failure is retryable — `classify_error()` in
  `model_provider.py`, used UNCHANGED.
- Actually retrying — `call_with_retry()` in `agent/retry.py`, used
  UNCHANGED.
- Facts about specific OpenAI models (real token limits) —
  `agent/adapters/openai/quirks.py`, same split as Anthropic's
  `provider.py`/`quirks.py` pair.

## Parts

Two real methods, plus one real helper:

- **`chat(messages, system, tools)`** — ask once, get one full answer.
- **`stream(messages, system, tools)`** — ask once, get the answer
  piece by piece.
- **`_map_finish_reason(finish_reason)`** — translates OpenAI's
  `finish_reason` vocabulary into our engine's `stop_reason`
  vocabulary. This is the ONE piece of real translation work that
  didn't exist in the Anthropic adapter in this exact shape (Anthropic
  already uses very similar wording — `end_turn`, `max_tokens` — so no
  dedicated mapping function was needed there; OpenAI's vocabulary
  genuinely differs — `stop`, `length`, `tool_calls` — so a real
  translation step earns its keep here).

## Relationships

```
Agent Loop  --calls-->  ModelProvider interface (model_provider.py)
    --satisfied by-->  AnthropicProvider (anthropic/provider.py)  --calls-->  Anthropic API
    --satisfied by-->  OpenAIProvider   (openai/provider.py)      --calls-->  OpenAI API

Both adapters  --share-->  classify_error()  (model_provider.py)
Both adapters  --share-->  call_with_retry() (agent/retry.py)
```

Nothing in this diagram was invented for OpenAI — the loop, the
classifier, and the retry logic are the EXACT SAME boxes drawn for
Anthropic. Only a new leaf (`OpenAIProvider`) and a new outgoing arrow
(to OpenAI's API) were added.

## Mechanisms

Two real mechanisms worth calling out, because they're genuinely
different from how Anthropic's adapter works — this is where "two
vendors speak different wire protocols" becomes concrete, not abstract:

1. **The system prompt is a MESSAGE, not a separate parameter.**
   Anthropic's API takes `system` as its own top-level argument,
   separate from the `messages` list. OpenAI's Chat Completions API has
   no such parameter at all — the system prompt has to be the FIRST
   entry in the `messages` list, with `role="system"`. Verified
   directly against the real SDK's `create()` signature (no `system`
   kwarg exists), not assumed from memory.
2. **`finish_reason` needs an explicit translation table, because
   OpenAI's vocabulary doesn't line up with ours by coincidence the way
   Anthropic's mostly does.** OpenAI's real values (verified against
   `openai.types.chat.chat_completion.Choice.finish_reason`): `"stop"`,
   `"length"`, `"tool_calls"`, `"content_filter"`, `"function_call"`
   (the last one deprecated, kept for completeness). None of these
   match our `ModelResponse.stop_reason` vocabulary by name — `_map_finish_reason`
   exists specifically to do that translation once, in one place,
   rather than every caller having to know both vocabularies.

## Underlying principles

- **"A second real implementation is the only honest way to test
  whether an interface is actually generic, or just happened to fit
  the first vendor by coincidence."** Designing an interface against
  ONE vendor and declaring it "vendor-agnostic" is a claim that can't
  really be checked until a second, genuinely different vendor is
  plugged in. OpenAI was the test; it passed — zero changes needed
  upstream.
- **"Where two vendors' wire formats genuinely differ, the adapter
  absorbs the difference — it never leaks outward as a special case in
  the loop or the interface."** The system-prompt-as-message quirk and
  the `finish_reason` translation table both live ENTIRELY inside
  `agent/adapters/openai/`. Nothing in `model_provider.py` or the
  (future) loop needs an `if provider == "openai"` branch anywhere.
- **"Shared infrastructure stays shared — don't let a second adapter
  tempt you into duplicating logic 'just to be safe.'"** `call_with_retry`
  and `classify_error` are reused byte-for-byte, not copy-pasted and
  re-adapted. If OpenAI ever needed genuinely different retry behavior,
  that would be a real, deliberate decision to make — not an accident
  of copy-pasting a working function and quietly diverging from it.

## Deeper levels — two real bugs, caught by two real live calls

Same honesty standard as every other adapter in this project: built,
tested with mocks, then verified live — and the live call found real
things the mocks couldn't have caught, because the mocks only test
what we already believed to be true.

**Bug 1 — no `system` parameter exists.** This wasn't actually a bug
caught by surprise; it was identified UP FRONT by checking the real
SDK's `create()` signature before writing any code (same discipline
used for the Anthropic adapter from day one) — so the fix (prepend a
`{"role": "system", ...}` message) was built in correctly the first
time, not discovered via a failing live call. Mentioned here because
it's exactly the kind of difference a careless "just copy the Anthropic
adapter's shape" port would have missed.

**Bug 2 — `max_tokens` is rejected outright by `gpt-5.6`.** This one
WAS caught live, the hard way:

```
openai.BadRequestError: Error code: 400 -
{'error': {'message': "Unsupported parameter: 'max_tokens' is not
supported with this model. Use 'max_completion_tokens' instead.",
'type': 'invalid_request_error', 'param': 'max_tokens',
'code': 'unsupported_parameter'}}
```

In plain words: OpenAI's newer/reasoning-family models (which includes
the `gpt-5.6` family) no longer accept the parameter named `max_tokens`
at all — they require a differently-named parameter,
`max_completion_tokens`, instead. This is a real, documented OpenAI API
change (their own reasoning: with reasoning models, the number of
tokens GENERATED and the number of tokens RETURNED to the caller aren't
the same thing anymore, so they renamed the parameter to force every
caller to explicitly opt into that new behavior rather than silently
reinterpreting the old parameter's meaning).

**The fix:** both `chat()` and `stream()` were switched from
`max_tokens=` to `max_completion_tokens=` in their real API calls. A
regression test
(`test_chat_uses_max_completion_tokens_not_the_legacy_max_tokens_param`)
locks this in by asserting the exact kwarg name sent to the mocked
client, so a future accidental revert back to `max_tokens` would fail
a fast test instead of only being caught by another live call.

**The one-sentence rule underneath this section:** *the mocks we write
only verify the behavior we already believed was correct — a real,
live call is the only thing that can tell you the vendor's actual API
contract has a detail you didn't know to mock correctly in the first
place.*

## Coding

Built in this order:

1. Checked the real SDK (`openai.OpenAI.chat.completions.create`'s
   signature, the real response/chunk shapes via
   `openai.types.chat.*`) BEFORE writing any code — same discipline as
   the Anthropic adapter.
2. `agent/adapters/openai/quirks.py` — the model-limits table, built
   first since `provider.py` depends on it (same build order as
   Anthropic: data/facts before the logic that consumes them).
3. `agent/adapters/openai/provider.py` — `_map_finish_reason()` first
   (a pure, easily-testable translation function), then `chat()`, then
   `stream()`.
4. Live-verified both methods against the real API — found and fixed
   the `max_completion_tokens` bug during this step.
5. `agent/adapters/openai/__init__.py` — the re-export, matching
   Anthropic's package shape exactly.

## Code understanding

Full function-by-function explanation lives in
[`01f-openai-adapter-code-explaination.md`](01f-openai-adapter-code-explaination.md).
