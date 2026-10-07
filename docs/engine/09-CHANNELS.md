# 09 — Channels

**Problem this subsystem solves:** an agent needs to receive and send
messages through some external surface (messaging platform, email,
webhook) — the loop and pipeline runner must not be coupled to which one.

## Component diagram

```mermaid
flowchart TB
    LOOP["Agent Loop /<br/>Pipeline DELIVER stage"]

    subgraph CH["Channel interface"]
        RECV["receive()"]
        SEND["send()"]
        BULK["send_bulk()"]
        FMT["format()"]
    end

    subgraph ADAPT["Concrete adapter: e.g. WhatsAppChannel"]
        BRIDGE["platform bridge<br/>(vendor-specific)"]
    end

    PLATFORM["External messaging<br/>platform"]

    LOOP --> RECV
    LOOP --> SEND
    LOOP --> BULK
    SEND --> FMT
    BULK --> FMT
    FMT --> ADAPT --> BRIDGE --> PLATFORM
    PLATFORM --> BRIDGE --> ADAPT --> RECV

    style ADAPT fill:#5a7a9a,stroke:#5a7a9a,color:#ffffff
```

## Sequence diagram — a bulk send with per-recipient reporting

```mermaid
sequenceDiagram
    participant CALLER as Caller (tool or DELIVER stage)
    participant CH as Channel
    participant GATE as WhitelistGate
    participant PLATFORM as Platform

    CALLER->>CH: send_bulk([r1, r2, r3], content)
    CH->>GATE: is_allowed(r1)?
    GATE-->>CH: yes
    CH->>GATE: is_allowed(r2)?
    GATE-->>CH: NO
    CH->>GATE: is_allowed(r3)?
    GATE-->>CH: yes
    Note over CH: validated BEFORE sending to ANY of them —<br/>not best-effort with silent partial rejection
    CH->>PLATFORM: send to r1
    PLATFORM-->>CH: delivered
    CH->>PLATFORM: send to r3
    PLATFORM-->>CH: delivered
    CH-->>CALLER: BulkResult{r1: ok, r2: rejected(whitelist), r3: ok}
    Note over CALLER: caller can always tell EXACTLY<br/>who did and didn't receive it
```

## Interface

```python
class Channel(Protocol):
    def receive(self) -> NormalizedMessage: ...
    def send(self, chat_id: str, content: str) -> SendResult: ...
    def send_bulk(self, chat_ids: list[str], content: str) -> BulkResult: ...
    def format(self, markdown: str) -> str: ...
```

## Engineering judgment

- **`format()` is its own method, not inlined into `send()`**, because
  markdown-to-platform-native conversion is real, non-trivial,
  independently-testable logic (real bold vs. literal asterisks, heading
  structure, platform-specific limits) — reused identically across
  `send` and `send_bulk` rather than duplicated or drifting between them.
- **`send_bulk` is NOT a separate code path reimplementing delivery** —
  it's `send` applied per-recipient, with WHITELIST VALIDATION happening
  for every recipient BEFORE any message goes out to any of them (see
  sequence diagram), and explicit PER-RECIPIENT success/failure
  reporting — never a silent partial failure a caller can't see.
- **A new channel is one new class implementing this interface.** The
  loop, the pipeline runner, and every existing agent remain completely
  unaware a new channel was added — this is the concrete proof of the
  "add capability without touching the engine" promise for the
  reachability dimension specifically.

## Cross-references

- `WhitelistGate` contract (checked here, specified fully in):
  `10-ACCESS-CONTROL.md`.
- Why whitelist validation happens at THIS boundary, not just as prompt
  guidance: `docs/standards/SECURITY.md` §1.2.
