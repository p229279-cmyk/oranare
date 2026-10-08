"""
agent/adapters/openai/__init__.py

Re-exports OpenAIProvider so callers can write
`from agent.adapters.openai import OpenAIProvider` without caring that
it actually lives in provider.py - same reasoning as
agent/adapters/anthropic/__init__.py.
"""

from agent.adapters.openai.provider import OpenAIProvider

__all__ = ["OpenAIProvider"]
