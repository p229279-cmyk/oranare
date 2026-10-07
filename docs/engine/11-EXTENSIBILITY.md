# 11 — Extensibility (Skills, Plugins, MCP)

**Problem this subsystem solves:** new capability must be addable at the
EDGES of the engine, without growing the core loop or its always-sent
tool schemas (`03-TOOLS.md`'s footprint cost is real and recurring).

## Component diagram — the footprint ladder

```mermaid
flowchart TB
    NEED["new capability needed"]

    Q1{"can existing<br/>code/tools do it?"}
    Q2{"is it 'how to do X'<br/>guidance, not code?"}
    Q3{"does it only sometimes<br/>apply (conditional)?"}
    Q4{"does it bundle its own<br/>tools + logic as a unit?"}
    Q5{"does an MCP server<br/>already exist for it?"}

    A1["extend existing code"]
    A2["write a Skill"]
    A3["check_fn-gated Tool"]
    A4["write a Plugin"]
    A5["use the existing<br/>MCP server"]
    A6["new CORE tool<br/>(last resort)"]

    NEED --> Q1
    Q1 -->|"yes"| A1
    Q1 -->|"no"| Q2
    Q2 -->|"yes"| A2
    Q2 -->|"no"| Q3
    Q3 -->|"yes"| A3
    Q3 -->|"no"| Q4
    Q4 -->|"yes"| A4
    Q4 -->|"no"| Q5
    Q5 -->|"yes"| A5
    Q5 -->|"no"| A6

    style A6 fill:#94331f,stroke:#94331f,color:#ffffff
    style A1 fill:#4a8a5a,stroke:#4a8a5a,color:#ffffff
```

**Reading this:** the ladder is a decision tree, not a menu — walk it
top to bottom, stop at the first "yes." The last rung is colored red
deliberately: it's the most expensive option (paid for on every single
model call, forever, per `03-TOOLS.md`) and should be rare.

## The three mechanisms, precisely

- **Skills** — markdown procedural knowledge, loaded into context ON
  DEMAND (by keyword/explicit reference), not compiled into code and not
  a permanent tool-schema cost. Used for "how to do X" guidance an agent
  should follow without that guidance costing a permanent slot in the
  core tool schema.
- **Plugins** — Python modules that register new tools/adapters at
  startup, through the SAME `ToolRegistry`/`Channel` interfaces already
  specified in `03-TOOLS.md`/`09-CHANNELS.md`. A plugin never reaches
  into the loop's internals — it only ever calls the same `register()`
  entry points any other tool/channel uses.
- **MCP (Model Context Protocol)** — treated as a "buy," not a "build":
  for an integration where an existing MCP server already exists, use
  the official client rather than hand-writing the integration. Only
  hand-write a plain `Tool` when no MCP server exists for that need.

## Sequence diagram — adding capability without touching the engine

```mermaid
sequenceDiagram
    participant DEV as Developer (future "add agent #3" task)
    participant PLUGIN as New plugin module
    participant REG as ToolRegistry (existing)
    participant ENGINE as Engine core (everything in 01-10)

    DEV->>PLUGIN: write new_capability.py
    PLUGIN->>REG: register(new_tool) [at import time]
    Note over ENGINE: zero files in docs/engine/<br/>or their corresponding code changed
    REG-->>DEV: new_tool is now callable by<br/>whichever agent's registry<br/>it was registered into
```

**This diagram is the direct, concrete proof of the standing requirement
that drove this whole document set: a new agent is a new plugin/profile/
prompt — never a change to the engine itself.**

## Cross-references

- The registry this all plugs into: `03-TOOLS.md`.
- The channel interface plugins can also extend: `09-CHANNELS.md`.
- Why the ladder exists (recurring token cost of every core tool):
  `docs/standards/COST.md` §2.1 and `03-TOOLS.md`'s footprint discussion.
