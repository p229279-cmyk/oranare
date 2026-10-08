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

## Why we need these three specific shapes

They're the shared vocabulary every part of the engine uses to talk about a conversation. Without them, every function would pass around raw dicts like `{"role": "user", "content": "hi"}` — which gives you zero guarantees. Nothing stops a typo like `"rol"` instead of `"role"`. Nothing tells you what fields are supposed to exist. Your editor can't warn you, autocomplete can't help you, and a bug like this would only show up later, somewhere confusing, far from where the typo actually happened.

**`Message`** — one single turn in the conversation (one thing said, by one side).

- `role` can ONLY be `"user"` or `"assistant"` — nothing else is allowed. If someone accidentally typed `"system"` here, Python would reject it immediately instead of letting a silent bug slip through.
- `content` is left loose (`Any`) on purpose — explained below.

**`ModelResponse`** — what the model actually sent back after we asked it something.

- `stop_reason` is the most important field in this whole file. It's the ONE thing that tells the Agent Loop what to do next: "did the model want to use a tool, or is this its final answer?" Everything downstream depends on reading this field correctly.
- `input_tokens` / `output_tokens` are attached to every single response from day one — not added later as an afterthought — because this is exactly what lets us track cost per call without retrofitting it in afterward.

**`StreamEvent`** — one tiny fragment of a response, arriving piece by piece, instead of waiting for the whole answer to finish before showing anything. Used when we want text to appear live, the way ChatGPT/Claude's UI shows words appearing as they're generated.

## Why `content` is typed as `Any` instead of something stricter

At first glance `Any` looks lazy — like we just didn't bother being specific. It's actually the opposite: it's a deliberate choice, made for a real reason.

A message's content can genuinely be one of two different shapes:

- just plain text (`"hello"`), or
- a list of structured pieces — some text, maybe a tool call, maybe a tool's result — all bundled together

If we tried to force one strict type here, we'd end up having to invent a type that copies Anthropic's own internal format for how it structures tool calls. And that's exactly the trap this whole file is designed to avoid: keeping the REST of the engine completely unaware of what Anthropic's API specifically looks like.

The actual strict shape-checking still happens — just not here. It happens later, inside `AnthropicProvider`, which is the ONE place in the whole system that's allowed to know Anthropic's exact wire format. Everywhere else stays vendor-agnostic.
