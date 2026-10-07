# Ornare Harness

A production-scale successor to the hand-built Ornare agent system —
built from scratch as our own scoped, pluggable harness, to support:

- **Agent A — Franchise Sales & Negotiation Intelligence**, one fully
  isolated instance per franchise (own WhatsApp number, own data).
- **Agent B — Client Lookup**, a single orchestrator-level agent that
  researches a client and synthesizes a profile ("story") for any
  franchise to use.

Built over a 10-day sprint. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the full system design, every subsystem interface, and the
day-by-day build plan.

## Status

**Day 1 of 10 — Architecture.** See `docs/ARCHITECTURE.md`.

## Design principles

- Every subsystem has a clean, generic interface; only the concrete
  adapters this product actually needs are implemented today.
- One small agent-loop core; capability (agents, channels, tools) lives
  at the edges.
- Full filesystem isolation per franchise (directory-per-profile).
- Deterministic pipeline stages (COLLECT/ANALYZE/DELIVER) with exactly
  one locked-prompt LLM call per pipeline (REASON) — the proven shape
  from the original Ornare build.
