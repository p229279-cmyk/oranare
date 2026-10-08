# Technology Stack — Decision Record

**Status:** Locked, Day 1. This is a decision record, not a living
document — if this ever needs to change, it should be a deliberate,
reasoned update here, not silent drift in what language a new file
happens to get written in.

## The decision

**We use the same language Hermes uses, in the same places Hermes uses
it — confirmed against Hermes's real source
(`/home/ubuntu/.hermes/hermes-agent`), not assumed.**

| Layer | Language | Matches Hermes's own real choice |
|---|---|---|
| Agent core / runtime (loop, providers, tools, prompts, session store) | **Python 3.11+** | `agent/conversation_loop.py`, `agent/anthropic_adapter.py`, `tools/registry.py`, `hermes_state.py` — all `.py` (note: Hermes's own layout; our engine groups adapters under `agent/adapters/` instead, see below) |
| CLI / orchestration scripts | **Python** | `cli.py` |
| Gateway / scheduler | **Python** | `gateway/run.py` |
| WhatsApp bridge specifically | **Node.js** (Baileys) | `scripts/whatsapp-bridge/`, built on `@whiskeysockets/baileys` |
| Everything else (web dashboard, if/when built) | **TBD at that point**, not decided today | Hermes's own desktop app is Electron/TS, but that's UI shell, out of this build's scope (`docs/PRD.md` non-goals) |

## Why this is the right call, not just "copy Hermes"

- **Python for the core:** every interface we've already specified in
  `docs/engine/` is written as Python `Protocol`/`dataclass`. The
  Anthropic SDK we're using, the WhatsApp formatter logic we're reusing,
  and every real mechanism we grounded our standards in
  (`error_classifier.py`, `retry_utils.py`, `system_prompt.py`) is
  already Python — matching it isn't deference, it's the path of least
  friction for code we're directly reusing or directly modeling.
- **Node.js for WhatsApp specifically, and ONLY there:** Baileys (the
  WhatsApp Web protocol implementation Hermes uses) is JavaScript-only —
  there is no mature, actively-maintained Python equivalent. Hermes's
  own Python core talks to this Node bridge over a local process
  boundary (HTTP/IPC). Our `WhatsAppChannel` adapter
  (`docs/engine/09-CHANNELS.md`) does exactly the same thing: Python
  calls out to the same kind of local Node bridge process, never
  reimplementing the WhatsApp protocol itself.
- **No framework layer added on top of either.** This stack is
  deliberately thin — Python stdlib + the Anthropic SDK + SQLite, no
  LangChain/CrewAI/etc. — because a heavyweight framework would silently
  undo the minimal-surface, fully-audited design `docs/standards/SECURITY.md`
  and `docs/standards/COST.md` depend on.

## What this means concretely for Day 2 onward

- Every file under `agent/`, `tools/`, `channels/` (except the WhatsApp
  bridge process itself), `cron/` in this repo is Python.
- The WhatsApp bridge, when built in Day 5, is either the EXACT existing
  Node/Baileys bridge from the original Ornare build (reused, not
  rewritten) or a thin fork of it — not a new implementation in a
  different language.
- No new language gets introduced into this repo without a new decision
  record here, reasoned the same way as above (a real, named constraint
  forcing it — not convenience or familiarity).
