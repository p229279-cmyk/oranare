## What `@dataclass` is

A shortcut that auto-writes a class's boilerplate (`__init__`, printing, equality) from just a list of fields.

**Without it:**
```python
class Message:
    def __init__(self, role, content):
        self.role = role
        self.content = content
```

**With it:**
```python
@dataclass
class Message:
    role: str
    content: str
```

Same result, way less typing.

## Why we need it here

Without a dataclass, every part of the engine would pass around raw dicts like `{"role": "user", "content": "hi"}` — no safety net. A typo like `"rol"` instead of `"role"` would fail silently, and your editor can't warn you a field is missing. A dataclass locks in the exact shape, so mistakes get caught immediately instead of causing a weird bug later.

## Why we need THESE three specifically

They're the shared vocabulary every part of the engine uses to talk about a conversation — without them, every function would have to pass around raw dicts (`{"role": "user", "content": "hi"}`), which has no guarantees: nothing stops a typo like `"rol"` instead of `"role"`, nothing tells you what fields exist, and your editor/IDE can't help you.
