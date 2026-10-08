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

- `stop_reason` is the most important field in this whole file. It's the ONE thing that tells the Agent Loop what to do next: "did the model want to use a tool, or is this its final answer?" Everything downstream depends on reading this field correctly. **Updated while building the real adapter:** this field originally only allowed 3 values (`end_turn`, `tool_use`, `max_tokens`) — guessed before we'd checked the real SDK. Once we actually verified against the installed `anthropic` package's own type definitions, it turned out the real API can return 7 different values (also `stop_sequence`, `pause_turn`, `refusal`, `model_context_window_exceeded`). Fixed to match exactly — a good example of why "verify against the real thing" beats "assume you remember the shape right."
- `input_tokens` / `output_tokens` are attached to every single response from day one — not added later as an afterthought — because this is exactly what lets us track cost per call without retrofitting it in afterward.

**`StreamEvent`** — one tiny fragment of a response, arriving piece by piece, instead of waiting for the whole answer to finish before showing anything. Used when we want text to appear live, the way ChatGPT/Claude's UI shows words appearing as they're generated.

## Why `content` is typed as `Any` instead of something stricter

At first glance `Any` looks lazy — like we just didn't bother being specific. It's actually the opposite: it's a deliberate choice, made for a real reason.

A message's content can genuinely be one of two different shapes:

- just plain text (`"hello"`), or
- a list of structured pieces — some text, maybe a tool call, maybe a tool's result — all bundled together

If we tried to force one strict type here, we'd end up having to invent a type that copies Anthropic's own internal format for how it structures tool calls. And that's exactly the trap this whole file is designed to avoid: keeping the REST of the engine completely unaware of what Anthropic's API specifically looks like.

The actual strict shape-checking still happens — just not here. It happens later, inside `AnthropicProvider`, which is the ONE place in the whole system that's allowed to know Anthropic's exact wire format. Everywhere else stays vendor-agnostic.

## What `Protocol` is, and why `ModelProvider` uses it instead of a normal base class

A `Protocol` is Python's way of saying "any class that HAS these methods counts as this type" — without that class needing to explicitly say `class AnthropicProvider(ModelProvider):`. It's checked by *shape*, not by inheritance.

**The normal way (inheritance):**
```python
class ModelProvider(ABC):
    @abstractmethod
    def chat(self, ...): ...

class AnthropicProvider(ModelProvider):   # must explicitly inherit
    def chat(self, ...): ...
```

**The `Protocol` way (what we did):**
```python
class ModelProvider(Protocol):
    def chat(self, ...): ...

class AnthropicProvider:   # no inheritance needed at all
    def chat(self, ...): ...   # just HAS the right methods — that's enough
```

## Why this matters for us specifically

A new model provider (say, a second vendor someday) can be added by just writing a plain class with the right methods — it never has to know `ModelProvider` exists, never has to import it, never has to remember to inherit from it. This directly matches the test we set for the whole engine: adding something new should never require touching an existing file.

**Updated once we actually built the real adapter:** this isn't just about not touching the interface's *code* — it's also about which *file* a new provider lives in. We originally put the concrete `AnthropicProvider` class in the same file as this `Protocol` (`agent/model_provider.py`). Once we checked how Hermes itself actually does this, we found every one of its real provider adapters (`anthropic_adapter.py`, `bedrock_adapter.py`, `vertex_adapter.py`, and three more) is its own separate file — never folded into one shared module with the interface. We split ours to match: `agent/model_provider.py` now holds ONLY the generic pieces (this `Protocol`, the data shapes, `classify_error`), and the real `AnthropicProvider` class moved to its own new file, `agent/anthropic_adapter.py`. A future second provider gets its own new file too (e.g. `agent/openai_adapter.py`) — zero changes to either existing file.

## Why both methods take the exact same three arguments

`chat(messages, system, tools)` and `stream(messages, system, tools)` are deliberately symmetric — same inputs, just a different way of getting the output back (all-at-once vs. piece-by-piece). This means the Agent Loop can pick whichever one it needs without reshaping its data first.

## What `classify_error` actually does

When a call to the model fails, we don't just blindly retry a few times and hope. We look at WHAT KIND of failure it was, and decide the right response for that specific kind — because not every failure is worth retrying.

```python
def classify_error(error: Exception) -> ClassifiedError:
    status_code = getattr(error, "status_code", None)

    if status_code == 429:
        return ClassifiedError("rate_limit", should_retry=True, ...)
    if status_code in (500, 502, 503, 529):
        return ClassifiedError("server_error", should_retry=True, ...)
    if status_code == 401:
        return ClassifiedError("auth", should_retry=False, ...)
    if status_code == 400:
        return ClassifiedError("bad_request", should_retry=False, ...)
    ...
```

## Why retrying everything the same way is wrong

Imagine two failures:
- **429 (rate limited)** — we sent requests too fast. Waiting a moment and trying again has a real chance of working.
- **401 (bad API key)** — our key is wrong or expired. Trying again with the *same* bad key will fail **exactly the same way, every single time.**

Treating both the same way (just "retry 3 times") wastes time and money on the 401 case — it can never succeed, no matter how many times you try. `classify_error` exists so the code can tell these two apart and react correctly to each.

## Why `should_retry` is a field on the result, not decided later

```python
@dataclass
class ClassifiedError:
    failure_type: FailureType
    should_retry: bool
    message: str
```

The classifier makes the retry decision **once, in one place**. If instead every caller had to look at `failure_type` and re-decide "should I retry this?" themselves, that logic could drift — one caller might retry an `auth` failure by mistake, another might not. Baking `should_retry` directly into the result means there's only one place this decision is ever made, and it can't be gotten wrong twice.

## Why we check `status_code` first, not the error message text

Status codes are a reliable, structured signal — `429` always means rate-limited, `401` always means auth failed. Error message *text*, on the other hand, can vary (different wording, different languages, formatting changes between SDK versions). We read the status code first because it's the most trustworthy signal, and only fall back to inspecting text when the status code alone doesn't tell us enough.

## Why this was tested without ever calling the real API

```python
class FakeAPIError(Exception):
    def __init__(self, status_code, message="fake error"):
        self.status_code = status_code
```

We built a fake error with just a `status_code` attribute — no real network call, no API key needed. This proves the *classification logic itself* is correct, completely separately from "does the real Anthropic API actually work." If this logic has a bug, we want to find it in a test that runs in milliseconds, not by waiting for a rare real failure in production.

**Updated once we checked against the real SDK:** "no real network call needed" is true, but we still went one step further and tested against the REAL `anthropic` package's actual exception classes (not just our `FakeAPIError` stand-in) — and this caught a genuine bug. Our original timeout check was `isinstance(error, (TimeoutError, OSError))`, which seemed reasonable, but the real `anthropic.APITimeoutError` is **not** a subclass of either one — it inherits from `APIConnectionError → APIError → AnthropicError → Exception` instead. A real timeout would have silently been classified as `"unknown"` instead of `"timeout"` (both still retry, so this specific bug wouldn't have broken behavior, but the label would have been wrong — and that label is exactly what feeds the observability records this whole classifier exists to produce). Fixed by also checking the exception's type name (`"APITimeoutError" in error_type_names`), without importing the `anthropic` package directly into this file — so the classifier still works even somewhere the SDK isn't installed. A new test, `test_real_anthropic_timeout_error_is_classified_correctly`, now exercises the real exception class specifically to catch this class of bug if it ever comes back.
