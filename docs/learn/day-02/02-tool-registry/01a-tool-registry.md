# Day 2, Component 2, Step 1 — ToolRegistry: the `Tool` shape

Same build order as `ModelProvider`: real shapes first, one piece at
a time, each grounded in real Hermes source before being written —
but deviating deliberately wherever our own spec
(`docs/engine/03-TOOLS.md`, `docs/standards/SECURITY.md`) already made
a different decision. See
`docs/learn/day-02/02-tool-registry/00-big-picture.md` for the full
conceptual walkthrough this build follows; this file tracks the real
code as it gets built.

## What was built

`tools/registry.py` — a `Tool` dataclass: `name`, `description`,
`parameters`, `handler`, `blast_radius` (required), `check_fn`
(optional, defaults to `None`).

## Two deliberate differences from Hermes's real `ToolEntry`

1. **`blast_radius` is required, with no default.** Hermes's real
   `ToolEntry` has no such field — Hermes's own approval system
   (`tools/approval.py`, 5,498 lines) is a separate, much larger
   subsystem layered on top of dispatch. Our
   `docs/standards/SECURITY.md` made an explicit decision: every tool
   gets an enforced tier AT REGISTRATION TIME, never inferred later.
   Verified this is a REAL enforcement, not just documentation, with
   a test: constructing a `Tool` without `blast_radius` raises
   `TypeError` immediately.
2. **Only 6 fields, not Hermes's 11.** Hermes's real `ToolEntry`
   (`tools/registry.py`, verified via its `__slots__` tuple) also
   carries `toolset`, `requires_env`, `is_async`, `emoji`,
   `max_result_size_chars`, `dynamic_schema_overrides`. We start
   WITHOUT these — same YAGNI discipline as
   `agent/adapters/anthropic/quirks.py` starting with just 2 models.
   Each one gets added only when a real tool actually needs it, not
   speculatively. `toolset` and `is_async` are the two most likely to
   be needed soon (Step 5 and Step 4 of this build respectively).

## One more deliberate difference: dataclass, not `__slots__`

Hermes's real `ToolEntry` uses `__slots__` — a real, measured
memory-footprint optimization that matters when 100+ tool instances
live in one shared registry for the lifetime of a long-running
process. We don't have that scale yet. A plain `@dataclass` is
simpler to read, simpler to test, and the memory saving `__slots__`
buys isn't a problem we actually have today. Revisit only if real
tool counts and process lifetimes ever make this matter.

## Verified

5 tests, `tests/test_tool_registry.py`: construction with all
required fields, the handler is a real callable that produces a real
result, `check_fn` defaults to `None` (always available) and can be
set to a real callable, and — the one enforcement test that matters
most — omitting `blast_radius` raises `TypeError`, proving the
"required, not optional" design decision is real, not just a comment.

## Next

Step 2: the `ToolRegistry` class itself, starting with `register()`
only — mirroring how `AnthropicProvider` was built one method at a
time (`chat()` before `stream()`).

## A real question worth recording: why `blast_radius` when Hermes has no such field?

Hermes controls tool danger completely differently — not by tiering
tools at registration, but by pattern-matching the CONTENT of a
specific call (`tools/approval.py`'s `HARDLINE_PATTERNS`,
`DANGEROUS_PATTERNS`, the Tirith scanner). That mechanism fits
Hermes's real shape: ONE general-purpose tool (`terminal`) whose
danger depends on arbitrary command text, not on which tool it is.

Our shape is the opposite: many narrow, specific, purpose-built tools
per agent, where the danger is a property of WHICH tool it is, known
and fixed the moment it's written — not something that needs parsing
a call's content. `blast_radius` fits THIS shape, and — importantly,
given this project's goal of becoming one general-purpose harness
across 100+ future agent types across many industries, not just
Oranare's 2 — it scales cleanly: a dental agent's "cancel all
appointments" tool and a fraud-review agent's "freeze an account"
tool both just get tagged `consequential_bulk`, same mechanism, zero
new code per agent.

The two mechanisms are not competing choices — see `TODO.md`'s
"Content-based danger detection for tools" entry for the real,
deferred trigger condition for when a FUTURE tool (e.g. a `run_sql`
tool) would need BOTH: a fixed `blast_radius` tier AND a
Hermes-style content-pattern check layered on top.
