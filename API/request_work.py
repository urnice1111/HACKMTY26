"""Bound agent work without a waiting queue; abandon disconnected requests."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException, Request

T = TypeVar("T")
_active: set[asyncio.Task] = set()


async def run_request_work(
    request: Request, work: Callable[[], Awaitable[T]], timeout: float = 20,
) -> T:
    # Admission and registration have no await between them: one job per worker.
    if _active:
        raise HTTPException(status_code=429, detail="Agent busy; request was not queued")
    task = asyncio.ensure_future(work())
    _active.add(task)

    async def disconnected() -> None:
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)

    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait(
            {task, watcher}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED,
        )
        if watcher in done:
            watcher.result()
            raise HTTPException(status_code=499, detail="Client disconnected")
        if task in done:
            return task.result()
        raise asyncio.TimeoutError()
    finally:
        task.cancel()
        watcher.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
        _active.discard(task)
