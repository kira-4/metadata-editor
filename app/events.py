"""Server-Sent Events fan-out, safe to publish from any thread.

Routes run in FastAPI's threadpool and the scanner runs in its own thread, but
asyncio queues belong to the event loop. `publish_event` hops onto the loop with
`call_soon_threadsafe`, so callers never need to be async.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, List, Optional

logger = logging.getLogger(__name__)

CLIENT_QUEUE_SIZE = 100

_loop: Optional[asyncio.AbstractEventLoop] = None
_clients: List[asyncio.Queue] = []


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Remember the server's event loop (called at startup and on SSE connect)."""
    global _loop
    _loop = loop


def _fan_out(data: dict) -> None:
    for queue in list(_clients):
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            # A stalled client just misses events; it reconciles on its next poll
            logger.warning("SSE client queue full; dropping event %s", data.get("type"))


def publish_event(data: dict) -> None:
    """Send an event to all SSE clients. Callable from any thread."""
    if _loop is None or _loop.is_closed():
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _loop:
        _fan_out(data)
    else:
        _loop.call_soon_threadsafe(_fan_out, data)


async def event_stream() -> AsyncIterator[str]:
    """Yield JSON event payloads for one connected client (framed by EventSourceResponse)."""
    set_loop(asyncio.get_running_loop())
    queue: asyncio.Queue = asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
    _clients.append(queue)
    try:
        while True:
            data = await queue.get()
            yield json.dumps(data)
    except asyncio.CancelledError:
        pass
    finally:
        # Always remove the queue so disconnected clients don't accumulate
        try:
            _clients.remove(queue)
        except ValueError:
            pass
