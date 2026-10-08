# Day 2 — Agenda

**Goal today:** build the first 3 real engine components, in code, as
hardened (production-quality) implementations — not teaching-lab
versions. Specs already exist for all three in `docs/engine/`; today we
implement them.

## Build order, and why

```
ModelProvider  →  ToolRegistry  →  Agent Loop
  (leaf)           (leaf)           (composer)
```

- **`ModelProvider` first.** It depends on nothing else we're building —
  only the Anthropic SDK. It's also the simplest of the three: one real
  job (talk to a model, classify failures correctly). Easiest + a true
  leaf = start here.
- **`ToolRegistry` second.** Also a leaf (no dependency on the Loop or
  on `ModelProvider`), but has more moving parts (registration, schema
  generation, dispatch, blast-radius tiering) — one step harder than
  `ModelProvider`.
- **Agent Loop last.** It's the composer — it needs BOTH of the above to
  already exist and be testable before it makes sense to build. Building
  it first would mean building against two interfaces we haven't proven
  out yet.

## How each component gets built (repeated for all 3 today)

1. **Write the learning doc first** (`docs/learn/day-02/0N-<component>.md`),
   following this fixed teaching order every time:
   **whole → boundaries → parts → relationships → mechanisms → underlying
   principles → deeper levels → coding → code understanding.**
2. **Write the code second**, one function or one class at a time — never
   a whole file dropped at once. Each step gets explained before moving
   to the next.
3. **Verify** — a real test proving the component's core contract, not
   just "it runs."

## Today's files

| # | Learning doc | Code | Spec it implements |
|---|---|---|---|
| 1 | `docs/learn/day-02/01-model-provider/01a-model-provider.md` | `agent/model_provider.py` | `docs/engine/02-MODEL-PROVIDER.md` |
| 1b | `docs/learn/day-02/01-model-provider/01b-anthropic-adapter.md` | `agent/adapters/anthropic_adapter.py` | `docs/engine/02-MODEL-PROVIDER.md` (concrete adapter) |
| 2 | `docs/learn/day-02/02-tool-registry.md` | `tools/registry.py` | `docs/engine/03-TOOLS.md` |
| 3 | `docs/learn/day-02/03-agent-loop.md` | `agent/loop.py` | `docs/engine/01-AGENT-LOOP.md` |

1 and 1b done. Continuing with 2 (`ToolRegistry`) next.
