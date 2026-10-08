## 1. What is `AnthropicProvider`, and why do we need it?

This is the one class that actually talks to Anthropic. Every other part of the engine pretends it doesn't know which AI company we're using — this class is the only place that "secret" is allowed to live.

**Why we do it this way:** imagine if 20 different files in our engine each knew Anthropic's exact request format. The day Anthropic changes something — even a small thing — we'd have to go hunt through all 20 files to fix it, and we'd probably miss one. By keeping that knowledge in ONE place, a change only ever needs ONE fix.

**Why we need this specific kind of thing (an "adapter"):** our engine's loop just wants to say "here's a conversation, give me an answer" — it shouldn't have to care HOW that happens behind the scenes. This class exists to absorb all of Anthropic's specific quirks so the rest of the system can stay simple and never has to think about vendor details.

```python
class AnthropicProvider:
    def __init__(self, api_key, model="claude-sonnet-4-5", max_tokens=4096):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
```

- `import anthropic` is tucked inside `__init__`, not at the top of the file. **Why:** this way, the rest of the engine can still be loaded and tested even on a machine where the `anthropic` package isn't installed at all — only the moment someone actually tries to USE this specific class does it need to exist.
- The real client is built once and saved (`self._client`), not rebuilt every single time we call it. **Why:** building a fresh connection every call would be slower and wasteful — we set it up once, then reuse it for every request this provider ever makes.

## 2. `chat()` — ask once, get one full answer back

```python
def chat(self, messages, system, tools):
    anthropic_messages = [{"role": m.role, "content": m.content} for m in messages]

    response = self._client.messages.create(
        model=self._model, max_tokens=self._max_tokens,
        system=system, messages=anthropic_messages, tools=tools,
    )

    if response.stop_reason is None:
        raise ValueError("...")

    return ModelResponse(
        content=response.content,
        stop_reason=response.stop_reason,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
```

Three steps, and a reason for each:

1. **Turn our shape into Anthropic's shape.** Why: our engine uses its own `Message` objects everywhere, on purpose — so if we ever add a second AI provider, nothing upstream has to change, only this translation step.
2. **Make the real call.** This is the one and only place the actual network request happens.
3. **Turn Anthropic's answer back into our shape.** Why: so the rest of the engine keeps reading one consistent shape (`ModelResponse`), no matter which vendor actually answered.

**Why the `stop_reason is None` check exists:** Anthropic's own type system technically allows this field to come back empty, even though in practice it never should on a normal finished call. We check for it anyway and raise a clear error if it ever happens — because a loud, obvious error right here is much easier to debug than a weird crash somewhere else, minutes later, with no clue what caused it.

## 3. `stream()` — ask once, get the answer back word by word

```python
with self._client.messages.stream(...) as stream:
    for event in stream:
        if event.type == "content_block_delta" and event.delta.type == "text_delta":
            yield StreamEvent(type="text_delta", data=event.delta.text)
        elif event.type == "message_stop":
            final = stream.get_final_message()
            yield StreamEvent(type="message_stop", data=ModelResponse(...))
```

**Why we need this at all, separate from `chat()`:** when a real person is waiting and watching (like a live WhatsApp chat), seeing words appear as they're generated feels much faster and more natural than staring at a blank screen until the whole answer is ready. `chat()` makes you wait for everything; `stream()` lets you show progress immediately.

Anthropic sends back a bunch of small technical events while streaming — far more than we actually need. **Why we only keep two of them:** a person watching a live chat only cares about two things in the end — "some new words just appeared" and "it's completely finished." Everything else is internal bookkeeping Anthropic uses behind the scenes, and if we passed all of it straight through, every part of the engine that uses streaming would have to learn Anthropic's whole internal event system just to find the two things it actually needs. So we filter it down here, once, and hand the rest of the engine only the two simple things it actually cares about.
