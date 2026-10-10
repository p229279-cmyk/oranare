## 1. `BlastRadius` — why a closed `Literal`, not a plain string

A `Literal` type lists the EXACT allowed values — nothing else is legal:

```python
BlastRadius = Literal[
    "read_only", "reversible_write",
    "consequential_single", "consequential_bulk",
]
```

**Why not just `blast_radius: str`?** With a plain string, a tool author could type `blast_radius="consequentail_bulk"` (a typo) or `blast_radius="medium"` (a made-up tier that was never actually decided on) and nothing would catch it — the mistake would sit silently until someone eventually noticed the tool wasn't getting the approval gate it should have had. With `Literal`, the type checker catches both mistakes immediately, before the code even runs — because these 4 tiers aren't arbitrary labels, they're a real, deliberate security policy decision (`docs/standards/SECURITY.md`), and a typo in a security tier is exactly the kind of silent mistake that should be structurally impossible, not just "hopefully caught in review."

## 2. `blast_radius` — why required, with no default value

```python
blast_radius: BlastRadius   # no "= ..." after it — required
```

**Why no default, like `"read_only"`?** If `blast_radius` quietly defaulted to the safest tier, a tool author could register a genuinely dangerous tool, forget to set the tier, and the tool would silently be treated as harmless — accidentally skipping every approval gate it should have had, with no error, no warning, nothing. By making it required, forgetting to set it is a loud, immediate `TypeError` at tool-registration time — the exact moment it's cheapest and safest to catch the mistake, not months later in production when the "harmless" tool turns out to have been bulk-deleting something.

## 3. Why `check_fn` DOES get a default (`None`), but `blast_radius` does NOT

```python
check_fn: Callable[[], bool] | None = None
```

This is a deliberate, asymmetric choice. `check_fn` answers "is this tool currently available" — and for the vast majority of tools, the honest answer is simply "yes, always" (there's no credential to check, no external service that might be down). Defaulting it to `None` (meaning "always available") matches reality for most tools and saves every tool author from writing `check_fn=lambda: True` by hand.

`blast_radius`, by contrast, has NO honest universal default — there is no tier that's correct for "most tools" the way "always available" is correct for most `check_fn`s. Every tool's real danger genuinely differs, and guessing wrong in either direction (too safe → skips needed approval; too dangerous → adds needless friction to a harmless tool) is a real mistake. The two fields look similar (`Optional[...] = None` vs. a plain required type) but the DECISION behind each is opposite, for a real reason: one has a correct universal default, the other genuinely doesn't.

## 4. `@dataclass(slots=True)` — getting both memory efficiency AND convenience, verified not assumed

An earlier version of this code used a plain `@dataclass` (no `slots=True`), reasoning that `__slots__` and dataclass convenience (`__repr__`, `__eq__`) were a tradeoff — pick memory efficiency OR readability, not both. **That reasoning was checked directly and found to be wrong.** Python 3.10+ lets a dataclass generate real `__slots__` automatically while STILL keeping its auto-generated `__repr__` and `__eq__` — there was no real tradeoff to make.

Measured directly on our actual 6-field `Tool` shape, using `sys.getsizeof()`:

```
with slots=True:     80 bytes
without slots=True:  352 bytes
```

A real, free 4.4x memory reduction, with zero loss of debugging convenience — confirmed with two tests: one proving an arbitrary extra attribute is still rejected (the real safety `__slots__` is supposed to buy), and one proving `repr()`/`==` still work correctly (the convenience a plain dataclass buys).

**Two real, tested limitations this DOES introduce** (see `TODO.md`'s "Known, tested limitations" section for the full writeup): (1) weak references (`weakref.ref(...)`) stop working on `Tool` instances — not a problem today, since nothing in our own code uses weak references, only third-party libraries we depend on do; (2) a future subclass of `Tool` would silently LOSE the slots protection unless it also declares `@dataclass(slots=True)` on itself — worth remembering if `Tool` is ever subclassed later.

The honest lesson from this whole episode: a plausible-sounding tradeoff should be CHECKED against the actual Python version in use, not assumed true from older, half-remembered Python behavior — this mistake was caught by a direct user question, not self-caught.
