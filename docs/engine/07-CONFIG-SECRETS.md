# 07 — Config & Secrets

**Problem this subsystem solves:** every profile needs its own behavioral
settings and its own credentials, without secrets ending up in version
control and without behavioral settings scattered across ad hoc
environment variables.

## Component diagram

```mermaid
flowchart TB
    subgraph PROFILE["One profile directory"]
        CFG["config.yaml<br/>(behavioral settings)"]
        ENV[".env<br/>(credentials ONLY)"]
    end

    LOADER["Config Loader<br/>(runs once, at process start)"]
    RUNTIME["Runtime config object<br/>(in-memory, this profile only)"]

    CFG --> LOADER
    ENV --> LOADER
    LOADER --> RUNTIME

    style ENV fill:#94331f,stroke:#94331f,color:#ffffff
    style CFG fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
```

**Reading this:** `.env` is colored as the highest-sensitivity box
deliberately — anything landing in it needs handling discipline that
`config.yaml` content does not.

## The split, and why it's load-bearing

| | `config.yaml` | `.env` |
|---|---|---|
| Contains | timeouts, thresholds, feature flags, which tools/channels are enabled, cost ceilings | API keys, tokens, passwords — credentials ONLY |
| Safe to commit/review in git? | Yes | **Never** |
| Safe to log/display in a debug dump? | Yes | **Never** |
| Failure mode if leaked | Non-event (a feature flag is not sensitive) | A real incident |

**Rule:** a setting that could be the subject of a code review comment
("should this timeout be 30s or 60s?") belongs in `config.yaml`. A
setting that unlocks access to something belongs in `.env`. Mixing them
makes both harder to handle correctly — `config.yaml` can be freely
shared for debugging; `.env` must never be.

## Sequence diagram — process start

```mermaid
sequenceDiagram
    participant MAIN as Process start
    participant LOADER as Config Loader
    participant CFG as config.yaml
    participant ENV as .env

    MAIN->>LOADER: load(profile_dir)
    LOADER->>CFG: read behavioral settings
    LOADER->>ENV: read credentials
    LOADER->>LOADER: merge into one runtime object,<br/>for THIS profile only
    LOADER-->>MAIN: RuntimeConfig
    Note over MAIN: this profile's loader never<br/>reads another profile's files —<br/>06-PROFILES.md's isolation applies here too
```

## Cross-references

- Per-run and per-profile cost ceilings are `config.yaml` entries, read
  by this loader: `docs/standards/COST.md` §3.
- Operator deny-list entries (temporarily blocked recipients/franchises)
  are `config.yaml` entries, checked at the same gate as the code-level
  hardline list: `docs/standards/SECURITY.md` §3.
- Why this loader never reaches across profiles: `06-PROFILES.md`.
