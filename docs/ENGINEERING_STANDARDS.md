# Engineering Standards — Security, Cost, Reliability, Observability, Context

**This is an ENGINE-level document** (same rule as `ENGINE.md`: no
business-specific content). It governs every subsystem in `ENGINE.md` and
every agent built on top of it. If a product-specific limit is needed
(e.g. "franchise X gets a $50/month ceiling"), that value lives in
`ARCHITECTURE.md` / that profile's config — the MECHANISM for enforcing
any such limit lives here.

**Why this document exists:** the goal stated for this build is not
"copy Hermes" — it's "match Hermes's real engineering rigor where that
rigor is the correct bar, and beat it on cost/security where our actual
structural situation allows it, without ever trading away correctness
to get there." This document is honest about which of those two cases
applies to each decision below, and shows the reasoning either way —
not just the conclusion.

---

## 0. The one structural fact that changes everything

Hermes is a **general-purpose, long-running conversational agent**. A
user might chat with it for hours, across days, using any of ~50+ tools,
through 20+ platforms, with no fixed job. That generality is expensive by
necessity: every conversation needs the full tool schema available
(footprint cost), a real memory/compression system for open-ended
history, and defenses against an open-ended range of things a user might
ask it to do.

**Every agent we build on this engine is the opposite shape: a narrow,
known-job pipeline** (COLLECT→ANALYZE→REASON→DELIVER, `ENGINE.md` §8),
triggered by a schedule or a bounded inbound request, with a SMALL, KNOWN
set of tools, running for seconds to minutes, not hours to days.

This is not a limitation to work around — **it is the single biggest
lever we have for beating Hermes on cost and security**, and the rest of
this document is mostly about using that lever deliberately rather than
copying Hermes's general-purpose machinery where it isn't needed. Where
our agents DO need something Hermes-shaped (e.g. a real back-and-forth
WhatsApp conversation with a staff member), we use the Hermes-proven
pattern exactly, because at that point we have the same problem Hermes
has, and Hermes already solved it well.

---

## 1. Security

### 1.1 Minimal tool surface, enforced per agent, not "everything available"

**Decision:** no agent on this engine gets a default toolset. Every tool
an agent can call is explicitly registered into THAT agent's
`ToolRegistry` instance (`ENGINE.md` §3) — there is no shared "all
tools" registry an agent could accidentally inherit access to.

**Why this beats Hermes's default posture, for our case specifically:**
Hermes must support an open-ended range of user requests, so a large
available toolset is the correct trade-off for it — the cost is paid in
footprint, but the capability is the product. Our agents have a KNOWN,
narrow job (e.g. Agent A never needs a browser tool, a shell tool, or a
code-execution tool — it needs: read sales data, query negotiation
state, send/receive WhatsApp, request approval). Giving it anything
beyond that is pure downside: more attack surface, more token cost per
call, zero added capability for the job it actually has. This is
Hermes's own footprint-ladder principle (`ENGINE.md` §11), applied more
aggressively than Hermes applies it to itself, because our per-agent job
is narrower than Hermes's own.

**Concrete rule:** before registering a tool to an agent, ask "does this
specific agent's specific job require this," not "could this be useful."
If the formal report later reveals a real need, add the tool then — this
is the same YAGNI discipline already applied to the architecture
(`ARCHITECTURE.md` §9).

### 1.2 Blast-radius tiering, explicit per tool

Every tool registered anywhere in the system gets an explicit blast-
radius tier at registration time, not an implicit one inferred later:

| Tier | Examples in this system | Rule |
|---|---|---|
| **Read-only** | query sales data, read negotiation state, web search (Agent B) | No approval gate needed |
| **Reversible write** | draft a report, draft a message (not yet sent) | No approval gate needed |
| **Consequential, single-recipient** | send one WhatsApp message to one known, already-whitelisted contact | Whitelist check mandatory; approval gate optional per product config |
| **Consequential, bulk/irreversible** | bulk WhatsApp send, any negotiation action, franchise provisioning | Whitelist check AND `ApprovalGate` mandatory, no exceptions, not configurable off |

This is Day 2's blast-radius concept (`ENGINE.md` §3) turned into an
enforced table instead of a general principle — every new tool gets
placed in this table before it's registered, and the bottom tier's gates
are not something a product config can disable.

### 1.3 A hardline layer, same two-tier shape as Hermes, scoped to what we actually run

Hermes's real hardline pattern (`tools/approval.py`,
`detect_hardline_command()`) is genuinely good design: a CODE-LEVEL,
never-bypassable blocklist for truly catastrophic operations, PLUS a
user-editable deny-list layered on top for operator-specific rules —
both checked before any approval-bypass mode could skip them.

**We adopt the same two-tier shape, scoped down:** our agents don't run
arbitrary shell commands, so a shell-command blocklist isn't the right
content — but the SHAPE transfers directly:
- **Hardline tier (code, never bypassable):** e.g. a tool can never send
  to a recipient outside its franchise's registered WhatsApp number
  range; a tool can never read another franchise's `profiles/` directory
  (enforced by which `SessionStore`/`ProfileManager` instance the running
  agent was constructed with, per `ENGINE.md` §6 — defense in depth, not
  just "shouldn't happen").
- **Operator deny-list tier (config, editable without a code change):**
  e.g. a specific recipient number temporarily blocked, a specific
  franchise temporarily suspended — lives in that profile's `config.yaml`
  (`ENGINE.md` §7), checked at the same gate as the hardline tier.

### 1.4 Credential and data isolation — already specified, restated as a security property

`ENGINE.md` §6's directory-per-profile isolation is, among other things,
a SECURITY boundary, not just an organizational one: a compromised or
misbehaving Agent A instance for franchise X cannot read franchise Y's
credentials or session history, because they are not reachable from the
process's own filesystem view of "its" profile directory — not because
of a runtime permission check that could have a bug.

### 1.5 Prompt-injection awareness for the specific tools we do register

Any tool whose result text the model will read back (e.g. Agent B's web
search results, Agent A's ingested sales-data free-text fields) is a real
prompt-injection surface — instructions embedded in that content are
untrusted. **Rule:** tool RESULTS are never treated as instructions, only
as data to reason about — this is enforced by never concatenating raw
external content into the system prompt (which the model weighs more
heavily) and always keeping it in tool-result turns, following the same
discipline Hermes itself documents for handling untrusted page/search
content.

---

## 2. Cost management

### 2.1 Why our pipeline shape is structurally cheaper than a chat agent for the same work

A chat agent (Hermes's own shape) re-sends system prompt + full tool
schema + growing history on every turn of an open-ended conversation.
Our pipeline shape (`ENGINE.md` §8) makes exactly ONE model call
(REASON) per run — COLLECT/ANALYZE/DELIVER cost zero tokens, by
construction, because they're plain code. **This is the single largest
cost advantage we have over a general chat agent doing the same
reporting job**, and it's not a trick — it's simply that most of what
"generate a franchise report" requires is data transformation, not
reasoning, and we only pay for the part that's actually reasoning.

### 2.2 A real per-run cost ledger, modeled on Hermes's own session-cost columns

Hermes's `state.db` tracks, per session: `input_tokens`,
`output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
`actual_cost_usd`, `cost_status` (`estimated`/confirmed),
`pricing_version`. **We adopt the same fields, per pipeline run** (not
per chat session, since our unit of work is a run, not a conversation) —
this is cheap to build (it's a few extra columns on an existing
`PipelineContext`/run record) and gives us exactly what Hermes has:
after-the-fact auditability of what every run actually cost, not just an
estimate baked into a dashboard assumption.

### 2.3 What we build that Hermes does NOT need, because our workload shape is different: a per-run cost ceiling, enforced BEFORE the call, not just logged after

Hermes is built for a human actively driving a conversation — a runaway
cost is visible to that human in real time and they can stop it. Our
pipelines run UNATTENDED (cron-triggered), potentially across dozens of
franchises. **A cost ceiling must be enforced proactively, not just
logged for later review:**
- Each pipeline run estimates its REASON-stage call cost BEFORE making
  it (known: prompt token count is deterministic once ANALYZE has run;
  only output length is estimated, conservatively, from a configured max).
- If the estimate exceeds that profile's configured per-run ceiling, the
  run fails loudly (a named error, delivered to the operator — not a
  silent skip) rather than executing an unexpectedly expensive call.
- A rolling per-profile monthly ceiling (sum of actual costs from §2.2)
  triggers an alert, and optionally a hard stop, before the bill does.

This is genuinely new engineering beyond what Hermes does for itself,
because Hermes's cost-control problem (one human, one conversation,
real-time visibility) is different from ours (N unattended agents,
running on a schedule, nobody watching in real time). The fields are
copied from Hermes; the proactive ceiling is invented for our shape.

### 2.4 Prompt caching discipline — identical to Hermes, non-negotiable

`ENGINE.md` §4's caching rules apply without modification. One addition
specific to our multi-franchise shape: because every franchise running
Agent A shares the exact same STABLE prompt tier (`ARCHITECTURE.md` §5),
the FIRST franchise's run each day effectively "pays" the cache-write
cost and every subsequent franchise's run in the same window hits a
warm cache for that shared prefix — a real, structural cost benefit of
keeping the stable tier byte-identical across franchises that a careless
per-franchise prompt customization would silently destroy.

---

## 3. Reliability

### 3.1 Classified, not generic, failure handling — same shape as Hermes's `FailoverReason`

Hermes's `error_classifier.py` maps ~20 distinct failure types to ~20
distinct recovery strategies (rate limit → backoff then rotate; context
overflow → compress, don't retry; content-policy-blocked → fail fast,
don't retry unchanged; SSL cert failure → fail fast with guidance, don't
burn retries on a deterministic failure). **We adopt this exact
discipline, scoped to the failure modes our engine can actually
encounter** (a strict subset of Hermes's, since we don't have Hermes's
full surface of providers/platforms):

| Failure | Our recovery |
|---|---|
| Rate limit (429) | Jittered backoff, retry |
| Server error (5xx) | Backoff, retry, bounded attempts |
| Context too large | Compress ANALYZE output further before REASON, don't blind-retry |
| Timeout | Rebuild client connection, retry once |
| Auth failure | Abort the run, alert operator — never silently retry with the same bad credential |
| Deterministic 400 (bad request) | Abort immediately, log the exact payload shape — retrying an identical malformed request wastes a call and never succeeds |
| WhatsApp send failure (per recipient, in `send_bulk`) | Reported individually per `ENGINE.md` §9 — never silently dropped from a bulk result |

The underlying principle, stated plainly: **retrying is only correct
when the retry has a real chance of succeeding.** A deterministic failure
(bad request shape, permanently revoked auth) retried blindly just burns
cost and time for a guaranteed-identical result — Hermes's classifier
exists specifically to tell these apart, and so does ours.

### 3.2 No partial delivery, ever — already specified in `ENGINE.md` §8, restated as a reliability property

A pipeline that fails at REASON must not produce a DELIVER. This is
already an engine-level rule; it's restated here because it's as much a
reliability guarantee (no half-correct report ever reaches a franchise)
as it is a design principle.

### 3.3 Idempotent re-runs

Every pipeline run is identified by a `run_id` (`TECHNICAL_SPEC.md` §3).
**Rule, new for this engine:** a run with the same `run_id` re-executed
(e.g. a cron retry after a transient infra failure) must not produce a
DUPLICATE delivery — the DELIVER stage checks whether this `run_id`
already successfully delivered before sending again. This matters
specifically because our pipelines are unattended and may be retried by
infrastructure outside the agent's own control (a cron scheduler
restarting a missed job, for instance) — a human-driven Hermes chat
doesn't have this failure mode in the same way, so this is a genuinely
new concern for our shape.

---

## 4. Observability

### 4.1 Structured per-run records, not just logs

Every pipeline run produces one structured record (not scattered log
lines) containing: `run_id`, `profile`/franchise, pipeline name, start/
end time, per-stage duration, the cost ledger (§2.2), final status
(`success`/`failed`/`partial`), and — on failure — the classified failure
reason (§3.1). This is queryable later ("show me every failed run for
franchise X this week") without grepping logs.

### 4.2 No third-party observability SaaS baked into the engine core

Hermes's own stated rule (`AGENTS.md`, quoted in `ENGINE.md` is implied
but worth stating explicitly here): third-party observability/analytics
backends are not core dependencies — they're opt-in integrations at the
edges (a plugin/exporter), never something every deployment is forced to
run or pay for. **We adopt this directly**: the structured run record
(§4.1) is written locally (same SQLite-based discipline as
`SessionStore`, `ENGINE.md` §5) by default; exporting it to an external
observability platform is an optional adapter, not a hard dependency.

### 4.3 A `pending_pairing` / `live` / `suspended` profile status (already specified) IS an observability signal

`TECHNICAL_SPEC.md` §2's franchise status field isn't just provisioning
bookkeeping — it's the first thing an operator should be able to query
to answer "which franchises are actually operational right now," without
needing to inspect individual pipeline run history.

---

## 5. Context management — explicitly different from Hermes, reasoned from first principles

**This is the one area where "do it exactly like Hermes" is the WRONG
default**, and it's worth being precise about why, since the instruction
was to think carefully here rather than copy blindly.

Hermes's context-management problem: a single conversation can run for
hours/days, accumulate a large tool-call history, and must use
compression (`ENGINE.md` §4, the one accepted cache-breaking exception)
to stay within a model's context window while preserving enough history
for the conversation to remain coherent to the user who's been chatting
the whole time.

**Our pipelines mostly don't have this problem, structurally:**

- A pipeline run's REASON stage receives exactly ONE thing as its
  "context": that run's own ANALYZE output — not a growing conversation
  history. There is no multi-hour accumulation to compress, because
  there is no multi-hour conversation. Each run is bounded by
  construction.
- **Where real Hermes-style context management DOES apply to us:** any
  genuine back-and-forth conversation a franchise has with its Agent A
  instance over WhatsApp (e.g. a staff member asking follow-up questions
  about a report) IS a real, potentially-long-running conversation, using
  the engine's normal `SessionStore` + loop (`ENGINE.md` §1/§5) — at
  that point we have Hermes's exact problem and use Hermes's exact
  solution (compression as the one accepted exception). The distinction
  is: **pipeline runs (scheduled, bounded) need no compression strategy
  at all; conversational sessions (user-initiated, open-ended) need
  Hermes's full compression discipline, unmodified.**
- **Where we can do BETTER than a generic compression strategy, because
  our job is narrower:** when a pipeline's ANALYZE output itself is very
  large (e.g. a franchise with thousands of deals), the right move is
  not "compress it the way a long chat gets compressed" — it's "ANALYZE
  should already be producing a SUMMARIZED, bounded structure as its
  output, sized for what REASON actually needs to reason about." This
  pushes the context-management problem upstream into deterministic code
  (cheap, reliable, zero tokens) instead of downstream into the model
  (expensive, lossy). This is a real, available optimization specific to
  our pipeline shape that a general chat agent like Hermes structurally
  cannot take, because Hermes doesn't control the shape of what's being
  discussed the way a pipeline's own ANALYZE stage controls what REASON
  sees.

**Rule, stated plainly:** context management for THIS engine is a
decision made per code path, not one global strategy — bounded pipeline
runs get bounded-by-design context (no compression machinery needed at
all); genuine conversational sessions get Hermes's proven compression
discipline, unmodified, because at that point the problem really is the
same problem.

---

## 6. Permissions management

Summarizing the cross-cutting permission model implied by §1 and
`ENGINE.md` §§3/6/10, stated as one coherent model:

| Layer | Mechanism | Enforced by |
|---|---|---|
| Which tools an agent can even call | Per-agent `ToolRegistry` instance, explicit registration only | `ENGINE.md` §3 |
| Which franchise's data a running agent can reach | Which `SessionStore`/`ProfileManager` instance it was constructed with | `ENGINE.md` §5/§6 |
| Which recipients a send-capable tool can reach | `WhitelistGate`, checked at the tool execution boundary | `ENGINE.md` §10, §1.2 above |
| Which consequential actions require a human | `ApprovalGate`, opt-in per tool via `requires_approval`, mandatory for bulk/irreversible tier | `ENGINE.md` §10, §1.2 above |
| Which operator-level overrides exist | Config-level deny-list, editable without a code change, checked at the same gate as the hardline tier | §1.3 above |

No single layer is trusted alone — a tool that shouldn't exist for an
agent is caught by registration; if it somehow existed, the whitelist
would catch a bad recipient; if that somehow failed, the approval gate
catches a bulk/irreversible action before it executes. This layering
(defense in depth) is deliberate, not redundant — any one layer having a
bug should not be sufficient to cause harm by itself.
