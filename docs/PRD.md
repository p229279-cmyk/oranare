# Product Requirements Document (PRD)

**Status:** Draft, based on inferred requirements pending the client's
formal written report. Sections marked **[CONFIRM]** need validation once
that report arrives. See `docs/ARCHITECTURE.md` §9 for the full open-
questions list this PRD depends on.

---

## 1. Summary

Build a harness-based system delivering two new automated agents over
WhatsApp:

- **Agent A** — one fully isolated instance per franchise, handling sales
  data collection, negotiation tracking, and reporting for that franchise.
- **Agent B** — one shared instance for client lookup/intelligence,
  usable by any franchise.

## 2. Goals

| Goal | How we'll know it's met |
|---|---|
| Each franchise gets automated sales/negotiation reporting | A franchise can request (or receive on schedule) a report containing sales performance + production→delivery status, with real data, not placeholders |
| Negotiation stages/actions are visible, not silent | Agent A can state what stage a tracked negotiation is in and what action is next, for at least one real franchise's data |
| Franchises can be added without hand-wiring | A new franchise can be provisioned (isolated WhatsApp number, isolated data) via the provisioning flow, not by manually repeating setup steps |
| Bulk WhatsApp messaging works safely | A message can be sent to multiple whitelisted recipients, and a non-whitelisted recipient is correctly rejected |
| Consequential actions require human sign-off | At least one Agent A action (e.g. sending a bulk negotiation message) goes through the same numbered-reply approval flow already proven in the original Ornare system (Rapid) before executing |
| New clients get an automated lookup/story | Given a client name/company, Agent B returns a synthesized profile grounded in real sources (web search, not fabricated) |

## 3. Non-goals (explicitly out of scope for this build)

- A general CRM or data warehouse.
- Cross-franchise/head-office rollup views — **[CONFIRM]** only added if
  the formal report requires it.
- A web dashboard UI for this product (the harness curriculum's Day 24
  pattern exists if this becomes a later requirement; not in the 10-day
  scope).
- Any third agent beyond A and B.
- Multi-language support beyond what the underlying model already
  provides.

## 4. Users

- **Franchise staff** — receive reports and bulk messages on their
  franchise's WhatsApp number; interact with Agent A for sales/
  negotiation status.
- **Client-facing staff at any franchise** — trigger Agent B to look up a
  new client.
- **An operator/admin** — provisions new franchises, manages whitelists,
  approves consequential actions.

## 5. Requirements detail

### 5.1 Agent A — Franchise Sales & Negotiation Intelligence

**[CONFIRM — source of sales data]** Current assumption: each franchise's
sales data arrives as a file export or similar structured source, mirroring
how Pulse ingests showroom CSVs today in the original Ornare system. The
exact source (spreadsheet export, CRM API, manual upload) is unconfirmed.

Functional requirements:
- FR-A1: Collect sales records for one franchise, on a schedule or on
  demand.
- FR-A2: Analyze records into deal stage, stalled-deal flags, and
  negotiation-action recommendations.
- FR-A3: Produce one report per franchise containing sales performance
  and production→delivery indicators.
- FR-A4: Deliver the report over that franchise's own WhatsApp number.
- FR-A5: Support bulk WhatsApp messaging to a whitelisted recipient set.
- FR-A6: Reject any send attempt to a non-whitelisted recipient.
- FR-A7: Require human approval before executing any action flagged as
  consequential (e.g. a bulk send, a negotiation action) — numbered-reply
  flow (1=Accept/2=Reject/3=Edit), matching the existing proven pattern.

**[CONFIRM]**: exact definition of "stale" negotiation and the action
taxonomy ("actions of negotiation") — currently undefined.

### 5.2 Agent B — Client Lookup / Intelligence

- FR-B1: Accept a client name/company as input, from any franchise.
- FR-B2: Perform a real web search (and any available internal lookup)
  — no fabricated results; low/no confidence must be stated plainly
  rather than invented, matching the existing Scout/Sentry discipline.
- FR-B3: Synthesize a "story" — a profile document combining what was
  found, useful for staff preparing to engage that client.
- FR-B4: Deliver the result back to the requesting franchise's channel.

**[CONFIRM]**: exact expected depth/format of the "story," and whether it
should be stored for later reference per client (vs. generated fresh each
time).

### 5.3 Provisioning & platform requirements

- FR-P1: An operator can provision a new franchise profile: isolated
  config, isolated session store, its own WhatsApp number pairing.
- FR-P2: A franchise name is validated/normalized before any filesystem
  or config operation touches it.
- FR-P3: A failed WhatsApp pairing leaves the franchise in a clearly
  marked pending state, not silently "live."
- FR-P4: Each franchise's data is provably isolated from every other
  franchise's data (automated test, not just architectural claim).

## 6. Success metrics (initial, to be refined against the formal report)

- At least 2 franchise profiles provisioned and running Agent A with real
  (or realistic sample) data by Day 7.
- Agent B returns a real, evidence-grounded lookup by Day 8.
- End-to-end WhatsApp delivery verified for both agents by Day 9.
- Zero cross-franchise data leakage, proven by an automated isolation
  test (same discipline as Day 7's lab).

## 7. Timeline

See `docs/ARCHITECTURE.md` §8 for the full day-by-day build plan (10
days total, started Day 1 with architecture).

## 8. Dependencies / risks

- **Risk:** formal report may change scope materially once it arrives —
  mitigated by building infrastructure (Days 1–5) in a way that doesn't
  assume unconfirmed specifics, per `docs/ARCHITECTURE.md`'s open
  questions.
- **Dependency:** WhatsApp pairing requires real phone numbers per
  franchise — provisioning speed is bounded by how fast numbers can be
  obtained/paired, not by the software itself.
- **Risk:** sales-data source is unconfirmed; Day 6–7's COLLECT stage may
  need rework once the real source is known.
