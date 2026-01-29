"""Series flow for walking through NEXT episodes."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app import media
from app.buttons import click_button, find_button
from app.config import load_config
from app.state import dedup_add, dedup_has, save_state

logger = logging.getLogger(__name__)

_RECENT_FETCH_LIMIT = 50


async def _get_message_by_id(client: Any, entity: Any, message_id: int) -> Any | None:
    message = await client.get_messages(entity, ids=message_id)
    if isinstance(message, list):
        return message[0] if message else None
    return message


async def _find_start_message(client: Any, entity: Any, start_id: int) -> Any | None:
    message = await _get_message_by_id(client, entity, start_id)
    if message and message.sender_id == entity.id:
        return message

    messages = await client.get_messages(entity, limit=_RECENT_FETCH_LIMIT)
    closest = None
    for msg in messages:
        if msg.sender_id != entity.id:
            continue
        if msg.id <= start_id:
            continue
        if not media.is_media_message(msg):
            continue
        if closest is None or msg.id < closest.id:
            closest = msg
    return closest


async def _wait_for_next_media_message(
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
            if not media.is_media_message(message):
                continue
            return message
        await asyncio.sleep(1)
    return None


async def wait_for_media_after(
    client: Any,
    entity: Any,
    *,
    after_id: int,
    timeout_seconds: int,
) -> Any | None:
    return await _wait_for_next_media_message(
        client,
        entity,
        after_id=after_id,
        timeout_seconds=timeout_seconds,
    )


async def run_series_until_end(
    client: Any,
    bot_username: str,
    start_from_message_id: int,
    *,
    state: dict[str, Any] | None = None,
    dedup_limit: int = 0,
    state_path: str | None = None,
) -> dict:
    config = load_config()
    entity = await client.get_entity(bot_username)
    current_msg = await _find_start_message(client, entity, start_from_message_id)

    if not current_msg or not media.is_media_message(current_msg):
        last_id = current_msg.id if current_msg else start_from_message_id
        return {
            "ok": False,
            "reason": "start_message_not_media",
            "sent_total": 0,
            "last_message_id": last_id,
        }

    sent_total = 0

    def already_sent(message: Any) -> bool:
        if state is None:
            return media.already_sent(message)
        return dedup_has(state, message.id)

    def record_sent(message: Any) -> None:
        if state is None:
            media.mark_sent(message)
            media.record_sent(config.batch_size)
            return
        dedup_add(state, message.id, dedup_limit)
        state["sent_total"] = int(state.get("sent_total", 0)) + 1
        state["sent_in_batch"] = int(state.get("sent_in_batch", 0)) + 1
        if state["sent_in_batch"] >= config.batch_size:
            logger.info("batch complete: %s", state["sent_total"])
            state["sent_in_batch"] = 0
        state["last_media_message_id"] = message.id
        if state_path:
            save_state(state_path, state)

    if state is not None:
        state["last_media_message_id"] = current_msg.id
        if state_path:
            save_state(state_path, state)

    if not already_sent(current_msg):
        sent = await media.send_to_target(
            client, current_msg, config.target_chat_id, config.forward_mode
        )
        if sent:
            record_sent(current_msg)
            sent_total += 1
            logger.info("sent to target msg_id=%s", current_msg.id)

    while True:
        match = find_button(current_msg, config.button_next_text)
        if not match:
            reason = "end_no_next_button"
            logger.info("end reason=%s", reason)
            return {
                "ok": True,
                "reason": reason,
                "sent_total": sent_total,
                "last_message_id": current_msg.id,
            }

        next_media = None
        for _ in range(config.max_retries_next):
            await click_button(current_msg, match)
            logger.info("clicked NEXT on msg_id=%s", current_msg.id)
            await asyncio.sleep(config.wait_after_click_seconds)
            next_media = await _wait_for_next_media_message(
                client,
                entity,
                after_id=current_msg.id,
                timeout_seconds=config.wait_next_media_timeout_seconds,
            )
            if next_media:
                break

        if not next_media:
            reason = "end_timeout_no_new_media"
            logger.info("end reason=%s", reason)
            return {
                "ok": True,
                "reason": reason,
                "sent_total": sent_total,
                "last_message_id": current_msg.id,
            }

        logger.info("received media msg_id=%s", next_media.id)
        current_msg = next_media
        send_task = asyncio.create_task(
            media.send_to_target(client, current_msg, config.target_chat_id, config.forward_mode)
        )

        if state is not None:
            state["last_media_message_id"] = current_msg.id
            if state_path:
                save_state(state_path, state)

        if already_sent(current_msg):
            continue

        sent = await media.send_to_target(
            client, current_msg, config.target_chat_id, config.forward_mode
        )
        if not sent:
            continue

        record_sent(current_msg)
        sent_total += 1
        logger.info("sent to target msg_id=%s", current_msg.id)
