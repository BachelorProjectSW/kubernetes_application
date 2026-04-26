from __future__ import annotations

import queue
import threading
from typing import Any
from .logger import log_request

from pydantic import BaseModel

from ..db.postgres import save_model_log, save_terminal_debug


_log_queue: queue.Queue[Any] = queue.Queue()
_worker_thread: threading.Thread | None = None
_STOP = object()


def enqueue_terminal_log(
    config_id: str | None,
    message: str,
    level: str,
    payload: dict[str, Any],
) -> None:
    """Queue a terminal/debug log for DB persistence."""
    _log_queue.put_nowait(
        {
            "kind": "terminal",
            "config_id": config_id,
            "message": message,
            "level": level,
            "payload": payload,
        }
    )


def enqueue_model_log(config_id: str | None, model: BaseModel) -> None:
    """Queue a Pydantic log model for DB persistence."""
    _log_queue.put_nowait(
        {
            "kind": "model",
            "config_id": config_id,
            "model": model,
        }
    )


def get_log_queue_size() -> int:
    return _log_queue.qsize()


def wait_for_log_queue(timeout: float = 5.0) -> bool:
    """Wait until queued log writes are flushed, or return False on timeout."""
    done = threading.Event()

    def _waiter() -> None:
        _log_queue.join()
        done.set()

    threading.Thread(target=_waiter, daemon=True).start()
    return done.wait(timeout)


def _log_worker() -> None:
    while True:
        item = _log_queue.get()

        try:
            if item is _STOP:
                return

            if not isinstance(item, dict):
                continue

            if item["kind"] == "terminal":
                save_terminal_debug(
                    item["config_id"],
                    item["message"],
                    item["level"],
                    item["payload"],
                )

            elif item["kind"] == "model":
                save_model_log(
                    item["config_id"],
                    item["model"],
                )

        except Exception:
            # Do not call structlog here, or it can create recursive logging.
            pass

        finally:
            _log_queue.task_done()


def start_log_worker() -> None:
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _worker_thread = threading.Thread(
        target=_log_worker,
        name="db-log-worker",
        daemon=True,
    )
    _worker_thread.start()


def stop_log_worker(timeout: float = 5.0) -> None:
    try:
        _log_queue.put_nowait(_STOP)
    except Exception:
        return

    if _worker_thread is not None:
        _worker_thread.join(timeout=timeout)

async def log_request_fresh_async(*args, **kwargs):
    """
    Persist RequestLog before continuing, without blocking the async event loop.
    Use this for logs used by cluster scoring.
    """
    return await asyncio.to_thread(log_request, *args, **kwargs)