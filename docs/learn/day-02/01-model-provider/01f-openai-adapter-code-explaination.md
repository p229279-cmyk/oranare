## 1. `_map_finish_reason(finish_reason)` — translating OpenAI's vocabulary into ours

```python
_FINISH_REASON_MAP: dict[str, _StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "refusal",
}

def _map_finish_reason(finish_reason: str) -> _StopReason:
    mapped = _FINISH_REASON_MAP.get(finish_reason)
    if mapped is None:
        raise ProviderInvariantError(
            f"OpenAI API returned an unrecognized finish_reason "
            f"'{finish_reason}' - this should be impossible..."
        )
    return mapped
```

**Why this function exists at all:** OpenAI tells us WHY a response ended using its own words (`"stop"`, `"length"`, `"tool_calls"`...). Our engine has its own words for the exact same ideas (`"end_turn"`, `"max_tokens"`, `"tool_use"`...), because the rest of the engine was built to be vendor-agnostic — it should never have to learn OpenAI's specific vocabulary just because OpenAI happens to be one of the vendors we use. This function is the one place that translation happens.

**Why two different OpenAI values (`"tool_calls"` and `"function_call"`) both map to the same one of ours (`"tool_use"`):** `"function_call"` is OpenAI's OLD, deprecated name for the same concept `"tool_calls"` now represents (newer, current naming). We don't need two different outcomes in our engine for "the model wants to call a tool" — we only have ONE concept for that. Mapping both old and new OpenAI names onto our single concept means our engine code never has to care which naming era a particular OpenAI response happened to use.

**Why it raises loudly instead of just passing the string through unchanged:** if OpenAI ever introduces a brand-new `finish_reason` we don't know about yet, silently passing it through would violate our own `ModelResponse.stop_reason` contract — which is deliberately locked to a fixed, specific list of allowed values. Catching this immediately, with a clear error message naming exactly which unrecognized value showed up, is far easier to debug than letting a bad value quietly travel somewhere else in the system and cause a confusing failure much later.

## 2. `chat()` — the system prompt has to go INSIDE the messages list

```python
openai_messages = [{"role": "system", "content": system}] + [
    {"role": m.role, "content": m.content} for m in messages
]

response = self._client.chat.completions.create(
    model=self._model,
    max_completion_tokens=self._max_tokens,
    messages=openai_messages,
    tools=tools if tools else None,
)
```

**Why the system prompt gets glued onto the FRONT of the messages list, instead of being passed as its own separate thing (the way Anthropic's adapter does it):** Anthropic's real API genuinely has a dedicated `system` parameter, completely separate from the conversation messages. OpenAI's API has no such parameter at all — as far as OpenAI's API is concerned, a "system instruction" is just another message in the list, the very first one, with a special role name (`"system"`) attached to it. Our engine's own `chat()` method still takes `system` as its own separate argument either way — callers never need to know this difference exists. The adapter is exactly the place that absorbs this kind of vendor-specific detail.

**Why `max_completion_tokens` instead of `max_tokens`:** this is the direct result of the real bug caught by actually calling OpenAI's live API — `gpt-5.6` rejected `max_tokens` outright with a clear error telling us to use `max_completion_tokens` instead. OpenAI made this change because, for their newer "reasoning" models, the number of tokens the model actually GENERATES internally and the number of tokens it RETURNS to us aren't necessarily the same number anymore — so they renamed the setting to make every caller explicitly acknowledge that distinction, rather than silently reusing an old parameter whose meaning had quietly changed underneath it.

**Why `tools=tools if tools else None` instead of just `tools=tools`:** when there are genuinely no tools to offer the model, we pass `None` rather than an empty list — this matches what a real caller with no tools would naturally want to express, and keeps us from accidentally sending an empty-but-present `tools` field that some part of OpenAI's API might treat differently than simply omitting it.

## 3. `stream()` — picking the final usage numbers out of a SEPARATE last chunk

```python
for chunk in stream:
    choice = chunk.choices[0] if chunk.choices else None
    if choice is not None and choice.delta.content:
        yield StreamEvent(type="text_delta", data=choice.delta.content)
    if choice is not None and choice.finish_reason is not None:
        final_finish_reason = choice.finish_reason
    if chunk.usage is not None:
        final_input_tokens = chunk.usage.prompt_tokens
        final_output_tokens = chunk.usage.completion_tokens
```

**Why there's a check for `chunk.choices` being empty:** when we ask OpenAI's streaming API to include token-usage information (`stream_options={"include_usage": True}`), the VERY LAST chunk it sends back is a special one that carries ONLY the usage numbers — its `choices` list is completely empty, because it's not delivering any more text, just the final accounting. Without this check, trying to read `chunk.choices[0]` on that last chunk would crash, since there's nothing at index 0 of an empty list.

**Why we track `final_finish_reason` and the token counts separately, piece by piece, instead of reading them from one single object at the end:** unlike a normal `chat()` response — which comes back as ONE complete object with everything already attached — a streamed response arrives as many small, separate pieces over time, and different pieces carry different parts of the final picture (one chunk tells us WHY it stopped, a different, later chunk tells us how many tokens were used). We have to collect these pieces as they arrive and only build the final, complete `ModelResponse` once the whole stream has finished.

**Why it raises loudly if the stream ends without ever setting `final_finish_reason`:** a stream that finishes without ever telling us why it finished would be a genuine anomaly in OpenAI's own API contract — exactly the same "this should be impossible, fail loud rather than guess" discipline used everywhere else in this adapter (and in the Anthropic adapter before it).
