"""Media detection and forwarding helpers."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

sent_message_ids: set[int] = set()
sent_total = 0
sent_in_batch = 0


def is_media_message(msg: Any) -> bool:
    return bool(getattr(msg, "video", None) or getattr(msg, "document", None))


async def send_to_target(client, msg, target_chat_id, mode="copy"):
    try:
        # Универсальный вариант для всех версий Telethon
        await client.forward_messages(
            entity=target_chat_id,
            messages=msg,
            from_peer=msg.chat_id,
        )
        return True
    except Exception:
        logger.exception(
            f"Failed to send message id={msg.id} to target={target_chat_id}"
        )
        return False


def already_sent(msg: Any) -> bool:
    return msg.id in sent_message_ids


def mark_sent(msg: Any) -> None:
    sent_message_ids.add(msg.id)


def record_sent(batch_size: int) -> None:
    global sent_total
    global sent_in_batch

    sent_total += 1
    sent_in_batch += 1
    if sent_in_batch == batch_size:
        logger.info("batch complete: %s", sent_total)
        sent_in_batch = 0
