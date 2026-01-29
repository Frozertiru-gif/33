"""State management helpers for resumable runs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "titles": [],
        "current_index": 0,
        "phase": "idle",
        "sent_total": 0,
        "sent_in_batch": 0,
        "sent_ids": [],
        "last_bot_chat": "",
        "last_title": "",
        "last_media_message_id": 0,
        "updated_at": "",
    }


def _merge_state(state: dict[str, Any]) -> dict[str, Any]:
    merged = _default_state()
    merged.update(state or {})
    return merged


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: str) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return _default_state()
    with state_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return _merge_state(data)


def save_state(path: str, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now_iso()
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp_path, state_path)


def dedup_has(state: dict[str, Any], msg_id: int) -> bool:
    return msg_id in state.get("sent_ids", [])


def dedup_add(state: dict[str, Any], msg_id: int, limit: int) -> None:
    sent_ids = list(state.get("sent_ids", []))
    if msg_id in sent_ids:
        return
    sent_ids.append(msg_id)
    if limit > 0 and len(sent_ids) > limit:
        sent_ids = sent_ids[-limit:]
    state["sent_ids"] = sent_ids
