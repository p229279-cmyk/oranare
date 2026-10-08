# Day 2, Component 1 — ModelProvider: Code Explanation

This file holds the detailed, function-by-function / class-by-class
explanation of the actual code in `agent/model_provider.py` — "what this
code does and why it's written this way," for every step. The teaching
doc (`01-model-provider.md`) stays focused on concepts (whole →
boundaries → parts → relationships → mechanisms → principles); this file
is where the CODE itself gets explained in depth.

---

## Step 1 — the shared data shapes (`Message`, `ModelResponse`, `StreamEvent`)

**What this code does:** defines the "vendor-agnostic vocabulary" — the
only shapes the REST of the engine (the loop, the tools) is ever allowed
to know about. No mention of Anthropic anywhere in this file.

**Why it's written this way:**

- `Message.content: Any` looks loose on purpose. A message's content
  really can be one of several different shapes (plain text, or a list
  of blocks when tool calls are involved) — forcing a single strict type
  here would just push the problem to invent a union type that mirrors
  Anthropic's own content-block shape, which is exactly the vendor
  leakage this file exists to prevent. The REAL shape-checking happens
  inside `AnthropicProvider`, where it's allowed to know vendor details.
- `ModelResponse.stop_reason` uses a `Literal` (not a free string) —
  this is the one field the Agent Loop's core decision (step 3: "tool
  call or final answer?") is built on, so it's worth being strict here
  even though `content` stays loose.
- `input_tokens`/`output_tokens` are included on every response, not
  bolted on later — this is what feeds the cost ledger
  (`docs/standards/COST.md` §2) from day one, instead of being an
  afterthought retrofitted once someone asks "wait, what did this
  cost?"

---

## Step 2 — the `ModelProvider` interface contract

**What this code does:** declares the two methods (`chat`, `stream`)
every provider adapter MUST implement — the contract itself, with zero
logic inside it.

**Why it's written this way:**

- `Protocol` (not an abstract base class) was chosen because it's
  structural typing — a class satisfies this interface just by HAVING
  the right methods with the right shapes, no explicit
  `class AnthropicProvider(ModelProvider)` inheritance required. This
  matches the engine's own stated design test
  (`docs/engine/00-OVERVIEW.md`): a new provider should be addable
  purely by writing a new class with the right shape, never by touching
  this file.
- Both methods take the exact same three arguments
  (`messages`, `system`, `tools`) — this symmetry is deliberate. The
  Agent Loop should be able to switch between `chat` and `stream` for
  the same request without reshaping its own data first.

---

## Step 3 — the failure classifier (`classify_error`)

**What this code does:** given a raw error from the Anthropic SDK,
decides WHICH of the failure types from the teaching doc's "Deeper
levels" table it is, and returns a `ClassifiedError` carrying that
decision plus whether a retry is worth attempting.

**Why it's written this way:**

- This is built and tested **on its own, before any real API call
  exists to produce errors for it.** We can fabricate fake exceptions
  with the right status codes and prove the classifier picks correctly
  — no network, no API key, no flakiness. This matches the project's
  standing honesty rule: logic that doesn't require a live model call
  must be fully testable without one.
- `should_retry: bool` is a field on the result, not something the
  caller has to re-derive from the failure type — the classifier is the
  one place that encodes "is this worth trying again," so that decision
  never gets silently reimplemented differently somewhere else in the
  codebase.
- The classifier reads the HTTP status code first (most reliable
  signal), and only falls back to inspecting the error message text when
  the status code alone is ambiguous (e.g. a 400 could be several
  different real problems depending on what the message says).

**Test coverage (`tests/test_model_provider.py`):** 6 tests, all passing,
all against fabricated fake exceptions — no network, no API key:
`test_rate_limit_is_retryable`, `test_server_error_is_retryable` (covers
500/502/503/529), `test_auth_failure_is_not_retryable`,
`test_bad_request_is_not_retryable`, `test_timeout_is_retryable`,
`test_unrecognized_error_defaults_to_retryable_unknown`.
