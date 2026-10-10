# Day 2, Component 2 — Tool Registry: The Big Picture (Hermes's real system, explained first)

This file is the CONCEPTUAL walkthrough of how Hermes's real tool
system works end-to-end, written before any of our own code — same
discipline as every other component: understand the real mechanism
first, ground every later design decision in it, build second.

Grounded in real Hermes source, verified by reading the actual files,
not assumed: `/home/ubuntu/.hermes/hermes-agent/tools/registry.py`
(1,335 lines), `tools/approval.py` (5,498 lines), `toolsets.py`
(1,083 lines), and real individual tool files like
`tools/computer_use_tool.py` and `tools/close_terminal_tool.py`.

---

## The big picture — 4 layers, in order

**1. DEFINE** — each tool file (`tools/*.py`) has three things: a
Python function (what it actually does), a `SCHEMA` dict
(name/description/parameters — this is literally what gets sent to the
model so it knows the tool exists), and a `registry.register(...)`
call at the bottom of the file.

**2. DISCOVER** — on startup, Hermes scans every file in `tools/`,
checks (via a cheap AST scan, not importing) whether it calls
`registry.register(...)`, and only imports the ones that do. Importing
the file is what ACTUALLY runs that `register()` call and adds it to
the registry.

**3. REGISTRY** (`ToolRegistry`, a singleton) — one big dict:
`name → ToolEntry` (schema + handler function + an optional `check_fn`
+ metadata). It's the single source of truth for "what tools exist and
how to run them." Nothing else holds a second copy.

**4. TOOLSETS** — tools are grouped into named bundles (e.g.
`"browser"`, `"terminal"`). A toolset is just a label; the registry
still holds every individual tool. Toolsets exist so a profile/session
can say "give me the `browser` bundle" instead of listing 15 tool names
by hand.

## The two moments the registry actually gets used

- **`get_definitions(tool_names)`** — called once per model request.
  Walks the requested names, skips any whose `check_fn()` says "not
  available right now" (e.g. browser tool but playwright isn't
  installed), and returns the OpenAI-format schema list that actually
  gets sent to the model.
- **`dispatch(name, args)`** — called when the model asks to USE a
  tool. Looks up the entry, calls `entry.handler(args)`, catches every
  exception and turns it into a clean `{"error": ...}` string instead
  of crashing, so a buggy tool never kills the conversation.

## The one engineering idea underneath all of it

**A tool is just data (schema) + a function (handler), registered
once, looked up by name everywhere else.** Nothing else in the system
(the loop, the model call, the UI) needs to know HOW a tool works —
only that it has a name, a schema, and something callable. `check_fn`
is the one clever addition: it lets a tool be REGISTERED (exists) but
conditionally HIDDEN from the model (not available right now) — e.g.
don't offer the browser tool if the browser binary isn't installed —
without having to register/deregister tools dynamically.

---

## Next

This is the conceptual skeleton only — nothing has been built yet for
our own engine. Follow-up topics to go deeper on before (or while)
designing our own `ToolRegistry`:
- `check_fn` mechanics in detail (caching, TTL, what triggers a
  re-check).
- The discovery/caching mechanics (the mtime+size cache that avoids
  re-scanning every file on every startup).
- Toolsets vs. registry — exactly how a toolset "bundle" resolves down
  to individual tool names (`resolve_toolset`, aliasing, nesting).
- The approval/blast-radius layer (`tools/approval.py`) — a separate,
  much larger concern layered on top of dispatch, not part of the core
  registry itself.
