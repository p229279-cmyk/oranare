# Technical Specification

Companion to `docs/PRD.md` (what/why) and `docs/ARCHITECTURE.md`
(system shape, interfaces). This document specifies exact data shapes,
schemas, and contracts precise enough to implement against. Updated as
each day's work lands — treat anything not yet built as a spec, not a
guarantee.

---

## 1. Directory layout (target, built incrementally Days 2–5)

```
oranare-harness/
├── agent/              # core loop, model provider, system prompt, session store, profiles
├── tools/              # tool registry + tool implementations
├── channels/           # Channel interface + WhatsAppChannel adapter
├── cron/               # Pipeline runner / scheduler
├── skills/             # markdown procedural knowledge (as needed)
├── plugins/            # pluggable capability modules (as needed)
├── web/                # (not in 10-day scope; placeholder only)
├── docs/                # this file + PRD + ARCHITECTURE + PROBLEM_STATEMENT
├── profiles/
│   ├── orchestrator/
│   │   ├── config.yaml
│   │   ├── .env
│   │   └── sessions.db
│   └── franchises/
│       ├── <franchise-id>/
│       │   ├── config.yaml
│       │   ├── .env
│       │   ├── sessions.db
│       │   └── whatsapp/        # pairing/session state
│       └── registry.json        # FranchiseRegistry — see §4
```

## 2. Franchise profile record (FranchiseRegistry entry)

```json
{
  "franchise_id": "branch-sao-paulo",
  "display_name": "São Paulo",
  "status": "live",
  "whatsapp_number": "+55...",
  "created_at": "2026-10-07T23:00:00Z",
  "profile_dir": "profiles/franchises/branch-sao-paulo"
}
```

`status` enum: `pending_pairing | live | suspended`. A franchise is never
visible to the router as `live` until WhatsApp pairing (the last,
non-rollback-able provisioning step) has succeeded.

## 3. Pipeline context (shared across COLLECT/ANALYZE/REASON/DELIVER)

```python
@dataclass
class PipelineContext:
    franchise_id: str | None   # None for Agent B (not franchise-scoped)
    run_id: str
    started_at: float
    data: dict                 # stage-to-stage payload, grows as stages run
    errors: list[str]          # non-fatal issues surfaced to DELIVER
```

Each stage receives the context, returns a (possibly mutated) context.
A stage that fails fatally raises; the pipeline runner is responsible for
not leaving a half-delivered report (no partial DELIVER on a failed
REASON, matching the "never retry a half-emitted stream" discipline from
the harness curriculum's Day 3).

## 4. Agent A — REASON stage output schema (draft, pending real data shape)

```json
{
  "franchise_id": "branch-sao-paulo",
  "period": "2026-10-01..2026-10-07",
  "headline": "string, 1-2 sentences, grounded only in ANALYZE output",
  "sales_performance": {
    "total": "number, from ANALYZE, never invented",
    "wow_change_pct": "number or null"
  },
  "production_to_delivery": {
    "flagged_count": "integer",
    "items": [{"id": "string", "stage": "string", "days_in_stage": "integer"}]
  },
  "negotiations": [
    {
      "deal_id": "string",
      "stage": "string",
      "recommended_action": "string",
      "requires_approval": "boolean"
    }
  ],
  "recommended_actions": ["string", "..."]
}
```

Hard rule (same as every Ornare REASON prompt): every number in this
output must trace back to real ANALYZE output. No padding to a fixed
structure; omit a section if ANALYZE produced nothing for it, rather than
inventing content to fill the schema.

## 5. Agent B — REASON stage output schema (draft)

```json
{
  "client_query": "string, the input name/company",
  "match_confidence": "none | low | medium | high",
  "summary": "string — empty or hedged if match_confidence is none/low",
  "sources": [{"url": "string", "title": "string"}],
  "story": "string — the synthesized profile, grounded only in sources above"
}
```

Hard rule (same discipline as Scout/Sentry): default `match_confidence`
to `"none"` unless there is real, explicit evidence tying a search result
to the actual client in question. Name collisions must not produce a
false match.

## 6. WhatsApp channel contract

```python
class WhatsAppChannel:
    def receive(self) -> NormalizedMessage: ...
    def send(self, chat_id: str, content_markdown: str) -> SendResult: ...
    def send_bulk(self, chat_ids: list[str], content_markdown: str) -> BulkResult: ...
```

- `send`/`send_bulk` run `content_markdown` through the proven markdown-
  to-WhatsApp formatter (real bold, heading box, no raw asterisks) before
  transmission — reusing the already-debugged conversion logic from the
  original Ornare build, not reimplementing it.
- `send_bulk` checks every `chat_id` against `WhitelistGate` BEFORE
  sending to any of them — a bulk send is all-or-validated, not
  best-effort with silent partial rejection.
- `BulkResult` reports per-recipient success/failure explicitly; a caller
  must be able to tell exactly who did and didn't receive the message.

## 7. WhitelistGate contract

```python
class WhitelistGate:
    def is_allowed(self, franchise_id: str, chat_id: str) -> bool: ...
```

Checked at the tool-execution boundary (inside the tool handler, not just
as prompt guidance) for every tool capable of sending a WhatsApp message
or performing a negotiation action — per Day 2's blast-radius principle.

## 8. ApprovalGate contract

```python
class ApprovalGate:
    def request(self, franchise_id: str, action_summary: str, payload: dict) -> ApprovalRequestId: ...
    def resolve(self, request_id: ApprovalRequestId, decision: Literal["accept","reject","edit"], edit_payload: dict | None) -> None: ...
```

Mirrors Rapid's proven numbered-reply flow exactly (1=Accept/2=Reject/
3=Edit). A tool marked `requires_approval=True` at registration never
executes directly — it always routes through `request()` first and only
runs after a matching `resolve(..., "accept")`.

## 9. Error handling conventions

- Every custom exception type is named for what broke, not generic
  (`FranchiseProvisioningError`, `TranscriptTooLargeError`,
  `WhitelistRejectedError` — not bare `Exception`/`ValueError` at
  application boundaries).
- No silent truncation anywhere a size ceiling exists (Day 6 principle)
  — raise a named error, let the caller decide.
- No tool call ever raises an uncaught exception back into the agent
  loop — tool execution always returns `is_error: true` with a message,
  per Day 2's tool-design discipline.

## 10. Testing conventions

- Every subsystem gets a real test proving its core invariant (not just
  "it runs") — e.g. the franchise isolation test from
  `docs/ARCHITECTURE.md`'s success metrics, the role-alternation
  round-trip test (Day 6 pattern), the match-confidence-defaults-to-none
  test for Agent B.
- No live API key is assumed to be present in the dev/build environment;
  logic that doesn't require a live model call must be fully testable
  without one (same standard upheld throughout the harness curriculum).

## 11. Open/unconfirmed items

Tracked centrally in `docs/ARCHITECTURE.md` §9 — do not duplicate here;
update that section when the formal report resolves an item, and update
this spec's affected sections (§4 and §6's sales-data source assumption,
primarily) in the same change.
