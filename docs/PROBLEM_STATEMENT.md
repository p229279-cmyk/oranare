# Problem Statement

## 1. Who has the problem

Ornare (and/or a related franchise business the client referred to in
planning notes — exact entity name pending the formal written report)
runs a multi-branch/franchise retail operation. The client's operations
team needs visibility and support across two separate, currently-manual
workflows.

## 2. What's broken today

**Sales & negotiation visibility across franchises.** Each franchise
branch handles its own sales pipeline and negotiations independently.
There is currently no automated, consolidated way to:
- See sales performance and production→delivery status per franchise
- Track where a negotiation stands and what action it needs next
- Get a standing, per-franchise report instead of someone manually
  compiling one
- Reach franchises in bulk over WhatsApp, with proper access control
  (whitelist) and human sign-off before consequential actions are taken

**Client intelligence at first contact.** When a new client/lead reaches
any franchise, staff have no fast, consistent way to look up who this
person/company is, what their current situation looks like, or what
story would help staff understand how to serve them — this currently
depends on individual staff knowledge or ad hoc research, not a
repeatable process.

## 3. Why this matters (business impact, inferred — confirm against formal report)

- Deals stall silently because nobody is systematically tracking
  negotiation stage/action across franchises.
- Franchise-level performance isn't visible without manual compilation,
  so problems surface late.
- Client-facing staff go in with less context than they could have,
  weakening the first interaction with a prospective client.
- None of this scales by hand past a handful of franchises — which is
  the explicit reason this is being built as a real harness rather than
  N more hand-wired agents.

## 4. Why now

The client has an existing, working proof of concept: a 5-agent Hermes-
based system (Pulse, Scout, Rapid, Forge, Sentry) already automating
showroom sales reporting, competitor research, quoting, meeting
intelligence, and partner-firm health monitoring for one operation. That
system proved the pattern works. The client now wants the SAME kind of
automation applied to a franchise network, at a scale the original
hand-built system was never designed for.

## 5. What is explicitly NOT the problem being solved right now

- This is not a general-purpose CRM replacement.
- This is not solving for arbitrary new agent types — only the two
  described (Agent A, Agent B) are in scope for this 10-day build.
- This is not solving cross-franchise/head-office rollup reporting
  unless the formal report confirms it's needed (see
  `docs/ARCHITECTURE.md` §9, Open Questions).

## 6. Status of this document

Written from: (a) two photographed handwritten planning-note pages, (b)
a verbal walkthrough of those notes, (c) direct knowledge of the
existing Ornare system this is modeled on. **Not yet validated against
the client's formal written report.** Every inferred claim above should
be checked against that report when it arrives; §9 of
`docs/ARCHITECTURE.md` tracks the specific open questions.
