"""Model adapters used by the pathfinding package.

The CPU GPT runner must not import the optional Llama3 GPU stack.
LLMAStar loads Llama3 only when explicitly requested.
"""

from .chatgpt import ChatGPT


def __getattr__(name):
    if name == 'Llama3':
        from .llama3 import Llama3
        return Llama3
    raise AttributeError(name)
