"""MTProto client helpers."""
from __future__ import annotations

import logging

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from app.config import load_config

logger = logging.getLogger(__name__)


def get_client() -> TelegramClient:
    config = load_config()
    return TelegramClient(config.session_name, config.api_id, config.api_hash)


async def login() -> None:
    config = load_config()
    client = get_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            await client.send_code_request(config.phone)
            code = input("Enter the login code: ").strip()
            try:
                await client.sign_in(config.phone, code)
            except SessionPasswordNeededError:
                await client.sign_in(password=config.two_fa_password)

        logger.info("Authorized as user")
    finally:
        await client.disconnect()


async def check_connection() -> None:
    client = get_client()
    await client.connect()
    try:
        me = await client.get_me()
        logger.info("Connected as id=%s username=%s", me.id, me.username)
    finally:
        await client.disconnect()
