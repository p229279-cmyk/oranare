# Ornare Harness

A production-scale successor to the hand-built Ornare agent system —
built from scratch as our own scoped, pluggable harness, to support:

- **Agent A — Franchise Sales & Negotiation Intelligence**, one fully
  isolated instance per franchise (own WhatsApp number, own data).
- **Agent B — Client Lookup**, a single orchestrator-level agent that
  researches a client and synthesizes a profile ("story") for any
  franchise to use.

Built over a 10-day sprint.

## Documentation

Read in this order:

1. [`docs/PROBLEM_STATEMENT.md`](docs/PROBLEM_STATEMENT.md) — who has the
   problem, what's broken today, why now.
2. [`docs/PRD.md`](docs/PRD.md) — product requirements: goals, non-goals,
   functional requirements, success metrics.
3. [`docs/STACK.md`](docs/STACK.md) — the technology stack decision
   record: Python for the agent core (matching Hermes's own real
   choice), Node.js only for the WhatsApp bridge specifically (matching
   Hermes's own real choice there too), no agent framework layered on
   top.
4. [`docs/engine/00-OVERVIEW.md`](docs/engine/00-OVERVIEW.md) — **the
   engine itself, start here**: the complete A-to-Z harness at four
   levels of zoom (System Context → Container → Component → Sequence),
   then one detailed file per subsystem in [`docs/engine/`](docs/engine/)
   (agent loop, model provider, tools, system prompt, session store,
   profiles, config/secrets, pipelines, channels, access control,
   extensibility). Completely business-agnostic — this is "our harness,"
   independent of what any specific agent's job is. `docs/ENGINE.md` is
   now a short index into this directory.
5. [`docs/standards/`](docs/standards/) — the engine's non-negotiable
   cross-cutting rulebook, one file per concern: `SECURITY.md`,
   `COST.md`, `RELIABILITY.md`, `OBSERVABILITY.md`,
   `CONTEXT_MANAGEMENT.md`, `PERMISSIONS.md` — each reasoned from
   Hermes's own real production mechanisms, explicit about where we
   match Hermes and where our narrower pipeline-shaped workload lets us
   do structurally better (most notably `CONTEXT_MANAGEMENT.md`, which
   deliberately does NOT copy Hermes by default). `docs/ENGINEERING_STANDARDS.md`
   is now a short index into this directory.
6. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the product
   architecture: how THIS specific product (Agent A, Agent B, the
   franchise provisioning flow) is assembled on top of the engine.
7. [`docs/TECHNICAL_SPEC.md`](docs/TECHNICAL_SPEC.md) — implementation-
   level detail: exact data shapes, schemas, error/testing conventions.

**Important:** large parts of the PRD and spec are marked **[CONFIRM]** —
built from inferred requirements (handwritten planning notes + a verbal
walkthrough) pending the client's formal written report. See
`docs/ARCHITECTURE.md` §9 for the full open-questions list. None of the
open items block Days 1–5 (pure harness infrastructure); they start to
matter from Day 6 onward.

## Status

**Day 1 of 10 — Architecture + requirements docs.** See
`docs/ARCHITECTURE.md` §8 for the full day-by-day plan.

## Design principles

- Every subsystem has a clean, generic interface; only the concrete
  adapters this product actually needs are implemented today.
- One small agent-loop core; capability (agents, channels, tools) lives
  at the edges.
- Full filesystem isolation per franchise (directory-per-profile).
- Deterministic pipeline stages (COLLECT/ANALYZE/DELIVER) with exactly
  one locked-prompt LLM call per pipeline (REASON) — the proven shape
  from the original Ornare build.
