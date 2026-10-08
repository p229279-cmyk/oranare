# Day 2, Component 1b — AnthropicProvider (agent/adapters/anthropic_adapter.py)

This is the concrete adapter for `ModelProvider` — the one piece of code
in the whole engine that is actually ALLOWED to know Anthropic's real
API shape. See `01-model-provider.md` first for the generic interface
this implements; this file is specifically about the concrete class,
kept in its own file (`agent/adapters/anthropic_adapter.py`), matching
Hermes's real one-file-per-adapter convention. One deliberate
difference: Hermes keeps these files flat directly in `agent/`, with no
dedicated subfolder; we group ours under `agent/adapters/` instead,
anticipating more adapters being added over time.

## Whole

`AnthropicProvider` is the one class standing between our entire engine
and the real Anthropic API over the network. Everything in
`model_provider.py` (the `Message`/`ModelResponse` shapes, the
`ModelProvider` Protocol, `classify_error`) exists to define WHAT this
class must do and HOW its inputs/outputs must look — this file is where
that contract actually gets fulfilled against a real vendor.

In one sentence: **`AnthropicProvider` is the only place in the whole
system where "Anthropic" is a word that's allowed to appear in code.**

## Boundaries

What's INSIDE this component's responsibility:
- Constructing and holding the real `anthropic.Anthropic` SDK client.
- Translating our engine's `Message`/`tools` shape into the exact dict
  shape `messages.create()`/`messages.stream()` expect.
- Translating Anthropic's real response (or stream of events) back into
  our engine's `ModelResponse`/`StreamEvent` shapes.
- Catching the one documented impossible case (`stop_reason=None` on a
  completed call) and failing loudly instead of silently.

What's OUTSIDE this component's responsibility (owned elsewhere):
- Deciding WHETHER to retry a failed call, or what kind of failure it
  was — that's `classify_error()`, in `model_provider.py`, which this
  file does not call directly; the caller (eventually the Agent Loop)
  is the one that catches an exception from this class and asks
  `classify_error()` what to do about it.
- Defining what shape `Message`/`ModelResponse`/`StreamEvent` must have
  — that's `model_provider.py`; this file only produces/consumes those
  shapes, never redefines them.
- Deciding what messages or tools to send in the first place — that's
  the Agent Loop and the system prompt builder, both still to come.

## Parts

One class, two public methods, matching the `ModelProvider` Protocol
exactly:

- **`__init__(api_key, model, max_tokens)`** — constructs the real SDK
  client once, holds it for the lifetime of this provider instance. The
  `anthropic` package is imported INSIDE this method, not at the top of
  the file, so `model_provider.py` and anything that only needs the
  generic interface can still be imported even where the `anthropic`
  package itself isn't installed.
- **`chat(messages, system, tools)`** — the non-streaming path: one
  request out, one complete `ModelResponse` back.
- **`stream(messages, system, tools)`** — the streaming path: one
  request out, a sequence of `StreamEvent`s back as the model generates
  its answer piece by piece.

## Relationships

```
Agent Loop  --calls-->  ModelProvider interface (model_provider.py)  --satisfied by-->  AnthropicProvider (anthropic_adapter.py)  --calls-->  Anthropic's real API over the network
```

Nothing else in the engine imports `anthropic_adapter.py` directly
except whatever code is responsible for CONSTRUCTING a provider instance
at startup (not yet built — that's a config/wiring concern for a later
day). Everything downstream of construction (the Agent Loop, pipelines)
only ever holds a reference typed as `ModelProvider`, never as
`AnthropicProvider` specifically.

## Mechanisms

Two mechanisms, same two as described conceptually in
`01-model-provider.md`, but this is where they're actually implemented
against a real vendor:

1. **Translation, in both directions.**
   - Request-side: our `list[Message]` becomes
     `[{"role": m.role, "content": m.content} for m in messages]` —
     deliberately the simplest possible translation, because `Message`
     was already designed (in `model_provider.py`) to be close enough to
     Anthropic's own shape that no deeper transformation is needed here.
   - Response-side: Anthropic's real `Message` object (from the SDK) has
     `.content`, `.stop_reason`, `.usage.input_tokens`,
     `.usage.output_tokens` — each gets read and placed directly into
     our own `ModelResponse` fields.
   - Stream-side: Anthropic's raw stream events (many different `type`
     values) get filtered down to only the two our engine actually
     needs to react to — `content_block_delta` (text arriving) and
     `message_stop` (the stream ending) — everything else is
     deliberately ignored, not translated.
2. **The impossible-value guard.** The SDK's own type definitions allow
   `stop_reason` to be `None`, but a completed, non-streaming call (or a
   stream that has genuinely finished) should never actually produce
   that. Rather than let a `None` quietly violate `ModelResponse`'s
   contract or surface as a confusing dataclass error two layers away,
   both `chat()` and the end of `stream()` check for this explicitly and
   raise a clear `ValueError` naming exactly what happened.

## Underlying principles

- **"This is the only file allowed to say the word Anthropic."**
  Every other file in the engine — the loop, the tools, the system
  prompt — is written as if it has no idea which vendor is on the other
  end. If a grep for `anthropic` or `Anthropic` ever turns up a hit
  outside this one file (and its own tests), that's a sign the boundary
  has leaked.
- **"Translate only what the caller needs, not everything the vendor
  sends."** The stream-handling code is the clearest example: Anthropic
  emits many different raw event types internally, but our engine's
  `StreamEvent` only needs two of them. Exposing every raw SDK event
  type here would leak Anthropic's internal streaming protocol one level
  further out than necessary.
- **"Fail loudly on an impossible case, don't silently let it through."**
  The `stop_reason=None` guard exists purely because of this principle —
  it is deliberately defensive code for a case that, as far as we know,
  cannot currently happen, written anyway because "the type system says
  it's possible" is reason enough to guard against it explicitly.

## Deeper levels — what streaming actually translates, and why so little

Anthropic's SDK, when you iterate over `messages.stream()`, emits events
with types like `message_start`, `content_block_start`,
`content_block_delta`, `content_block_stop`, `message_delta`, and
`message_stop` — six distinct raw event types for a single streamed
response. `AnthropicProvider.stream()` only ever produces two kinds of
`StreamEvent` from all of that:

| Raw SDK event(s) | What we do with it | Our StreamEvent |
|---|---|---|
| `content_block_delta` where `delta.type == "text_delta"` | Pull out just the new text fragment | `StreamEvent("text_delta", text)` |
| `message_stop` | Call `get_final_message()` to get the complete, final message; build a full `ModelResponse` from it exactly like `chat()` does | `StreamEvent("message_stop", ModelResponse(...))` |
| everything else (`message_start`, `content_block_start`, `content_block_stop`, `message_delta`, non-text content deltas) | Ignored entirely | *(nothing yielded)* |

**The one-sentence rule underneath this table:** *a caller watching a
live stream only ever needs to know two things — "here's some more text"
and "it's done, here's the complete picture" — everything else is
protocol-level bookkeeping the caller should never have to care about.*

## Coding

Already built, in `agent/adapters/anthropic_adapter.py`, in this order:

1. `__init__` — construct the real SDK client.
2. `chat()` — the non-streaming path, built and live-verified first
   (simpler to reason about and to test).
3. `stream()` — the streaming path, built once `chat()` was proven
   correct, reusing the exact same translation logic for the final
   message.

Both methods were verified two ways: mocked unit tests (no network call,
proving the translation logic itself), and one real live call each
against the actual Anthropic API using a cheap model (Haiku) — see
`tests/test_anthropic_adapter.py` for the mocked tests, and the Day 2
commit history for the live-verification details.

## Code understanding

*(Not written yet — per instruction, the detailed function-by-function
explanation for this file goes into
[`01-model-provider-code-explaination.md`](01-model-provider-code-explaination.md)
separately, shown for approval before it's added, same process as every
other component.)*
