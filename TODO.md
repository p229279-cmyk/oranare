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

---

## Done — built, tested, live-verified

- **Category C — Model-specific quirks** (`agent/adapters/anthropic/quirks.py`):
  full Claude model lineup, safe defaults, caught+fixed a real SDK
  non-streaming-timeout bug.
- **Category E — Retry/failover** (`agent/retry.py` +
  `context_overflow` classification): jittered backoff, bounded retry
  loop, wired into `AnthropicProvider.chat()`/`stream()`, caught+fixed
  a real `ProviderInvariantError`-vs-`ValueError` classification bug.

Full detail on both: `docs/learn/day-02/01-model-provider/01c-ornare-vs-hermes.md`.

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
