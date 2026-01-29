"""FastAPI server for running titles and viewing status."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.client import get_client
from app.config import load_config
from app.log import LOG_FORMAT, setup_logging
from app.runner import run_titles
from app.search_flow import run_inline_search_and_pick_first, run_search_and_pick_first
from app.state import load_state, save_state
from app.titles import load_titles

logger = logging.getLogger(__name__)


LOG_BUFFER: deque[str] = deque(maxlen=2000)


class RingBufferHandler(logging.Handler):
    def __init__(self, buffer: deque[str]) -> None:
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self.buffer.append(message)


setup_logging()
ring_handler = RingBufferHandler(LOG_BUFFER)
ring_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.getLogger().addHandler(ring_handler)


class RunOneRequest(BaseModel):
    title: str
    bot_username: str | None = None
    inline: bool = False


class RunListRequest(BaseModel):
    titles: list[str] | None = None
    titles_file: str | None = None
    bot_username: str | None = None
    inline: bool = False


@dataclass
class RunStatus:
    running: bool
    started_at: str | None
    last_error: str | None


class RunManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.current_task: asyncio.Task | None = None
        self.stop_event: asyncio.Event | None = None
        self.started_at: str | None = None
        self.last_error: str | None = None

    def status(self) -> RunStatus:
        running = self.current_task is not None and not self.current_task.done()
        return RunStatus(running=running, started_at=self.started_at, last_error=self.last_error)

    async def start(self, titles: list[str], bot_username: str, inline: bool) -> bool:
        async with self._lock:
            if self.current_task is not None and not self.current_task.done():
                return False
            self.stop_event = asyncio.Event()
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.last_error = None
            self.current_task = asyncio.create_task(
                self._run_titles(titles, bot_username, inline)
            )
            return True

    async def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
        if self.current_task is not None and not self.current_task.done():
            config = load_config()
            state = load_state(config.state_path)
            state["phase"] = "stopping"
            save_state(config.state_path, state)

    async def _run_titles(self, titles: list[str], bot_username: str, inline: bool) -> None:
        config = load_config()
        if not config.target_chat_id:
            self.last_error = "missing_target_chat_id"
            logger.error("TARGET_CHAT_ID is required to run titles")
            state = load_state(config.state_path)
            state["phase"] = "idle"
            save_state(config.state_path, state)
            return

        client = get_client()
        await client.connect()
        try:
            if not await client.is_user_authorized():
                self.last_error = "not_authorized"
                logger.error("User session is not authorized. Run login first.")
                state = load_state(config.state_path)
                state["phase"] = "idle"
                save_state(config.state_path, state)
                return

            search_flow = (
                run_inline_search_and_pick_first if inline else run_search_and_pick_first
            )
            state = load_state(config.state_path)
            state["phase"] = "running"
            save_state(config.state_path, state)
            await run_titles(
                client,
                bot_username,
                titles,
                state,
                search_flow=search_flow,
                stop_event=self.stop_event,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Runner failed")
            self.last_error = f"error:{exc.__class__.__name__}"
            state = load_state(config.state_path)
            state["phase"] = "idle"
            save_state(config.state_path, state)
        finally:
            await client.disconnect()


app = FastAPI()
run_manager = RunManager()


@app.get("/")
async def index() -> FileResponse:
    static_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(static_path)


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    config = load_config()
    state = load_state(config.state_path)
    status = run_manager.status()
    total_titles = len(state.get("titles", []))
    return {
        "state": state,
        "summary": {
            "phase": state.get("phase"),
            "current_index": int(state.get("current_index", 0)),
            "total_titles": total_titles,
            "last_title": state.get("last_title", ""),
            "sent_total": state.get("sent_total", 0),
            "last_media_message_id": state.get("last_media_message_id", 0),
        },
        "run_manager": {
            "running": status.running,
            "started_at": status.started_at,
            "last_error": status.last_error,
        },
    }


@app.post("/api/run/one")
async def api_run_one(payload: RunOneRequest) -> dict[str, Any]:
    config = load_config()
    bot_username = payload.bot_username or config.bot_username
    if not bot_username:
        raise HTTPException(status_code=400, detail="bot_username is required")

    state = load_state(config.state_path)
    state["titles"] = [payload.title]
    state["current_index"] = 0
    save_state(config.state_path, state)

    started = await run_manager.start([payload.title], bot_username, payload.inline)
    if not started:
        raise HTTPException(status_code=409, detail="already_running")
    return {"ok": True}


@app.post("/api/run/list")
async def api_run_list(payload: RunListRequest) -> dict[str, Any]:
    config = load_config()
    bot_username = payload.bot_username or config.bot_username
    if not bot_username:
        raise HTTPException(status_code=400, detail="bot_username is required")

    state = load_state(config.state_path)
    if payload.titles is not None:
        titles = payload.titles
    else:
        titles_path = payload.titles_file or config.titles_path
        titles = load_titles(titles_path)

    state["titles"] = titles
    state["current_index"] = 0
    save_state(config.state_path, state)

    started = await run_manager.start(titles, bot_username, payload.inline)
    if not started:
        raise HTTPException(status_code=409, detail="already_running")
    return {"ok": True, "count": len(titles)}


@app.post("/api/stop")
async def api_stop() -> dict[str, Any]:
    await run_manager.stop()
    return {"ok": True}


@app.post("/api/reset")
async def api_reset() -> dict[str, Any]:
    status = run_manager.status()
    if status.running:
        raise HTTPException(status_code=409, detail="already_running")
    config = load_config()
    state_path = Path(config.state_path)
    if state_path.exists():
        state_path.unlink()
    state = load_state(config.state_path)
    save_state(config.state_path, state)
    run_manager.last_error = None
    return {"ok": True}


@app.get("/api/logs")
async def api_logs(tail: int = Query(default=200, ge=1, le=2000)) -> dict[str, Any]:
    lines = list(LOG_BUFFER)[-tail:]
    return {"lines": lines}
