# The Engine — Index

**This file is now a short index.** The full, detailed engine
specification — with system-context, container, component, and sequence
diagrams for every subsystem — lives in [`docs/engine/`](engine/), one
file per subsystem, starting with the big picture:

➡️ **[`docs/engine/00-OVERVIEW.md`](engine/00-OVERVIEW.md) — start here.**
Shows the complete A-to-Z engine at four levels of zoom (System Context →
Container → Component → Sequence), and the full file index.

## Subsystem files

| File | Subsystem |
|---|---|
| [`01-AGENT-LOOP.md`](engine/01-AGENT-LOOP.md) | The core loop every agent runs on |
| [`02-MODEL-PROVIDER.md`](engine/02-MODEL-PROVIDER.md) | Talking to a model vendor |
| [`03-TOOLS.md`](engine/03-TOOLS.md) | Giving an agent capabilities |
| [`04-SYSTEM-PROMPT.md`](engine/04-SYSTEM-PROMPT.md) | Identity, rules, caching |
| [`05-SESSION-STORE.md`](engine/05-SESSION-STORE.md) | Memory / persistence |
| [`06-PROFILES.md`](engine/06-PROFILES.md) | Isolated agent identities |
| [`07-CONFIG-SECRETS.md`](engine/07-CONFIG-SECRETS.md) | Behavioral settings vs. credentials |
| [`08-PIPELINE-SCHEDULER.md`](engine/08-PIPELINE-SCHEDULER.md) | Scheduled/event-driven deterministic work |
| [`09-CHANNELS.md`](engine/09-CHANNELS.md) | Reachability from the outside world |
| [`10-ACCESS-CONTROL.md`](engine/10-ACCESS-CONTROL.md) | Whitelist + human approval gates |
| [`11-EXTENSIBILITY.md`](engine/11-EXTENSIBILITY.md) | Skills, plugins, MCP — adding capability without growing the core |

## Cross-cutting standards (security, cost, reliability, observability, context, permissions)

See [`docs/standards/`](standards/) — also one file per concern:
[`SECURITY.md`](standards/SECURITY.md), [`COST.md`](standards/COST.md),
[`RELIABILITY.md`](standards/RELIABILITY.md),
[`OBSERVABILITY.md`](standards/OBSERVABILITY.md),
[`CONTEXT_MANAGEMENT.md`](standards/CONTEXT_MANAGEMENT.md),
[`PERMISSIONS.md`](standards/PERMISSIONS.md).

## The core rule (unchanged)

Every file in `docs/engine/` and `docs/standards/` is completely
business-agnostic — no franchises, no Agent A/B, no product-specific
vocabulary. That content lives in `docs/ARCHITECTURE.md`, which consumes
everything specified here. **The test for any future change:** if a new
agent can be built by registering new tools/channels/profiles into these
existing interfaces, nothing in `docs/engine/` or `docs/standards/`
should need to change — see `docs/engine/00-OVERVIEW.md`'s closing
section for the precise test.
