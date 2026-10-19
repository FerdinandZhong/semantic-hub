"""Model-specific OpenAI wire rules; unknown compatible endpoints retain legacy behavior."""
from __future__ import annotations
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OpenAICompatibility:
    api: str = 'chat-completions'
    reasoning_effort: str | None = None
    completion_budget: bool = False
    minimum_budget: int = 0
    # Largest output budget the model family accepts; requests above it fail with HTTP 400.
    output_limit: int = 4000

    def budget(self, requested: int) -> int:
        return min(max(requested, self.minimum_budget), self.output_limit)

    def chat_options(self, requested: int, temperature: float) -> dict:
        if self.completion_budget:
            result = {'max_completion_tokens': self.budget(requested)}
            if self.reasoning_effort is not None:
                result['reasoning_effort'] = self.reasoning_effort
            return result
        return {'max_tokens': min(requested, self.output_limit), 'temperature': temperature}

    def response_options(self, requested: int) -> dict:
        result = {'max_output_tokens': self.budget(requested), 'store': False}
        if self.reasoning_effort is not None:
            result['reasoning'] = {'effort': self.reasoning_effort}
        return result


def openai_compatibility(model: str) -> OpenAICompatibility:
    # GPT-6.1 Sol/Astra require Responses for tools. Use the same API for all
    # GPT-6 variants, with low reasoning supported by Sol, Luna, and Astra.
    if re.match(r'^gpt-6(?:[.\-]|$)', model):
        return OpenAICompatibility('responses', 'low', True, 1024, 128000)
    # Preserve the existing GPT-5.1+ low-latency Chat Completions contract.
    if re.match(r'^gpt-5(?:[.\-]|$)', model):
        effort = 'none' if re.match(r'^gpt-5\.[1-9]\d*(?:[.\-]|$)', model) else None
        return OpenAICompatibility(reasoning_effort=effort, completion_budget=True, output_limit=128000)
    if re.match(r'^gpt-4\.1(?:[.\-]|$)', model):
        return OpenAICompatibility(output_limit=32768)
    if re.match(r'^gpt-4o(?:[.\-]|$)', model):
        return OpenAICompatibility(output_limit=16384)
    # ponytail: unknown compatible endpoints keep the former 4000 budget; add a family above when one needs more.
    return OpenAICompatibility()
