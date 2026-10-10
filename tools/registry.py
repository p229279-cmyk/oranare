"""
tools/registry.py

The generic, tool-agnostic vocabulary for the tool system: the shape
every tool is described with (Tool), and - in later steps - the
registry that stores and dispatches them.

See docs/learn/day-02/02-tool-registry/01a-tool-registry.md for the
teaching walkthrough and docs/engine/03-TOOLS.md for the spec this
implements.

Deliberately built the SAME way ModelProvider was: real shapes first,
one function/class at a time, each checked against real Hermes
source before being written - but NOT copying Hermes wherever our own
spec (docs/engine/03-TOOLS.md, docs/standards/SECURITY.md) already
made a different, deliberate decision. Two differences from Hermes's
real ToolEntry, both intentional:

1. blast_radius is a REQUIRED field here, with no default. Hermes's
   real ToolEntry has no such field at all - Hermes's own approval
   system (tools/approval.py) is a much larger, separate subsystem
   layered on top of dispatch. Our docs/standards/SECURITY.md made an
   explicit, deliberate decision to make this an enforced field at
   registration time, not something inferred later.
2. Hermes's real ToolEntry has 11 fields (requires_env, emoji,
   max_result_size_chars, dynamic_schema_overrides, ...). We start
   with only the fields we have a REAL, NAMED need for today - same
   YAGNI discipline as agent/adapters/anthropic/quirks.py starting
   with 2 models before being expanded. Extra fields get added only
   when a real tool actually needs one, not speculatively.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

# The four blast-radius tiers, verified against docs/standards/SECURITY.md
# section 2's enforcement table. This is a CLOSED set on purpose - a new
# tier is a real security-policy decision, not something a tool author
# should be able to invent ad hoc by typing a new string.
BlastRadius = Literal[
    "read_only",
    "reversible_write",
    "consequential_single",
    "consequential_bulk",
]


@dataclass
class Tool:
    """The generic shape every tool is described with - what the model
    sees (name/description/parameters) plus what actually runs
    (handler) plus how dangerous it is (blast_radius).

    Deliberately a dataclass, not Hermes's real __slots__-based class.
    Hermes's real ToolEntry uses __slots__ because it has 100+ live
    instances held in a shared registry for the lifetime of a long-running
    process - a real, measured memory-footprint concern at that scale.
    We don't have that scale yet; a plain dataclass is simpler to read
    and test, and the real memory saving __slots__ buys isn't a problem
    we actually have. Revisit if real tool counts and process lifetimes
    ever make this matter - YAGNI applies here the same as everywhere
    else in this project.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    blast_radius: BlastRadius
    check_fn: Callable[[], bool] | None = None
