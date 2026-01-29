"""Command-line interface for the Telegram user client."""
from __future__ import annotations

import argparse
import asyncio
import logging

import os

from app.buttons import click_button, find_button
from app.client import check_connection, get_client, login
from app.config import load_config
from app.log import setup_logging
from app import media
from app.runner import run_titles
from app.search_flow import (
    run_inline_search_and_pick_first,
    run_search_and_pick_first,
    wait_for_message_by_id,
)
from app.series_flow import run_series_until_end, wait_for_media_after
from app.state import load_state, save_state
from app.titles import load_titles

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram MTProto user client")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("login", help="Authorize the user session")
    subparsers.add_parser("me", help="Show current session user info")

    press_parser = subparsers.add_parser("press", help="Find and press an inline button")
    press_parser.add_argument("--chat", help="Chat username or ID (defaults to BOT_USERNAME)")
    press_parser.add_argument("--contains", required=True, help="Text contained in button label")
    press_parser.add_argument("--limit", type=int, default=20, help="How many recent messages to scan")

    search_parser = subparsers.add_parser("search", help="Search by title and pick first result")
    search_parser.add_argument("--chat", required=True, help="Bot username or ID")
    search_parser.add_argument("--title", required=True, help="Title to search for")
    search_parser.add_argument("--inline", action="store_true", help="Use inline query mode")

    search_send_parser = subparsers.add_parser(
        "search-send", help="Search by title, pick first result, and send media"
    )
    search_send_parser.add_argument("--chat", required=True, help="Bot username or ID")
    search_send_parser.add_argument("--title", required=True, help="Title to search for")
    search_send_parser.add_argument("--inline", action="store_true", help="Use inline query mode")

    series_parser = subparsers.add_parser(
        "series", help="Search by title and forward all episodes with NEXT"
    )
    series_parser.add_argument("--chat", required=True, help="Bot username or ID")
    series_parser.add_argument("--title", required=True, help="Title to search for")
    series_parser.add_argument("--inline", action="store_true", help="Use inline query mode")

    run_one_parser = subparsers.add_parser(
        "run-one", help="Run a single title with resume state"
    )
    run_one_parser.add_argument("--chat", help="Bot username or ID (defaults to BOT_USERNAME)")
    run_one_parser.add_argument("--title", required=True, help="Title to search for")
    run_one_parser.add_argument("--inline", action="store_true", help="Use inline query mode")

    run_list_parser = subparsers.add_parser(
        "run-list", help="Run a list of titles with resume state"
    )
    run_list_parser.add_argument("--chat", help="Bot username or ID (defaults to BOT_USERNAME)")
    run_list_parser.add_argument("--titles-file", help="Path to titles file")

    subparsers.add_parser("status", help="Show current resume state")

    reset_parser = subparsers.add_parser("reset", help="Reset resume state")
    reset_parser.add_argument("--yes", action="store_true", help="Confirm reset")
    run_list_parser.add_argument("--inline", action="store_true", help="Use inline query mode")

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "login":
        asyncio.run(login())
    elif args.command == "me":
        asyncio.run(check_connection())
    elif args.command == "press":
        asyncio.run(press_button(args))
    elif args.command == "search":
        asyncio.run(search_and_pick(args))
    elif args.command == "search-send":
        asyncio.run(search_and_send(args))
    elif args.command == "series":
        asyncio.run(run_series(args))
    elif args.command == "run-one":
        asyncio.run(run_one(args))
    elif args.command == "run-list":
        asyncio.run(run_list(args))
    elif args.command == "status":
        show_status()
    elif args.command == "reset":
        reset_state(args)
    else:
        parser.print_help()





async def press_button(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")

        entity = await client.get_entity(chat)
        messages = await client.get_messages(entity, limit=args.limit)
        for message in messages:
            match = find_button(message, args.contains)
            if not match:
                continue
            logger.info("Found button on message id=%s with text=%s", message.id, match.button.text)
            result = await click_button(message, match)
            logger.info("Button click finished: %s", result)
            return

        logger.info("No matching buttons found for %r in last %s messages", args.contains, args.limit)
    finally:
        await client.disconnect()


async def search_and_pick(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")

        if args.inline:
            result = await run_inline_search_and_pick_first(client, chat, args.title)
        else:
            result = await run_search_and_pick_first(client, chat, args.title)
        if not result.get("ok"):
            logger.info("reason=%s", result.get("reason"))
            return

        if args.inline:
            logger.info("picked_inline_title=%s", result["picked_inline_title"])
        else:
            logger.info("picked_button_text=%s", result["picked_button_text"])
        logger.info("next_message_id=%s", result["next_message_id"])
    finally:
        await client.disconnect()


async def search_and_send(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")
    if not config.target_chat_id:
        raise ValueError("TARGET_CHAT_ID is required for search-send.")

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")

        if args.inline:
            result = await run_inline_search_and_pick_first(client, chat, args.title)
        else:
            result = await run_search_and_pick_first(client, chat, args.title)
        if not result.get("ok"):
            logger.info("reason=%s", result.get("reason"))
            return

        entity = await client.get_entity(chat)
        next_message_id = result["next_message_id"]
        message = await wait_for_message_by_id(
            client,
            entity,
            message_id=next_message_id,
            timeout_seconds=config.after_pick_timeout_seconds,
        )
        if not message:
            logger.info("reason=timeout_after_pick")
            return

        if not media.is_media_message(message):
            logger.info("non_media_message_id=%s", message.id)
            return

        if media.already_sent(message):
            logger.info("duplicate_message_id=%s", message.id)
            return

        sent = await media.send_to_target(
            client, message, config.target_chat_id, config.forward_mode
        )
        if not sent:
            return

        media.mark_sent(message)
        media.record_sent(config.batch_size)
        logger.info(
            "sent_total=%s sent_in_batch=%s message_id=%s",
            media.sent_total,
            media.sent_in_batch,
            message.id,
        )
    finally:
        await client.disconnect()


async def run_series(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")
    if not config.target_chat_id:
        raise ValueError("TARGET_CHAT_ID is required for series.")

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")

        if args.inline:
            result = await run_inline_search_and_pick_first(client, chat, args.title)
        else:
            result = await run_search_and_pick_first(client, chat, args.title)
        if not result.get("ok"):
            logger.info("reason=%s", result.get("reason"))
            return

        entity = await client.get_entity(chat)
        next_message_id = result["next_message_id"]
        message = await wait_for_media_after(
            client,
            entity,
            after_id=next_message_id - 1,
            timeout_seconds=config.wait_next_media_timeout_seconds,
        )
        if not message:
            logger.info("reason=timeout_after_pick_media")
            return

        series_result = await run_series_until_end(client, chat, message.id)
        logger.info("reason=%s", series_result.get("reason"))
        logger.info("sent_total=%s", series_result.get("sent_total"))
        logger.info("last_message_id=%s", series_result.get("last_message_id"))
    finally:
        await client.disconnect()


async def run_one(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")
    if not config.target_chat_id:
        raise ValueError("TARGET_CHAT_ID is required for run-one.")

    state = load_state(config.state_path)
    state["titles"] = [args.title]
    state["current_index"] = 0
    save_state(config.state_path, state)

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")
        search_flow = run_inline_search_and_pick_first if args.inline else run_search_and_pick_first
        await run_titles(client, chat, [args.title], state, search_flow=search_flow)
    finally:
        await client.disconnect()


async def run_list(args: argparse.Namespace) -> None:
    config = load_config()
    chat = args.chat or config.bot_username
    if not chat:
        raise ValueError("Chat is required. Provide --chat or set BOT_USERNAME.")
    if not config.target_chat_id:
        raise ValueError("TARGET_CHAT_ID is required for run-list.")

    state = load_state(config.state_path)
    titles_path = args.titles_file or config.titles_path
    if not state.get("titles"):
        titles = load_titles(titles_path)
        state["titles"] = titles
        state["current_index"] = int(state.get("current_index", 0))
        save_state(config.state_path, state)
    else:
        titles = list(state.get("titles", []))
        logger.info("using titles from state (%s items)", len(titles))

    if not titles:
        logger.info("No titles to process.")
        return

    # 🔽 ВАЖНО: выбираем функцию поиска в зависимости от флага --inline
    search_flow = run_inline_search_and_pick_first if getattr(args, "inline", False) else run_search_and_pick_first

    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("User session is not authorized. Run the login command first.")

        # 🔽 ВАЖНО: прокидываем search_flow в runner
        await run_titles(client, chat, titles, state, search_flow=search_flow)
    finally:
        await client.disconnect()



def show_status() -> None:
    config = load_config()
    state = load_state(config.state_path)
    total_titles = len(state.get("titles", []))
    current_index = int(state.get("current_index", 0))
    last_title = state.get("last_title", "")
    sent_total = state.get("sent_total", 0)
    last_media_message_id = state.get("last_media_message_id", 0)
    print(f"{current_index} / {total_titles}")
    print(f"last_title: {last_title}")
    print(f"sent_total: {sent_total}")
    print(f"last_media_message_id: {last_media_message_id}")


def reset_state(args: argparse.Namespace) -> None:
    if not args.yes:
        raise RuntimeError("Reset requires --yes confirmation.")
    config = load_config()
    if os.path.exists(config.state_path):
        os.remove(config.state_path)
    state = load_state(config.state_path)
    save_state(config.state_path, state)
if __name__ == "__main__":
    main()