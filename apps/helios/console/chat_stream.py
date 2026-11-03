"""Bounded NDJSON transport. Progress reports actions, never private reasoning."""
from __future__ import annotations

import asyncio
import json
import logging
from queue import Empty, Queue
from threading import BoundedSemaphore, Event, Thread
import time

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from helios_core.demo.chat import answer
from helios_core.demo.registry import DemoError
from helios_core.retrieval.service import RetrievalError

SLOTS = BoundedSemaphore(4)
LOGGER = logging.getLogger(__name__)


def stream_answer(playground, payload, llm_factory):
    playground.runtime.check_binding(payload)
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, 'All chat workers are busy. Please retry shortly.')
    messages, stopped = Queue(), Event()

    def emit(stage, detail):
        if stopped.is_set():
            raise DemoError('The chat request was stopped.')
        messages.put({'type': 'retrieval' if stage == 'retrieval' else 'progress',
                      'stage': stage, 'detail': detail})

    def work():
        try:
            result = answer(playground, payload, llm_factory, emit)
            if not stopped.is_set():
                messages.put({'type': 'result', 'result': result})
        except (DemoError, RetrievalError) as exc:
            messages.put({'type': 'error', 'message': str(exc)})
        except Exception:
            LOGGER.exception('Chat execution failed')
            messages.put({'type': 'error', 'message': 'The request could not complete. No verified answer is available. Retry or check the query model configuration.'})
        finally:
            messages.put(None)
            SLOTS.release()

    async def events():
        deadline = time.monotonic() + 240
        try:
            while time.monotonic() < deadline:
                try:
                    item = await asyncio.to_thread(messages.get, True, 1)
                except Empty:
                    yield json.dumps({'type': 'heartbeat'}) + '\n'
                    continue
                if item is None:
                    return
                yield json.dumps(item, ensure_ascii=False) + '\n'
            yield json.dumps({'type': 'error', 'message': 'The request exceeded its time limit. No complete answer is available.'}) + '\n'
        finally:
            stopped.set()

    Thread(target=work, daemon=True).start()
    return StreamingResponse(events(), media_type='application/x-ndjson',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
