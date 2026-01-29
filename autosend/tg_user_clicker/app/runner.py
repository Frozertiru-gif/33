"""Runner for processing titles with resume support."""
from __future__ import annotations

import logging
import asyncio
from typing import Any

from app import media
from app.config import load_config
from app.search_flow import run_search_and_pick_first
from app.series_flow import run_series_until_end, wait_for_media_after
from app.state import dedup_add, dedup_has, save_state

logger = logging.getLogger(__name__)


def _record_sent(state: dict[str, Any], msg_id: int, *, batch_size: int, dedup_limit: int) -> None:
    dedup_add(state, msg_id, dedup_limit)
    state["sent_total"] = int(state.get("sent_total", 0)) + 1
    state["sent_in_batch"] = int(state.get("sent_in_batch", 0)) + 1
    if state["sent_in_batch"] >= batch_size:
        logger.info("batch complete: %s", state["sent_total"])
        state["sent_in_batch"] = 0


async def run_titles(
    client: Any,
    bot_username: str,
    titles: list[str],
    state: dict[str, Any],
    *,
    search_flow: Any = run_search_and_pick_first,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    config = load_config()
    state["phase"] = "running"
    state["last_bot_chat"] = bot_username
    save_state(config.state_path, state)

    try:
        for index in range(state.get("current_index", 0), len(titles)):
            if stop_event is not None and stop_event.is_set():
                logger.info("stop requested before title index=%s", index)
                break
            title = titles[index]
            resume_from_message_id = 0
            if state.get("last_title") == title and state.get("last_media_message_id"):
                resume_from_message_id = int(state["last_media_message_id"])

            if resume_from_message_id:
                logger.info("resume title=%s from message_id=%s", title, resume_from_message_id)
            else:
                state["last_title"] = title
                state["last_media_message_id"] = 0
                save_state(config.state_path, state)

                result = await search_flow(
                    client,
                    bot_username,
                    title,
                    stop_event=stop_event,
                )
                if result.get("reason") == "stopped":
                    logger.info("reason=stopped")
                    break
                if not result.get("ok"):
                    logger.info("reason=%s", result.get("reason"))
                    state["current_index"] = index + 1
                    save_state(config.state_path, state)
                    continue

                entity = await client.get_entity(bot_username)
                next_message_id = result["next_message_id"]
                first_media = await wait_for_media_after(
                    client,
                    entity,
                    after_id=next_message_id - 1,
                    timeout_seconds=config.wait_next_media_timeout_seconds,
                    stop_event=stop_event,
                )
                if not first_media:
                    if stop_event is not None and stop_event.is_set():
                        logger.info("reason=stopped")
                        break
                    logger.info("reason=no_media_after_pick")
                    state["current_index"] = index + 1
                    save_state(config.state_path, state)
                    continue

                state["last_media_message_id"] = first_media.id
                if not dedup_has(state, first_media.id):
                    sent = await media.send_to_target(
                        client,
                        first_media,
                        config.target_chat_id,
                        config.forward_mode,
                    )
                    if sent:
                        _record_sent(
                            state,
                            first_media.id,
                            batch_size=config.batch_size,
                            dedup_limit=config.sent_dedup_limit,
                        )
                        logger.info("sent to target msg_id=%s", first_media.id)
                    save_state(config.state_path, state)

                resume_from_message_id = first_media.id

            series_result = await run_series_until_end(
                client,
                bot_username,
                resume_from_message_id,
                state=state,
                dedup_limit=config.sent_dedup_limit,
                state_path=config.state_path,
                stop_event=stop_event,
            )
            logger.info("reason=%s", series_result.get("reason"))
            if series_result.get("reason") == "stopped":
                break
            state["current_index"] = index + 1
            save_state(config.state_path, state)

            if config.search_delay_seconds > 0:
                if stop_event is not None and stop_event.is_set():
                    logger.info("stop requested during delay")
                    break
                if stop_event is None:
                    await asyncio.sleep(config.search_delay_seconds)
                else:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=config.search_delay_seconds,
                        )
                        logger.info("stop requested during delay")
                        break
                    except asyncio.TimeoutError:
                        pass
        return state
    finally:
        state["phase"] = "idle"
        save_state(config.state_path, state)
