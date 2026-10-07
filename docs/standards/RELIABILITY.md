# Reliability

**This is an ENGINE-level standard.** Grounded in Hermes's real
`error_classifier.py` (`FailoverReason`, ~20 distinct failure types each
mapped to a DIFFERENT recovery strategy), scoped to the failure modes
this engine can actually encounter, extended with a concern Hermes's
workload shape doesn't have.

## 1. Classified failure handling — the core principle

```mermaid
flowchart TB
    ERR["API error occurs"]
    CLASSIFY{"classify the<br/>failure type"}

    RATE["rate limit"]
    SERVER["server error 5xx"]
    CTX["context too large"]
    TIMEOUT["timeout"]
    AUTH["auth failure"]
    BADREQ["deterministic 400"]

    R1["jittered backoff, retry"]
    R2["backoff, retry, bounded attempts"]
    R3["compress ANALYZE output<br/>further, don't blind-retry"]
    R4["rebuild connection, retry once"]
    R5["ABORT, alert operator —<br/>never retry with same bad cred"]
    R6["ABORT immediately, log<br/>exact payload — retrying an<br/>identical malformed request<br/>never succeeds"]

    ERR --> CLASSIFY
    CLASSIFY --> RATE --> R1
    CLASSIFY --> SERVER --> R2
    CLASSIFY --> CTX --> R3
    CLASSIFY --> TIMEOUT --> R4
    CLASSIFY --> AUTH --> R5
    CLASSIFY --> BADREQ --> R6

    style R5 fill:#94331f,stroke:#94331f,color:#ffffff
    style R6 fill:#94331f,stroke:#94331f,color:#ffffff
    style R1 fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
    style R2 fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
```

**The underlying principle, stated plainly: retrying is only correct
when the retry has a real chance of succeeding.** A deterministic
failure (bad request shape, permanently revoked auth) retried blindly
just burns cost and time for a guaranteed-identical result. Hermes's
classifier exists specifically to tell these apart — so does ours, scoped
to the strict subset of failure modes our narrower engine can actually
hit (we don't have Hermes's full surface of 20+ platforms/providers, so
our table is intentionally shorter, not less rigorous).

## 2. Per-recipient failure reporting (bulk operations)

Already specified structurally in `docs/engine/09-CHANNELS.md` — a bulk
send reports EVERY recipient's outcome individually, never silently
dropping a failed one from the result. Restated here as a reliability
property: a caller must always be able to answer "did recipient X
actually get this" with certainty, not an assumption.

## 3. No partial delivery, ever

```mermaid
stateDiagram-v2
    [*] --> Reasoning
    Reasoning --> Delivering: REASON succeeded
    Reasoning --> Failed: REASON failed
    Delivering --> Delivered
    Failed --> [*]
    Delivered --> [*]

    note right of Failed
        There is NO path from a failed
        Reasoning state to Delivering.
        Structurally impossible, not
        just avoided by convention.
    end note
```

Already specified in `docs/engine/08-PIPELINE-SCHEDULER.md`'s state
machine — restated here because it's as much a reliability guarantee (no
half-correct report ever reaches anyone) as a design principle.

## 4. Idempotent re-runs — a concern Hermes's shape doesn't have

```mermaid
sequenceDiagram
    participant INFRA as Scheduling infrastructure
    participant RUNNER as Pipeline Runner
    participant LEDGER as Run Ledger

    INFRA->>RUNNER: run(run_id=X)
    RUNNER->>RUNNER: complete, deliver
    RUNNER->>LEDGER: mark X delivered
    Note over INFRA: infra restarts a missed job,<br/>re-triggers the SAME run_id
    INFRA->>RUNNER: run(run_id=X) [retry]
    RUNNER->>LEDGER: already delivered?
    LEDGER-->>RUNNER: yes
    RUNNER-->>INFRA: no-op
```

Every pipeline run is identified by a `run_id`
(`docs/TECHNICAL_SPEC.md` §3). A run with the same `run_id` re-executed
(e.g. a scheduler retry after a transient infra failure) must NOT
produce a duplicate delivery — the DELIVER stage checks whether this
`run_id` already successfully delivered before sending again.

**Why this is genuinely new, not a copy of Hermes:** our pipelines are
unattended and may be retried by infrastructure outside the agent's own
control (a scheduler restarting a missed job). A human-driven Hermes
chat doesn't have this failure mode in the same way — there's always a
human in the loop who would notice a duplicate response.

## 5. Approval timeout/rejection as first-class terminal states

An `ApprovalGate` request (`docs/engine/10-ACCESS-CONTROL.md`) that is
rejected, edited, or never resolved must leave the pipeline run in a
clearly terminal state — never silently retried as if nothing happened,
never silently treated as accepted. This is the same "no ambiguous
intermediate state" discipline as §3 above, applied to the
human-in-the-loop boundary specifically.

## Cross-references

- Failure classification lives alongside the provider call:
  `docs/engine/02-MODEL-PROVIDER.md`.
- Pipeline state machine this all enforces against:
  `docs/engine/08-PIPELINE-SCHEDULER.md`.
- Observability of failure reasons (for post-incident review):
  `OBSERVABILITY.md` §1.
