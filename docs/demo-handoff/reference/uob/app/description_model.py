"""Connect Helios description suggestions to the demo's compatible model client."""
import asyncio
import json
import time

import httpx

from .model_client import chat_completion


class DescriptionModel:
    def __init__(self, settings):
        self.settings = settings
        self.deadline = time.monotonic() + 180
        self.calls = 0

    def complete_json(self, system, user):
        # Helios calls this synchronous interface from the discovery worker thread.
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.calls >= 40:
            raise RuntimeError('Description suggestion budget reached.')
        self.calls += 1
        try:
            return asyncio.run(self._complete(system, user, min(30, remaining)))
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError('Description suggestion request failed.') from None

    async def _complete(self, system, user, timeout):
        settings = self.settings
        headers = {'Authorization': 'Bearer ' + settings.llm_key} if settings.llm_key else {}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await chat_completion(
                client, settings.llm_url.rstrip('/') + '/chat/completions', headers,
                settings.llm_model, [{'role': 'system', 'content': system},
                                     {'role': 'user', 'content': user}], 4000, timeout)
        content = response.json()['choices'][0]['message']['content']
        # Compatible endpoints can wrap their JSON answer in a Markdown code fence.
        if isinstance(content, str) and content.strip().startswith('```'):
            content = content.strip().split('\n', 1)[1].rsplit('```', 1)[0].strip()
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError('Expected a JSON object.')
        return result
