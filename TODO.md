# Oranare Harness — Standing TODO / Decision Memory

This file is the authoritative, durable record of decisions that must
survive context resets — read this FIRST when picking work back up
after a gap, before re-deriving anything from scratch.

---

## Deferred work — NOT built yet, on purpose, with a real trigger condition

### Category D — Message-list sanitization (NOT built)

**What it would do:** repair a conversation's message list before
sending it to Anthropic (merge consecutive same-role messages, strip
orphaned tool-call blocks with no matching result) — see
`docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md` category
D for the full reasoning, grounded in Hermes's real
`agent/anthropic_adapter.py` (`_merge_consecutive_roles`,
`_strip_orphaned_tool_blocks`).

**Why it's not built:** our current pipeline-shaped agents build a
SHORT, FRESH conversation every single run — there is no long-lived,
repeatedly-edited history that could ever drift into one of the
invalid shapes this would fix. Building it now would be speculative
work against a problem that does not exist yet.

**The real trigger to build it:** the moment either of these becomes
true:
1. Real multi-turn WhatsApp conversation handling is built (Day 5+ —
   `docs/engine/09-CHANNELS.md`), OR
2. Context compression/history-trimming is added for long
   conversations (`docs/standards/CONTEXT_MANAGEMENT.md`).

Do NOT build D before one of these two things exists for real.

### Category F — Model metadata/pricing (NOT built)

**What it would do:** a small, static table of real per-model PRICING
(not just the output-token limits category C already covers), feeding
a cost ledger — see `01c-ornare-vs-hermes.md` category F, grounded in
Hermes's real `agent/model_metadata.py`.

**Why it's not built:** `docs/standards/COST.md` already describes the
INTENT to track real per-call cost, but no cost-ledger code exists at
all yet. Building the pricing table in isolation, with nothing to feed
it, would be premature — there's no consumer for the data yet.

**The real trigger to build it:** the moment `docs/standards/COST.md`'s
cost tracking is actually implemented in code. Build F ALONGSIDE that
work, not before it, not separately.

### Content-based danger detection for tools (NOT built)

**What it would do:** Hermes's real mechanism
(`tools/approval.py` — `HARDLINE_PATTERNS`, `DANGEROUS_PATTERNS`, the
Tirith security scanner, smart-approval via an auxiliary LLM) decides
whether ONE SPECIFIC CALL to a tool is dangerous by pattern-matching
the actual CONTENT of its arguments (e.g. is this exact shell command
`rm -rf /tmp/foo` or `rm -rf /`). This is a fundamentally different
question from `blast_radius` (see below), and genuinely useful — but
only for a tool whose risk depends on WHAT'S INSIDE the call, not on
WHICH tool it is.

**Why it's not built:** every tool across both of today's agents
(Pulse, Rapid, Forge, Scout, Sentry via `oranare-harness`) is a
specific, narrow, named action (e.g. "send one approved quote").
`blast_radius` (identity-based tiering, already built —
`tools/registry.py`) is sufficient for every tool like this: the tier
is fixed and known the moment the tool is written, no content parsing
needed. We have no tool today whose danger varies call-by-call based
on its own argument content.

**The real trigger to build it:** the moment ANY future tool — in
Oranare or any of the other 100 planned agent types (see "Standing
architectural principle" below) — is genuinely open-ended, i.e. its
real-world danger depends on what's INSIDE a specific call, not on
which tool was invoked. Concrete future examples that would trigger
this: a `run_sql` tool for a Data Analytics Agent (`SELECT` vs.
`DROP TABLE` are wildly different risk, same tool), a
`run_shell_command` tool for a DevOps Incident Agent, or an
`execute_workflow_script` tool. When that tool is built, give IT
specifically a Hermes-style pattern-matching layer on top of its own
fixed `blast_radius` tier — not a general subsystem built ahead of
any real consumer.

---

## Standing architectural principle — build for 100 agent types, not 2

This harness's real long-term goal is ONE general-purpose system,
reused across a wide range of future agent types across many
industries (real estate, dental, legal, finance, HR, e-commerce,
logistics, and more) — NOT a system custom-built only for Oranare's 2
current agents. Every architectural decision in this repo must be
checked against that future scale and diversity, not just today's
narrow case.

**The concrete rule this produces, when deciding whether to copy a
Hermes mechanism or build our own:** adopt Hermes's real mechanism
where OUR tool/agent shape genuinely MATCHES Hermes's own shape
(Hermes: one general-purpose tool whose danger depends on arbitrary
content — e.g. a shell command's text). Build our own, simpler
mechanism where our shape is genuinely different (us: many narrow,
specific, purpose-built tools per agent, whose danger is a property of
WHICH tool it is, fixed at registration, not what's inside one call).
`blast_radius` (identity-based tiering, built) and Hermes's real
content-based pattern matching (not yet needed, deferred above) are
not competing choices — they are two different tools for two different
real problems, and a future tool can need BOTH layered together (a
fixed `blast_radius` tier, plus a content-based check on top, for the
rare tool whose risk is genuinely call-by-call).

---

## Done — built, tested, live-verified

- **Category C — Model-specific quirks** (`agent/adapters/anthropic/quirks.py`):
  full Claude model lineup, safe defaults, caught+fixed a real SDK
  non-streaming-timeout bug.
- **Category E — Retry/failover** (`agent/retry.py` +
  `context_overflow` classification): jittered backoff, bounded retry
  loop, wired into `AnthropicProvider.chat()`/`stream()`, caught+fixed
  a real `ProviderInvariantError`-vs-`ValueError` classification bug.
- **Second ModelProvider adapter — `OpenAIProvider`**
  (`agent/adapters/openai/`, mirrors `agent/adapters/anthropic/`'s
  exact shape): built to prove, not just assert, the engine's
  "zero changes to the generic interface" design guarantee — confirmed
  true, no changes needed to `model_provider.py`, the loop, or
  `AnthropicProvider`. Retry/classification logic (`call_with_retry`,
  `classify_error`) reused completely unchanged. Caught+fixed two real
  bugs via live calls: (1) OpenAI's Chat Completions API has no
  top-level `system` parameter — the system prompt is prepended as the
  first message instead; (2) `gpt-5.6` rejects the legacy `max_tokens`
  parameter outright (400 error) — fixed by switching to
  `max_completion_tokens`. Live-verified end-to-end (`chat()` and
  `stream()`) against the real OpenAI API with `gpt-5.6-luna`.

Full detail on all of the above: `docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md`.

---

## Standing process rules (apply to every future component, not just ModelProvider)

1. Every `0Nc-ornare-vs-hermes.md` comparison doc gets a **KNOWLEDGE**
   section explaining the relevant Hermes mechanism from scratch
   (what it solves, how it works, real code grounding) BEFORE the
   needed/not-needed verdict table — never just a bare table.
2. Code-explanation files (`*-code-explaination.md`) are drafted in
   chat and shown first — never written to disk without explicit
   approval on that exact content.
3. Every single step — even one small function — gets committed and
   pushed immediately, never batched to the end.
4. When code changes after a doc was already written describing it,
   BOTH the teaching doc and the code-explanation doc get checked and
   corrected in the same pass — never left stale.
5. A new adapter (second model provider, etc.) gets its own new
   package/file — zero changes to existing generic interfaces.
