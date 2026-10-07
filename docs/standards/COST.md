# Cost Management

**This is an ENGINE-level standard.** Grounded in Hermes's real
`state.db` session-cost columns and prompt-caching discipline, extended
with mechanisms Hermes's own workload shape doesn't need but ours does.

## 1. Why the pipeline shape is structurally cheaper for the same work

```mermaid
flowchart LR
    subgraph CHAT["General chat agent doing this job"]
        T1["turn 1: model call<br/>(full prompt + tools)"]
        T2["turn 2: model call<br/>(full prompt + tools + history)"]
        T3["turn 3: model call<br/>(...)"]
        T1 --> T2 --> T3
    end

    subgraph PIPE["Our pipeline doing the same job"]
        C["COLLECT<br/>0 tokens"]
        A["ANALYZE<br/>0 tokens"]
        R["REASON<br/>1 model call"]
        D["DELIVER<br/>0 tokens"]
        C --> A --> R --> D
    end

    style R fill:#c96442,stroke:#c96442,color:#ffffff
    style T1 fill:#94331f,stroke:#94331f,color:#ffffff
    style T2 fill:#94331f,stroke:#94331f,color:#ffffff
    style T3 fill:#94331f,stroke:#94331f,color:#ffffff
```

**This is not a trick — it's that most of "generate a report" is data
transformation, not reasoning**, and the pipeline shape
(`docs/engine/08-PIPELINE-SCHEDULER.md`) only pays for the part that
actually requires a model. A general chat agent doing the equivalent
multi-step task pays the full prompt+tools+history cost on every
exchange along the way.

## 2. A real per-run cost ledger, modeled on Hermes's own

Hermes's `state.db` tracks, per session: `input_tokens`,
`output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
`actual_cost_usd`, `cost_status` (`estimated`/confirmed),
`pricing_version`.

**We adopt the same fields, per PIPELINE RUN** (not per chat session,
since our unit of work is a run, not an open-ended conversation) — cheap
to add to an existing run record, and gives us the same after-the-fact
auditability Hermes has: what every run actually cost, not just a
dashboard assumption.

## 3. What goes beyond Hermes: a proactive cost ceiling

```mermaid
sequenceDiagram
    participant RUNNER as Pipeline Runner
    participant EST as Cost estimator
    participant REASON as REASON stage
    participant LEDGER as Cost Ledger

    RUNNER->>EST: estimate cost (known prompt tokens<br/>+ configured max output)
    alt estimate exceeds per-run ceiling
        EST-->>RUNNER: over ceiling
        RUNNER-->>RUNNER: FAIL LOUDLY (named error,<br/>alert to operator) — never<br/>silently skip
    else within ceiling
        EST-->>RUNNER: ok
        RUNNER->>REASON: execute
        REASON-->>RUNNER: actual cost
        RUNNER->>LEDGER: record actual cost
        LEDGER->>LEDGER: check rolling monthly total<br/>against profile's ceiling
        alt monthly ceiling exceeded
            LEDGER-->>RUNNER: alert operator
        end
    end
```

**Why this is genuinely new engineering, not a copy of Hermes:** Hermes
is built for a human actively driving a conversation — a runaway cost is
visible to that human in real time, and they can stop it. Our pipelines
run UNATTENDED (cron-triggered), potentially across many profiles at
once. A cost ceiling must be enforced PROACTIVELY (before the call), not
just logged for later review — because there is structurally no human
watching in real time to catch it otherwise.

**Two ceiling levels:**
- **Per-run ceiling:** estimated before the REASON call executes; a run
  that would exceed it fails loudly instead of running.
- **Rolling per-profile monthly ceiling:** sum of actual costs from §2;
  triggers an alert, and optionally a hard stop, before the bill does.

## 4. Prompt caching discipline — identical to Hermes, non-negotiable

`docs/engine/04-SYSTEM-PROMPT.md`'s caching rules apply without
modification: stable tier first, volatile tier last, never rebuilt
mid-conversation.

**One addition specific to our multi-profile shape:**

```mermaid
flowchart TB
    SHARED["ONE byte-identical<br/>stable prompt tier<br/>(same agent TYPE)"]
    P1["Profile 1's first<br/>run today"]
    P2["Profile 2's first<br/>run today"]
    P3["Profile 3's first<br/>run today"]

    SHARED -->|"cache WRITE<br/>(first hit, pays full)"| P1
    SHARED -->|"cache HIT<br/>(warm already)"| P2
    SHARED -->|"cache HIT<br/>(warm already)"| P3

    style P1 fill:#94331f,stroke:#94331f,color:#ffffff
    style P2 fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
    style P3 fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
```

Because every profile running the SAME agent type shares the exact same
stable prompt tier (`docs/ARCHITECTURE.md` §5), the FIRST profile's run
in a time window effectively "pays" the cache-write cost, and every
SUBSEQUENT profile's run in the same window hits a warm cache for that
shared prefix. This is a real, structural cost benefit — a careless
per-profile prompt customization (baking profile-specific data into the
stable tier) would silently destroy it. See
`docs/engine/04-SYSTEM-PROMPT.md`'s rule that profile-specific data
belongs in the volatile tier.

## Cross-references

- Pipeline shape this all depends on: `docs/engine/08-PIPELINE-SCHEDULER.md`.
- System prompt tiering mechanics: `docs/engine/04-SYSTEM-PROMPT.md`.
- Session-store size ceilings as a related cost control:
  `docs/engine/05-SESSION-STORE.md`.
- Observability of actual vs. estimated cost: `OBSERVABILITY.md` §1.
