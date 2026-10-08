# 01c — Ornare Harness vs. Hermes: What We Built, What Hermes Built, Why

**Purpose of this file:** a complete, honest, detailed comparison between
our `ModelProvider` + `AnthropicProvider` and Hermes's real equivalent
files — what each one does, HOW each one does it, WHY Hermes needs what
it has, and — the actual point of this file — which of those things we
genuinely need too, and which we don't, with reasons for every single
one. The goal isn't to copy Hermes or to avoid it; it's to understand
Hermes well enough that every decision we make about our own engine is a
real decision, not a guess.

**Read this after:** `01a-model-provider.md`, `01a-model-provider-code-explaination.md`,
`01b-anthropic-adapter.md`, `01b-anthropic-adapter-code-explaination.md`.

---

## Part 1 — What we have done, in plain terms

We built:

- `agent/model_provider.py` — the generic, vendor-agnostic vocabulary
  (`Message`, `ModelResponse`, `StreamEvent`), the `ModelProvider`
  interface, and a failure classifier (`classify_error`) that
  recognizes 6 kinds of failure.
- `agent/adapters/anthropic/provider.py` — the real adapter class,
  `AnthropicProvider`, with two methods: `chat()` (ask once, get one
  full answer) and `stream()` (ask once, get the answer word by word).
- `agent/adapters/anthropic/quirks.py` — a small table of real,
  model-specific facts (currently: max output tokens per model we
  actually use), added after this file's own category C analysis below
  concluded we needed it (not present when this file was first written
  — see the update note under category C).

Both were tested (21 passing tests as of the category-C update) and
both were verified with real, live calls to the actual Anthropic API
using a cheap model (Haiku) — not just mocked.

**Total real logic: roughly 80-120 lines across both files.**

This is correct, working code. It does exactly what it's supposed to
do, cleanly, with no wasted complexity. The question this file answers
is: compared to what a REAL, battle-tested harness (Hermes) does for the
exact same job, what's different, and does that difference matter for
us specifically?

---

## Part 2 — What Hermes's equivalent file actually does

**File:** `/home/ubuntu/.hermes/hermes-agent/agent/anthropic_adapter.py`
(same machine, mirrors `github.com/NousResearch/hermes-agent/blob/main/agent/anthropic_adapter.py`)

**Size: 3,284 lines.** That is roughly **40x the size** of our adapter.
Hermes also has NO separate generic-interface file the way we do —
everything lives in this one file, plus several supporting files:

| File | What it's for |
|---|---|
| `agent/anthropic_adapter.py` (3,284 lines) | The adapter itself — auth, endpoint detection, model quirks, message repair, the actual API call |
| `agent/error_classifier.py` (92,569 bytes) | `FailoverReason` — 25 distinct failure types, `classify_api_error()` |
| `agent/retry_utils.py` (8,224 bytes) | Jittered backoff, parsing `Retry-After` headers, adaptive rate-limit backoff |
| `agent/turn_retry_state.py` (4,980 bytes) | `TurnRetryState` — tracks how many times THIS turn has been retried |
| `agent/model_metadata.py` (166,257 bytes) | Per-model context window size, pricing, capability flags, with disk caching |

Hermes's ~70 top-level functions in `anthropic_adapter.py` group into 6
real categories. Here is each one, explained from first principles so
the "why" is actually understandable — not just a label.

---

### A. Auth — a whole subsystem, not a parameter

**What it is, for anyone who's never thought about this:** when our
code calls Anthropic's API, Anthropic needs to know WHO is asking and
whether they're allowed to. The simplest way to prove that is an API
key — a long secret string you pass with every request. That's what we
do: `AnthropicProvider(api_key="sk-ant-...")`.

**What Hermes does instead/also:** Hermes supports several DIFFERENT
ways a user might be authorized to use Claude, because Hermes is
installed by thousands of different people with different
subscriptions:
- A plain API key (what we use).
- An **OAuth token** — the kind of credential you get when you log in
  through a browser flow, the way "Sign in with Google" works, instead
  of pasting a secret string.
- **Claude Code's own stored login** — if the person already has Claude
  Code (Anthropic's coding CLI) installed and logged in, Hermes can
  reuse THAT login instead of asking for a separate key. It reads this
  from the operating system's secure credential storage (macOS
  Keychain) or a JSON file on disk, and if that login has expired, it
  automatically refreshes it (`refresh_anthropic_oauth_pure`) using a
  standard OAuth technique called PKCE.
- A **pool of possible tokens** — checking several of the above sources
  in order and using whichever one is actually valid right now.

**Why Hermes needs this:** Hermes is a general-purpose tool anyone
downloads and runs on their own machine. It has no idea in advance which
of these the user has, so it has to support all of them, gracefully.

**Do we need this? No — and here's exactly why.** Every one of our
agents runs as ONE Ornare-controlled service, with ONE Anthropic API key
we provision and manage ourselves. There's no "different user with a
different login" scenario — there's no user at all in that sense; it's
our own backend talking to Anthropic on Ornare's behalf. OAuth,
Keychain, Claude Code credential-sharing — none of these solve a problem
we actually have. **This confirms what you suspected: this category is
about personal Claude/Claude-Code subscriptions, not about running a
backend service with its own API key — which is exactly our situation.**

---

### B. Endpoint/vendor detection — Anthropic's API is used by many "compatible" proxies

**What it is, for anyone who's never thought about this:** Anthropic's
"Messages API" format has become popular enough that OTHER companies
build their own AI services that accept requests in the SAME format,
even though they're not Anthropic. Think of it like a universal remote:
several different TV brands agree to respond to the same button layout,
even though they're different TVs inside.

**What Hermes does:** it detects, from the URL being called, whether
it's really talking to Anthropic, or actually talking to Amazon Bedrock,
Microsoft Azure, MiniMax, DeepSeek, Moonshot/Kimi, OpenCode, or Nous's
own hosted service — each of which needs slightly different headers,
slightly different auth, or slightly different request shaping, even
though they all speak "Anthropic-ish."

**Why Hermes needs this:** again — Hermes is installed by many
different people, some of whom route their requests through one of
these alternative providers instead of Anthropic directly (often for
cost or access reasons).

**Do we need this? No.** We talk to Anthropic directly, with our own
key, always. There is no proxy, no aggregator, no alternative backend in
our picture at all. If that ever changed — say, Ornare decided to route
through Bedrock for cost reasons — THAT would be the moment to build
this, as one new concrete concern, not before. Building it now would be
solving a problem we don't have, which is the opposite of what our
`ENGINEERING_STANDARDS.md` discipline asks for.

---

### C. Model-specific quirks — different Claude models behave differently

**What it is, for anyone who's never thought about this:** "Claude" is
not one single thing — it's a family of different model VERSIONS
(Haiku, Sonnet, Opus, each with multiple generations: 3, 3.5, 4, 4.5,
4.6...). Newer versions sometimes support NEW features older versions
don't, and sometimes the way you ASK for a feature changes between
versions. If your code assumes every "Claude model" behaves identically,
it will work fine on one version and then throw a confusing error on
another.

**A real example from Hermes's code**, read directly from the file:

```python
def _supports_adaptive_thinking(model: str) -> bool:
    """Return True for Claude models that use adaptive thinking (4.6+).
    ...only returns False for the explicit legacy list of older Claude
    families that require manual budget-based thinking."""

def _supports_xhigh_effort(model: str) -> bool:
    """Opus 4.7 introduced xhigh as a distinct level between high and max.
    Pre-4.7 adaptive models ... reject xhigh with an HTTP 400."""

def _get_anthropic_max_output(model: str) -> int:
    """Look up the max output token limit for an Anthropic model.
    Uses substring matching ... so date-stamped model IDs
    (claude-sonnet-4-5-20250929) and variant suffixes (:1m, :fast)
    resolve correctly."""
```

In plain words: "thinking" (letting the model reason step-by-step before
answering) works differently depending on the model generation. Newer
models accept a setting called `xhigh` effort; older ones will error out
if you send it. Even the maximum number of tokens a model is ALLOWED to
output in one response differs by model, and Hermes has to look that up
by matching the model's name against a table, because the name itself
can be messy (`claude-sonnet-4-5-20250929` has a date baked into it).

**Why Hermes needs this:** Hermes lets the user pick ANY Claude model,
switch between them freely, and must never silently send a
request shape one model will reject.

**Do we need this? Yes — you're right, this one matters.** Even though
our agents are narrow and scripted, we still:
- Hardcode `max_tokens=4096` right now, with no check against what the
  actual model we're using actually allows — if we ever pick a model
  with a SMALLER real limit, or want to deliberately use a LARGER one a
  newer model supports, our code has no way to know that's even
  possible or how much headroom exists.
- Have zero handling for "thinking" mode at all. We may never need
  extended thinking for these specific agents — but if a future agent
  genuinely benefits from it (say, Agent A reasoning through a complex
  negotiation summary), we'd hit this exact wall Hermes already solved.

**What we'd actually need, scoped to us (not Hermes's full version):** a
small, honest table of the handful of specific Claude models we
ourselves will ever actually use, with their real max-output limits —
not Hermes's full cross-vendor pattern-matching system, just enough to
stop guessing a number and hope it's right.

**UPDATE — this is now built.** `agent/adapters/anthropic/quirks.py`
holds `ANTHROPIC_MAX_OUTPUT_TOKENS` (just our 2 real models,
`claude-sonnet-4-5` and `claude-haiku-4-5`, each confirmed at 64,000 —
cross-checked against Hermes's own real table rather than guessed) and
`get_max_output_tokens()`. `AnthropicProvider.__init__` now uses this
instead of a hardcoded `4096`.

A real bug was caught in the process, discovered by a LIVE call, not
assumed: using the model's raw 64,000-token limit as the DEFAULT broke
every non-streaming `chat()` call outright. The Anthropic Python SDK
itself refuses a non-streaming request if `max_tokens` is large enough
that the call could plausibly run over 10 minutes (its own
`_calculate_nonstreaming_timeout` check: `3600 * max_tokens / 128_000 >
600` seconds, i.e. `max_tokens > ~21_333`). This is an SDK-level safety
rail, not a model capability limit — the model itself can genuinely
produce more, but only `stream()` is allowed to ask for it.

Fixed with a second function, `get_default_max_tokens()`, which returns
the smaller of the model's real limit and a safe non-streaming ceiling
(20,000) — this is what `AnthropicProvider` actually defaults to. A
caller who knowingly wants the model's full real capacity for a
STREAMED answer can still pass `get_max_output_tokens(model)` as an
explicit `max_tokens` value. Both the bug and the fix are covered by
real tests in `tests/test_anthropic_quirks.py` and
`tests/test_anthropic_adapter.py`, and the fix was re-verified with
another live API call after the change.

---

### D. Message-list sanitization — the real heavyweight part

**What it is, for anyone who's never thought about this:** Anthropic's
API has strict rules about the SHAPE of a conversation you send it —
messages must strictly alternate user/assistant (no two user messages in
a row), every "tool call" the model made must be immediately followed by
that tool's result (not just somewhere later in the conversation), and a
few other structural rules. In a short, simple conversation, these rules
are trivially satisfied. In a LONG conversation that's been edited,
compressed, or had parts removed — which happens naturally in a
general-purpose chat tool over time — these rules can get silently
violated, and Anthropic will reject the request with an error that
doesn't clearly explain what's wrong.

**Two real examples from Hermes's code:**

```python
def _merge_consecutive_roles(result):
    """Merge consecutive same-role messages to enforce Anthropic
    alternation."""
    # ... if two "user" messages ended up next to each other
    # (because something in between was removed), glue them into one.

def _strip_orphaned_tool_blocks(result):
    """Strip tool_use blocks with no matching tool_result, and vice versa.
    Context compression or session truncation can remove either side of
    a tool-call pair ... Anthropic requires each tool_use to have a
    matching tool_result in the IMMEDIATELY FOLLOWING user message —
    a global ID match is not enough."""
```

In plain words: if Hermes ever trims old messages to save space (context
compression — covered in Day 5's prompt-caching work), it might
accidentally leave a tool call "dangling" with no matching result, or
leave two user messages touching each other where something used to sit
between them. Rather than let Anthropic reject the request with a
confusing error, Hermes repairs the conversation structure right before
sending it.

**Why Hermes needs this:** Hermes conversations can run for HOURS,
across MANY tool calls, and get actively edited/compressed over time
(exactly the context-management problem our own `CONTEXT_MANAGEMENT.md`
describes for general-purpose chat). The longer and more mutated a
conversation gets, the more likely it drifts into one of these broken
shapes.

**Do we need this? You raised a real point here — let's think it
through carefully, not just say no.** Our CURRENT agents (Agent A/Agent
B pipelines) build a FRESH, short conversation every run — there's no
long-lived, repeatedly-edited history to corrupt, so this specific
problem genuinely doesn't exist for them YET.

BUT — you also said we're building this as a real, enterprise-grade,
SCALABLE engine, not a one-off script. Two honest scenarios where this
becomes real for us:
1. If a WhatsApp conversation (a live back-and-forth with a human, not a
   scripted pipeline) runs long enough and we ever compress/trim its
   history (which `docs/standards/CONTEXT_MANAGEMENT.md` already says we
   will do for genuine conversations) — the exact same corruption risk
   Hermes solved for appears.
2. If a tool call ever fails or gets cancelled mid-way, a tool_use block
   with no result can appear even in a short conversation.

**Verdict: this is a real future need, not a Hermes-only concern — but
it's not needed TODAY**, because nothing in our current pipeline-shaped
agents produces a long or edited history yet. The honest trigger for
building a SMALL version of this (not Hermes's full repair system) is:
the moment we build real, multi-turn WhatsApp conversation handling
(Day 5+) OR the moment we add context compression for long
conversations. Building it now, before either of those exist, would be
speculative.

---

### E. Retry/failover — the part that genuinely matters to us, and where we're thinnest

**What it is, for anyone who's never thought about this:** when a
network call to any API fails, "just try again" is not one strategy —
it's many different strategies depending on WHY it failed. Hermes
encodes this as an enum (a fixed list of named categories) called
`FailoverReason`, with **25 distinct values**, each one telling the
system exactly what kind of recovery makes sense. Reading some of them
directly from the real file:

```python
class FailoverReason(enum.Enum):
    auth = "auth"                        # Transient auth (401/403) — refresh/rotate
    auth_permanent = "auth_permanent"    # Auth failed after refresh — abort

    billing = "billing"                  # 402 or confirmed credit exhaustion — rotate immediately
    rate_limit = "rate_limit"            # 429 or quota-based throttling — backoff then rotate
    upstream_rate_limit = "upstream_rate_limit"  # Aggregator's upstream model is
                                          # rate-limited, NOT your key — don't rotate it

    overloaded = "overloaded"            # 503/529 — provider overloaded, backoff
    server_error = "server_error"        # 500/502 — internal server error, retry

    timeout = "timeout"                  # Connection/read timeout — rebuild client + retry
    ssl_cert_verification = "ssl_cert_verification"  # Deterministic per-host —
                                          # fail fast instead of burning retries

    context_overflow = "context_overflow"  # Context too large — compress, not failover
    payload_too_large = "payload_too_large"  # 413 — compress payload

    model_not_found = "model_not_found"  # 404 or invalid model — fallback to different model
    content_policy_blocked = "content_policy_blocked"  # Safety filter rejected —
                                          # deterministic, don't retry unchanged

    unknown = "unknown"                  # Unclassifiable — retry with backoff
```

**Compare to ours:** our `classify_error()` has **6** categories
(`rate_limit`, `server_error`, `auth`, `bad_request`, `timeout`,
`unknown`), each with a single `should_retry: bool`. That's it — no
actual retry LOOP exists anywhere in our code yet. Right now, if a real
call to Anthropic returns a 503 (overloaded), our classifier correctly
says "this is retryable" — but nothing in our codebase actually retries
it. The call just fails.

**Specific real distinctions Hermes makes that we currently can't:**
- `rate_limit` vs `upstream_rate_limit` — matters when going through an
  aggregator (see category B) — not directly relevant to us since we
  talk to Anthropic directly, but the UNDERLYING idea — "not every 429
  means the same fix" — generalizes.
- `auth` (temporary, worth refreshing and retrying) vs `auth_permanent`
  (already tried refreshing, it's still broken, stop wasting time) — we
  only have one `auth` category that never retries, which is actually
  the SAFE default, but loses the "maybe this was transient" case
  entirely.
- `context_overflow` — "the conversation itself is too big for this
  model" is a DIFFERENT problem than a network failure, and needs a
  DIFFERENT fix (shrink the conversation, don't just resend it
  unchanged). We have no such category at all.
- `ssl_cert_verification` — a cleverly specific case: if your network
  setup (e.g. a corporate proxy that inspects HTTPS traffic) causes a
  certificate error, retrying will ALWAYS fail the exact same way, so
  Hermes fails fast with a helpful message instead of burning time on
  retries that can never succeed. We don't check for this at all — it
  would currently fall into our generic `"unknown"` bucket and get
  retried pointlessly.
- Separately, Hermes has `retry_utils.py` (actual jittered backoff logic
  — waiting a randomized amount of time before retrying, so many
  retries don't all collide at once) and `turn_retry_state.py` (counting
  how many times THIS SPECIFIC request has already been retried, so it
  eventually gives up instead of retrying forever). **We have neither.**

**Why Hermes needs the full 25-category version:** it runs across MANY
different providers and aggregators simultaneously, with real
credential-rotation logic (switching to a backup API key automatically)
that needs fine-grained reasons to decide when rotating a key actually
helps vs. when it's pointless.

**Do we need this? Yes, unambiguously — this is the one category where
"we're thin" is a real production risk, not a stylistic difference.**
We don't need all 25 of Hermes's categories (most are about
multi-provider credential rotation, which doesn't apply to us), but we
are currently missing real, concrete things that WILL happen in
production:
- An actual retry loop with backoff — right now a transient 503 just
  fails outright, with zero attempt to recover, even though our own
  classifier already correctly identifies it as retryable.
- A retry ceiling — so a stuck request doesn't retry forever.
- A `context_overflow` category — distinct from a generic failure,
  because the fix is different (shrink the input) not the same
  (just try again).
- Possibly `ssl_cert_verification` as its own category, if Ornare's
  network setup (corporate proxies, VPNs) could ever produce this —
  worth a deliberate yes/no decision rather than silently missing it.

---

### F. Model metadata/pricing — not touched at all by us

**What it is:** `model_metadata.py` tracks, per model, real facts like
context window size and pricing, refreshed from the network and cached
to disk so it doesn't have to be re-fetched constantly.

**Why Hermes needs it:** it has to show the USER accurate cost estimates
and context-limit warnings across many different models they might pick.

**Do we need this?** Partially — but not Hermes's general version.
`docs/standards/COST.md` already describes our INTENT to track real
per-call cost, but no code implements it yet. We don't need Hermes's
disk-cached, network-probing, many-models version — we need a much
smaller, static table of just the few models we ourselves actually use,
with their real prices, so our cost ledger (still unbuilt) has real
numbers to multiply against instead of guesses.

---

## KNOWLEDGE: `retry_utils.py` and `TurnRetryState`, explained from scratch

Two more real Hermes files that back up Part 2's category E (retry/
failover) — worth understanding in detail before deciding what we
actually need, because "retry logic" is not one simple thing.

### What `retry_utils.py` actually does

**File:** `/home/ubuntu/.hermes/hermes-agent/agent/retry_utils.py` (8,224 bytes)

**The core problem it solves:** when you retry a failed request, "wait a
fixed amount and try again" sounds simple but causes a real issue
called a **thundering herd** — imagine 50 of your requests all get
rate-limited at the exact same moment, and all 50 wait exactly 5
seconds and retry at the exact same moment again. They'll just collide
and get rate-limited again, together, forever. The fix is **jitter** —
adding a small random amount to the wait time, so retries spread out
instead of landing in sync.

Three real pieces inside it:

1. **`parse_retry_after_seconds()`** — many APIs, when they rate-limit
   you, politely tell you exactly how long to wait via a `Retry-After`
   header (e.g. "wait 12 seconds" or a specific timestamp). This
   function reads that header in whatever format it comes in (a plain
   number, or an HTTP-style date) and converts it into "wait this many
   seconds." **Why this matters:** if the server tells you exactly how
   long to wait, guessing your own delay is worse than just listening
   to it.

2. **`jittered_backoff(attempt)`** — when there's no `Retry-After`
   header to read, this computes a wait time that **doubles each
   attempt** (5s → 10s → 20s → 40s...) up to a cap, **plus
   randomness**, so repeated failures don't retry faster and faster
   forever, and concurrent retries don't collide.

3. **The Z.AI-specific functions** (`is_zai_coding_overload_error`,
   `adaptive_rate_limit_backoff`, `zai_coding_overload_retry_ceiling`)
   — these are hyper-specific to ONE particular third-party AI
   provider's known quirky behavior (a specific error code `1305` from
   a specific endpoint). This is Hermes being thick in category B again
   (multi-vendor support) — irrelevant to us since we only use
   Anthropic directly.

### What `TurnRetryState` actually does

**File:** `/home/ubuntu/.hermes/hermes-agent/agent/turn_retry_state.py` (4,980 bytes)

**The core problem it solves:** when one single request to the model
fails, Hermes doesn't just "retry the same thing" — it might try
several DIFFERENT specific fixes in sequence (refresh an expired
credential, shrink an oversized conversation, strip a broken piece of
data) before giving up. Each one of those specific fixes should only be
attempted once per request, otherwise the code could loop forever
trying the same fix repeatedly if it doesn't work.

The comment in the file explains it plainly: this used to be ~16
separate `True`/`False` flag variables scattered through a single
2,400-line function (one flag per possible fix, like
`codex_auth_retry_attempted`, `thinking_sig_retry_attempted`,
`image_shrink_retry_attempted`). `TurnRetryState` just bundles all 16
flags into one clean object, created fresh for each new attempt, so the
code reads `state.image_shrink_retry_attempted = True` instead of a
loose floating variable with no clear home.

### The final decision on E, folded in here

- **F — Model metadata/pricing.** Needed eventually for the cost
  ledger, but it's not blocking anything today since no cost-ledger
  code exists yet either. I'd build this alongside whenever we actually
  implement `docs/standards/COST.md`'s cost tracking, not in isolation
  now.

**Do we need a `TurnRetryState`-style object right now? No** — that
pattern only earns its keep once you have MULTIPLE distinct recovery
strategies running in one request (which is what Hermes has, with 16 of
them). Right now we're only adding ONE recovery strategy (basic
retry-with-backoff), so a single boolean/counter is enough; introducing
a whole state object for one flag would be premature structure.

---

## Part 3 — The actual decision: what we need, what we don't, and why (summary table)

| Category | Hermes has it because... | Do we need it? | Why / why not |
|---|---|---|---|
| **A. Auth subsystem** (OAuth, Keychain, Claude Code credential sharing) | Many different end-users, each with their own personal Claude subscription/login | **No** | We are ONE backend service with ONE Ornare-provisioned API key. There is no "which user's login" question — correctly identified: this is about personal Claude/Claude Code subscriptions, not a service account, which is exactly our situation. |
| **B. Endpoint/vendor proxy detection** (Bedrock, Azure, MiniMax, Kimi, etc.) | Many users route through different compatible backends for cost/access reasons | **No** | We always talk to Anthropic directly. Build this only if Ornare ever deliberately decides to route through a different backend — a real, named decision, not a precaution. |
| **C. Model-specific quirks** (thinking modes, max-output-by-model, effort levels) | Users freely switch between many different Claude model versions | **Yes, a small version — DONE** | Built in `agent/adapters/anthropic/quirks.py`: a small table of just OUR actual models' real limits, not Hermes's full cross-model pattern-matcher. Caught and fixed a real bug in the process (see the UPDATE note under category C above) — the SDK rejects the model's raw limit for non-streaming calls. |
| **D. Message-list sanitization** (role-merging, orphaned tool-block stripping) | Long-lived, actively-edited/compressed conversations drift into invalid shapes | **Not yet — but a real future need** | Our current scripted pipelines build short, fresh conversations every run — no drift possible yet. Becomes real the moment we build long WhatsApp conversations with history compression (Day 5+). Flag to revisit then, not now. |
| **E. Retry/failover** (25-category classification, backoff, retry ceiling, context-overflow handling) | Needs fine-grained recovery across many providers with credential rotation | **Yes, definitely — and it's a real current gap** | We correctly classify SOME failures as retryable already, but nothing in our code actually retries. This is a production risk today, not a someday concern. |
| **F. Model metadata/pricing** | Accurate cost/context display across many possible models | **Yes, a small static version** | `docs/standards/COST.md` already promises real cost tracking — needs a small table of OUR models' real prices, not Hermes's full dynamic, disk-cached, many-vendor system. |

---

## Part 4 — The one-sentence takeaway

**Hermes is thick in exactly the places where it serves many different
people with many different setups (auth, proxies, model variety,
long-lived conversations) — and we should stay thin there, on purpose.
Hermes is NOT thicker than it needs to be in the one place that matters
to everyone regardless of setup — handling failure correctly — and that
is exactly the one place we are currently too thin, and should fix.**
