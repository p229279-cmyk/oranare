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


@dataclass(slots=True)
class Tool:
    """The generic shape every tool is described with - what the model
    sees (name/description/parameters) plus what actually runs
    (handler) plus how dangerous it is (blast_radius).

    Uses @dataclass(slots=True), not Hermes's real hand-written
    __slots__ tuple. Verified directly (not assumed) that Python 3.10+
    dataclasses can generate __slots__ automatically while STILL
    keeping the dataclass's auto-generated __repr__ and __eq__ - this
    is not a tradeoff between "memory efficiency" and "convenient to
    read/test" the way an earlier draft of this file incorrectly
    claimed. Measured directly: this 6-field shape is 80 bytes with
    slots=True vs 352 bytes without - a real, free 4.4x reduction,
    with zero loss of repr/equality convenience. There was no good
    reason to leave this out once actually checked instead of assumed.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    blast_radius: BlastRadius
    check_fn: Callable[[], bool] | None = None
