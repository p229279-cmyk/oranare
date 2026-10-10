# Day 2, Component 2, Step 1 — ToolRegistry: the `Tool` shape

Same build order as `ModelProvider`: real shapes first, one piece at
a time, each grounded in real Hermes source before being written —
but deviating deliberately wherever our own spec
(`docs/engine/03-TOOLS.md`, `docs/standards/SECURITY.md`) already made
a different decision. See
`docs/learn/day-02/02-tool-registry/00-big-picture.md` for the full
conceptual walkthrough this build follows; this file tracks the real
code as it gets built.

## What was built

`tools/registry.py` — a `Tool` dataclass: `name`, `description`,
`parameters`, `handler`, `blast_radius` (required), `check_fn`
(optional, defaults to `None`).

## Two deliberate differences from Hermes's real `ToolEntry`

1. **`blast_radius` is required, with no default.** Hermes's real
   `ToolEntry` has no such field — Hermes's own approval system
   (`tools/approval.py`, 5,498 lines) is a separate, much larger
   subsystem layered on top of dispatch. Our
   `docs/standards/SECURITY.md` made an explicit decision: every tool
   gets an enforced tier AT REGISTRATION TIME, never inferred later.
   Verified this is a REAL enforcement, not just documentation, with
   a test: constructing a `Tool` without `blast_radius` raises
   `TypeError` immediately.
2. **Only 6 fields, not Hermes's 11.** Hermes's real `ToolEntry`
   (`tools/registry.py`, verified via its `__slots__` tuple) also
   carries `toolset`, `requires_env`, `is_async`, `emoji`,
   `max_result_size_chars`, `dynamic_schema_overrides`. We start
   WITHOUT these — same YAGNI discipline as
   `agent/adapters/anthropic/quirks.py` starting with just 2 models.
   Each one gets added only when a real tool actually needs it, not
   speculatively. `toolset` and `is_async` are the two most likely to
   be needed soon (Step 5 and Step 4 of this build respectively).

## One more difference from Hermes: `@dataclass(slots=True)`, not a hand-written `__slots__` tuple

**Correction, caught by a direct user question, not something gotten
right the first time:** an earlier version of this doc (and the code)
claimed dataclass-vs-slots was a real tradeoff — "memory efficiency OR
convenient repr/equality, pick one." That was WRONG, and wrong because
it was assumed rather than checked. Verified directly: Python 3.10+'s
`@dataclass(slots=True)` gives BOTH at once — `__slots__`'s real
memory saving AND the dataclass's auto-generated `__repr__`/`__eq__`,
with zero loss either way. Measured directly on our actual 6-field
shape: **80 bytes with `slots=True` vs. 352 bytes without — a real,
free 4.4x reduction**, confirmed with `sys.getsizeof()`, not assumed.
Fixed in the code to use `@dataclass(slots=True)`; two new regression
tests added (`test_slots_blocks_arbitrary_extra_attributes`,
`test_repr_and_equality_still_work_with_slots`) proving both halves of
the claim are real, not just asserted in a docstring.

The real lesson here, worth stating plainly: **"check it, don't
assume it" applies to our OWN reasoning just as much as it applies to
claims about Hermes or the SDKs** — the earlier draft sounded
plausible and matched a real, generally-true fact about older Python
(`__slots__` used to genuinely conflict with dataclasses before 3.10),
but hadn't been verified against the ACTUAL Python version this
project targets (3.11, confirmed in `docs/STACK.md`).

## Verified

7 tests, `tests/test_tool_registry.py`: construction with all
required fields, the handler is a real callable that produces a real
result, `check_fn` defaults to `None` (always available) and can be
set to a real callable, the enforcement test that omitting
`blast_radius` raises `TypeError`, and the two new slots regression
tests described above.

## Code understanding

Full function-by-function explanation lives in
[`01a-tool-registry-code-explaination.md`](01a-tool-registry-code-explaination.md).

## Step 2 — `ToolRegistry`: `register()` and `get_entry()`

`tools/registry.py` now also has a `ToolRegistry` class: a plain
`dict[str, Tool]`, plus `register(tool)` and `get_entry(name)`.

**Deliberately much smaller than Hermes's real `register()`.** The
real Hermes signature takes 13 parameters and carries real complexity
we have no use for yet: plugin-ownership tracking
(`_plugin_owner_of`), per-profile scoped overlays (`scope=`), and an
`override=True` opt-in for a plugin replacing a built-in tool. All of
that exists because Hermes has a plugin ecosystem — third-party code
can register tools alongside, or instead of, built-in ones, at
unpredictable times, from code Hermes's own maintainers didn't write.
We have no plugins today — every tool we register is OUR OWN code,
so none of that ownership/override machinery has a real consumer yet
(same YAGNI discipline as everywhere else in this build; see `TODO.md`
if this ever needs revisiting).

**The one real behavioral difference worth naming:** Hermes's real
`register()` on a name collision **silently rejects** the NEW
registration (logs an error, returns, the ORIGINAL tool keeps its
slot) unless `override=True` is explicitly passed. Ours **raises
`ValueError` immediately** instead. Why the difference is deliberate,
not an oversight: Hermes's silent-reject makes sense when a
THIRD-PARTY plugin might register at an unpredictable time — crashing
the whole process over someone else's plugin mistake would be overly
disruptive. We have no plugins, so every duplicate-name collision
today is OUR OWN authoring mistake (two tools accidentally given the
same name) — and an authoring mistake in our own code should fail
loudly and immediately, at the exact moment it happens, not be
silently absorbed. Same "fail loud, not silent" discipline as
`blast_radius` being required and `ProviderInvariantError` in
`agent/model_provider.py`.

## Verified (Step 2)

5 more tests: register-then-get-entry returns the same object,
`get_entry` on an unknown name returns `None` (not an exception — "is
this registered" is a normal question, not an error), a duplicate
name raises `ValueError`, a duplicate registration does NOT replace
the original entry (proving the rejection is real, not just an
exception with no actual effect), and two different names both
register successfully side by side. 12 tests total in this file, 54
across the whole project.

## Next

Step 3: `get_definitions()` — the exposure-to-model lookup, including
`check_fn` filtering (mirrors Hermes's real availability check, see
the big-picture doc's Phase B sequence diagram).

## A real question worth recording: why `blast_radius` when Hermes has no such field?

Hermes controls tool danger completely differently — not by tiering
tools at registration, but by pattern-matching the CONTENT of a
specific call (`tools/approval.py`'s `HARDLINE_PATTERNS`,
`DANGEROUS_PATTERNS`, the Tirith scanner). That mechanism fits
Hermes's real shape: ONE general-purpose tool (`terminal`) whose
danger depends on arbitrary command text, not on which tool it is.

Our shape is the opposite: many narrow, specific, purpose-built tools
per agent, where the danger is a property of WHICH tool it is, known
and fixed the moment it's written — not something that needs parsing
a call's content. `blast_radius` fits THIS shape, and — importantly,
given this project's goal of becoming one general-purpose harness
across 100+ future agent types across many industries, not just
Oranare's 2 — it scales cleanly: a dental agent's "cancel all
appointments" tool and a fraud-review agent's "freeze an account"
tool both just get tagged `consequential_bulk`, same mechanism, zero
new code per agent.

The two mechanisms are not competing choices — see `TODO.md`'s
"Content-based danger detection for tools" entry for the real,
deferred trigger condition for when a FUTURE tool (e.g. a `run_sql`
tool) would need BOTH: a fixed `blast_radius` tier AND a
Hermes-style content-pattern check layered on top.
