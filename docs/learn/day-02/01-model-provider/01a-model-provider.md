# Day 2, Component 1 — ModelProvider

## Whole

`ModelProvider` is the one piece of code in the entire engine that
actually talks to an AI model. Everything else in the system — the loop,
the tools, the prompts — exists to prepare a request for this component
to send, and to make sense of what it sends back. If you deleted every
other file in `agent/`, this is the one file that would still need to
exist for the system to do anything at all.

In one sentence: **`ModelProvider` turns "a conversation and some tools"
into "a model's response," and hides every detail of how one specific
vendor's API happens to do that.**

## Boundaries

What's INSIDE this component's responsibility:
- Sending a request to the model vendor's API, in that vendor's exact
  wire format.
- Receiving the response and turning it into a result shape the REST of
  our engine understands (vendor-agnostic).
- Deciding what to do when a call fails (retry? give up? wait?).

What's OUTSIDE this component's responsibility (owned elsewhere):
- Deciding WHAT to say to the model (that's the system prompt — a
  different component).
- Deciding WHICH tools to offer (that's the tool registry).
- Deciding what to DO with a tool-call request once it comes back
  (that's the agent loop).
- Remembering past turns (that's the session store).

This component answers one question only: **"I have a conversation and
some tools — what does the model say?"** It does not ask or answer any
other question.

## Parts

Two methods make up the whole public surface:

- **`chat(messages, system, tools)`** — send everything at once, get one
  complete response back. Simple, used for pipeline REASON stages where
  we just need the final answer.
- **`stream(messages, system, tools)`** — send everything at once, get
  the response back piece by piece as it's generated. Used when a human
  is waiting and watching (e.g. a live WhatsApp conversation) where
  seeing partial output sooner genuinely matters.

Underneath, ONE concrete implementation today: `AnthropicProvider` — the
adapter that actually knows how to speak Anthropic's specific API. It
lives in its own package (`agent/adapters/anthropic/`), separate
from the generic interface (`agent/model_provider.py`) — matching
Hermes's real pattern of one file per provider adapter. One deliberate
difference: Hermes keeps these flat directly in `agent/`; we group ours
under a dedicated `agent/adapters/` subfolder instead, anticipating more
adapters being added over time.

## Relationships

```
Agent Loop  --calls-->  ModelProvider interface  --implemented by-->  AnthropicProvider  --calls-->  Anthropic's real API
```

The Agent Loop (tomorrow's component) will hold a reference to SOME
`ModelProvider` — it will never know or care that it's specifically
`AnthropicProvider` underneath, or which file that class happens to live
in. This is what lets us add a second vendor later (if we ever genuinely
need to) without touching the loop, the interface file, or any existing
adapter's file at all — just one new file.

## Mechanisms

Two mechanisms do almost all the real work inside `AnthropicProvider`:

1. **Translation.** Our engine's `messages`/`tools` shape gets converted
   to exactly what Anthropic's API expects, and Anthropic's response
   shape gets converted back to our engine's `ModelResponse` shape. This
   translation happens ONLY here — nowhere else in the engine needs to
   know Anthropic's wire format.
2. **Classification + recovery.** When a call fails, we don't just
   "retry a few times." We figure out WHAT KIND of failure it was (rate
   limit? bad request? server overloaded? auth expired?) and respond
   differently for each kind — because retrying a failure that can never
   succeed just wastes time and money.

## Underlying principles

- **"Ask what the caller needs, not what the vendor gives you."** We
  designed this interface by asking "what does the Agent Loop actually
  need to know" — not by copying Anthropic's own API shape one-for-one.
  This is why the interface stays stable even if Anthropic changes their
  API's exact field names tomorrow.
- **"A failure is not just a failure — it has a type, and the type
  decides what to do next."** This is the single most important idea in
  this file, and it's the one we'll spend the most code on.

## Deeper levels — the failure classification table

This is the part of `ModelProvider` with the most real engineering in
it, so it gets its own level before we touch any code:

| What actually happened | What it means | What we do about it |
|---|---|---|
| HTTP 429 (rate limited) | We're sending requests too fast | Wait a bit (with randomness so many retries don't all pile up at once), then try again |
| HTTP 500/503 (server error/overloaded) | Anthropic's own servers are having trouble, not us | Wait, then try again — a few times, not forever |
| HTTP 401 (auth failed) | Our API key is wrong or expired | STOP immediately. Trying again with the same bad key will fail the exact same way, forever. |
| HTTP 400 (bad request) | We sent something malformed | STOP immediately and log exactly what we sent — retrying an identical malformed request can never succeed |
| Network timeout | The connection itself had a problem, not the API | Try again, usually just once |

**The one-sentence rule underneath this whole table:** *only retry a
failure that has a real chance of succeeding on the next try.* A
malformed request will be malformed again. A dead API key is still dead.
Retrying those isn't resilience — it's wasted time and wasted money for
a guaranteed-identical result.

## Coding

We build this in two files, one piece at a time:

1. The shared data shapes every provider must speak (`Message`,
   `ModelResponse`) — the "vendor-agnostic vocabulary." Lives in
   `agent/model_provider.py`.
2. The `ModelProvider` interface itself (just the contract, no logic).
   Also in `agent/model_provider.py`.
3. The failure classifier — `classify_error()` — built and TESTED on
   its own, before it's wired into anything that calls a real API. Also
   in `agent/model_provider.py`.
4. `AnthropicProvider.chat()` — the simple, non-streaming path first.
   Lives in its OWN package, `agent/adapters/anthropic/` (provider.py
   + quirks.py), not `model_provider.py` — inspired by Hermes's real
   one-file-per-adapter pattern (confirmed against Hermes's actual
   source: `anthropic_adapter.py`, `bedrock_adapter.py`,
   `vertex_adapter.py` are each their own file there too, though Hermes
   keeps them flat in `agent/`, as one file each, rather than under a
   dedicated per-provider subfolder split into multiple files).
5. `AnthropicProvider.stream()` — added once `chat()` is proven correct.
   Same file as step 4.

## Code understanding

Short summary of each step's result — full function-by-function
reasoning lives in
[`01a-model-provider-code-explaination.md`](01a-model-provider-code-explaination.md).

1. **Shared data shapes** (`Message`, `ModelResponse`, `StreamEvent`) —
   the vendor-agnostic vocabulary every provider speaks. No Anthropic
   mentioned anywhere in this step. (`agent/model_provider.py`)
2. **`ModelProvider` interface** (`chat`, `stream`) — the contract
   itself, as a `Protocol`, zero logic inside it.
   (`agent/model_provider.py`)
3. **Failure classifier** (`classify_error`) — maps a raw error to a
   failure type + a `should_retry` decision. Built and tested standalone
   with fabricated errors, 6/6 tests passing, no live API key needed.
   Later hardened with 2 more tests against the REAL Anthropic SDK's
   own exception classes, which caught and fixed a real bug (timeout
   detection missed the SDK's actual `APITimeoutError`, which isn't a
   subclass of `TimeoutError`/`OSError`). (`agent/model_provider.py`)
4. **`AnthropicProvider.chat()`** — the real adapter that actually talks
   to Anthropic's API: translates our `Message`/`tools` into Anthropic's
   wire format, sends the request, translates the real response back
   into our `ModelResponse` shape. Also fixed a second real bug found
   while building this step: `ModelResponse.stop_reason` only allowed 3
   values but the real SDK allows 7 — corrected to match exactly. Tested
   with 3 mocked tests (request translation, response translation, and
   a defensive guard for an impossible `stop_reason=None` case) plus one
   LIVE verification call against the real API (Haiku, cheap model) that
   confirmed the whole thing end to end. Lives in its own file,
   `agent/adapters/anthropic/provider.py` — see the Relationships
   section above for why.


