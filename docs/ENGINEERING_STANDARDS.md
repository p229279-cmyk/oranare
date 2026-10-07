# Engineering Standards — Index

**This file is now a short index.** The full, detailed standards — each
with its own diagrams — live in [`docs/standards/`](standards/), one
file per concern:

| File | Covers |
|---|---|
| [`SECURITY.md`](standards/SECURITY.md) | Minimal tool surface, blast-radius tiering, the hardline+deny-list layer, credential/data isolation, prompt-injection handling |
| [`COST.md`](standards/COST.md) | Why the pipeline shape is structurally cheaper, the per-run cost ledger, proactive cost ceilings, caching economics across profiles |
| [`RELIABILITY.md`](standards/RELIABILITY.md) | Classified failure handling, no-partial-delivery, idempotent re-runs, approval timeout handling |
| [`OBSERVABILITY.md`](standards/OBSERVABILITY.md) | Structured per-run records, no forced third-party SaaS, status as a first-class signal |
| [`CONTEXT_MANAGEMENT.md`](standards/CONTEXT_MANAGEMENT.md) | Where this engine deliberately does NOT copy Hermes, and why — reasoned from first principles |
| [`PERMISSIONS.md`](standards/PERMISSIONS.md) | The full layered permission model, consolidated as one picture |

## The one structural fact every file above depends on

Hermes is a general-purpose, long-running conversational agent. Every
agent built on this engine is a narrow, known-job pipeline
(`docs/engine/08-PIPELINE-SCHEDULER.md`) with a small, known toolset,
running seconds to minutes, not hours to days. That shape is the real
lever for beating Hermes on cost and security — each file above is
explicit about where this lets us go further than Hermes, and where
Hermes's own proven solution applies to us unmodified (most notably in
`CONTEXT_MANAGEMENT.md`).
