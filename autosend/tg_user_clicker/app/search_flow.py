"""Search flow for selecting the first result from a bot."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.buttons import ButtonMatch, click_button
from app.config import load_config

logger = logging.getLogger(__name__)


async def _wait_for_results_message(
    client: Any,
    entity: Any,
    *,
    after_id: int,
    timeout_seconds: int,
) -> Any | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        messages = await client.get_messages(entity, limit=10)
        for message in messages:
            if message.id <= after_id:
                continue
            if message.sender_id != entity.id:
                continue
            if not getattr(message, "buttons", None):
                continue
            return message
        await asyncio.sleep(1)
    return None


async def _wait_for_next_message(
    client: Any,
    entity: Any,
    *,
    after_id: int,
    timeout_seconds: int,
) -> Any | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        messages = await client.get_messages(entity, limit=10)
        for message in messages:
            if message.id <= after_id:
                continue
            if message.sender_id != entity.id:
                continue
            return message
        await asyncio.sleep(1)
    return None


async def wait_for_message_by_id(
    client: Any,
    entity: Any,
    *,
    message_id: int,
    timeout_seconds: int,
) -> Any | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        message = await client.get_messages(entity, ids=message_id)
        if isinstance(message, list):
            message = message[0] if message else None
        if message and message.sender_id == entity.id:
            return message
        await asyncio.sleep(1)
    return None


async def run_search_and_pick_first(client: Any, bot_username: str, title: str) -> dict:
    config = load_config()
    entity = await client.get_entity(bot_username)
    send_text = f"{config.search_send_prefix}{title}"
    sent_message = await client.send_message(entity, send_text)

    results_message = await _wait_for_results_message(
        client,
        entity,
        after_id=sent_message.id,
        timeout_seconds=config.search_results_timeout_seconds,
    )
    if not results_message:
        return {"ok": False, "reason": "timeout_results"}

    buttons = getattr(results_message, "buttons", None) or []
    if not buttons or not buttons[0]:
        return {"ok": False, "reason": "no_results_buttons"}

    first_button = buttons[0][0]
    picked_button_text = getattr(first_button, "text", "") or ""
    match = ButtonMatch(button=first_button, row=0, col=0)
    await click_button(results_message, match)

    next_message = await _wait_for_next_message(
        client,
        entity,
        after_id=results_message.id,
        timeout_seconds=config.after_pick_timeout_seconds,
    )
    if not next_message:
        return {"ok": False, "reason": "timeout_after_pick"}

    return {
        "ok": True,
        "title": title,
        "results_message_id": results_message.id,
        "picked_button_text": picked_button_text,
        "next_message_id": next_message.id,
    }


async def run_inline_search_and_pick_first(
    client: Any,
    bot_username: str,
    query: str,
    timeout: int = 30,
) -> dict:
    bot = await client.get_entity(bot_username)
    last_message = await client.get_messages(bot, limit=1)
    last_message_id = last_message[0].id if last_message else 0

    results = await client.inline_query(bot, query)
    if not results:
        return {"ok": False, "reason": "no_inline_results"}

    first = results[0]
    await first.click(bot)

    next_message = await _wait_for_next_message(
        client,
        bot,
        after_id=last_message_id,
        timeout_seconds=timeout,
    )
    if not next_message:
        return {"ok": False, "reason": "timeout_after_inline_pick"}

    picked_inline_title = first.title or first.description or ""
    return {
        "ok": True,
        "query": query,
        "picked_inline_title": picked_inline_title,
        "next_message_id": next_message.id,
    }
