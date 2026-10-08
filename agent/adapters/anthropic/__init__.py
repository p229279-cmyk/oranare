"""
agent/adapters/anthropic/__init__.py

Re-exports AnthropicProvider so callers can write
`from agent.adapters.anthropic import AnthropicProvider` without caring
that it actually lives in provider.py — same reasoning as any package
__init__: the internal file layout (provider.py, quirks.py, and any
future file added to this folder) is free to change without breaking
anyone importing from the package itself.
"""

from agent.adapters.anthropic.provider import AnthropicProvider

__all__ = ["AnthropicProvider"]
