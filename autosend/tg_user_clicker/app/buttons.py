"""Helpers for working with inline keyboard buttons."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any, Iterable

from telethon.errors import FloodWaitError

logger = logging.getLogger(__name__)

_SPACE_RE = re.compile(r"\s+")
_ALLOWED_RE = re.compile(r"[^\w\s.,!?\\-]")


@dataclass(frozen=True)
class ButtonMatch:
    button: Any
    row: int
    col: int


def normalize_text(text: str) -> str:
    normalized = text.strip().lower().replace("ё", "е")
    normalized = _ALLOWED_RE.sub("", normalized)
    normalized = _SPACE_RE.sub(" ", normalized)
    return normalized


def _iter_buttons(button_rows: Iterable[Iterable[Any]]) -> Iterable[ButtonMatch]:
    for row_index, row in enumerate(button_rows):
        for col_index, button in enumerate(row):
            yield ButtonMatch(button=button, row=row_index, col=col_index)


def find_button(message: Any, contains_text: str) -> ButtonMatch | None:
    if not message or not getattr(message, "buttons", None):
        return None

    target = normalize_text(contains_text)
    if not target:
        return None

    for match in _iter_buttons(message.buttons):
        button_text = getattr(match.button, "text", "") or ""
        if target in normalize_text(button_text):
            return match

    return None


def is_callback_button(button: Any) -> bool:
    return bool(getattr(button, "data", None))


async def click_button(message: Any, match: ButtonMatch) -> Any:
    if not is_callback_button(match.button):
        raise ValueError("button is not callback")

    try:
        return await message.click(i=match.row, j=match.col)
    except FloodWaitError:
        raise
    except Exception:
        logger.exception("Failed to click button at row=%s col=%s", match.row, match.col)
        raise
