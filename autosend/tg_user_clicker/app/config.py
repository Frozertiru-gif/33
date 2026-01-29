"""Configuration loader for Telegram user client."""
from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    phone: str
    two_fa_password: str
    session_name: str
    bot_username: str
    button_next_text: str
    button_series_text: str
    button_quality_text: str
    button_back_text: str
    search_results_timeout_seconds: int
    after_pick_timeout_seconds: int
    wait_next_media_timeout_seconds: int
    max_retries_next: int
    wait_after_click_seconds: int
    search_delay_seconds: int
    search_send_prefix: str
    target_chat_id: str
    batch_size: int
    forward_mode: str
    state_path: str
    titles_path: str
    sent_dedup_limit: int


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> Config:
    load_dotenv()

    api_id_raw = _require_env("TG_API_ID")
    api_hash = _require_env("TG_API_HASH")
    phone = _require_env("TG_PHONE")
    two_fa_password = os.getenv("TG_2FA_PASSWORD", "")
    session_name = os.getenv("SESSION_NAME", "user")
    bot_username = os.getenv("BOT_USERNAME", "")
    button_next_text = os.getenv("BUTTON_NEXT_TEXT", "Вперёд")
    button_series_text = os.getenv("BUTTON_SERIES_TEXT", "Серии")
    button_quality_text = os.getenv("BUTTON_QUALITY_TEXT", "Качество")
    button_back_text = os.getenv("BUTTON_BACK_TEXT", "Назад")
    search_results_timeout_raw = os.getenv("SEARCH_RESULTS_TIMEOUT_SECONDS", "30")
    after_pick_timeout_raw = os.getenv("AFTER_PICK_TIMEOUT_SECONDS", "30")
    wait_next_media_timeout_raw = os.getenv("WAIT_NEXT_MEDIA_TIMEOUT_SECONDS", "60")
    max_retries_next_raw = os.getenv("MAX_RETRIES_NEXT", "3")
    wait_after_click_raw = os.getenv("WAIT_AFTER_CLICK_SECONDS", "1")
    search_delay_raw = os.getenv("SEARCH_DELAY_SECONDS", "0")
    search_send_prefix = os.getenv("SEARCH_SEND_PREFIX", "")
    target_chat_id = os.getenv("TARGET_CHAT_ID", "")
    batch_size_raw = os.getenv("BATCH_SIZE", "10")
    forward_mode = os.getenv("FORWARD_MODE", "copy").lower()
    state_path = os.getenv("STATE_PATH", "./state.json")
    titles_path = os.getenv("TITLES_PATH", "./titles.txt")
    sent_dedup_limit_raw = os.getenv("SENT_DEDUP_LIMIT", "2000")

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ValueError("TG_API_ID must be an integer") from exc

    try:
        search_results_timeout_seconds = int(search_results_timeout_raw)
    except ValueError as exc:
        raise ValueError("SEARCH_RESULTS_TIMEOUT_SECONDS must be an integer") from exc

    try:
        after_pick_timeout_seconds = int(after_pick_timeout_raw)
    except ValueError as exc:
        raise ValueError("AFTER_PICK_TIMEOUT_SECONDS must be an integer") from exc

    try:
        wait_next_media_timeout_seconds = int(wait_next_media_timeout_raw)
    except ValueError as exc:
        raise ValueError("WAIT_NEXT_MEDIA_TIMEOUT_SECONDS must be an integer") from exc

    try:
        max_retries_next = int(max_retries_next_raw)
    except ValueError as exc:
        raise ValueError("MAX_RETRIES_NEXT must be an integer") from exc

    try:
        wait_after_click_seconds = int(wait_after_click_raw)
    except ValueError as exc:
        raise ValueError("WAIT_AFTER_CLICK_SECONDS must be an integer") from exc
    try:
        search_delay_seconds = int(search_delay_raw)
    except ValueError as exc:
        raise ValueError("SEARCH_DELAY_SECONDS must be an integer") from exc


    try:
        batch_size = int(batch_size_raw)
    except ValueError as exc:
        raise ValueError("BATCH_SIZE must be an integer") from exc

    if forward_mode not in {"copy", "forward"}:
        raise ValueError("FORWARD_MODE must be 'copy' or 'forward'")

    try:
        sent_dedup_limit = int(sent_dedup_limit_raw)
    except ValueError as exc:
        raise ValueError("SENT_DEDUP_LIMIT must be an integer") from exc

    return Config(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        two_fa_password=two_fa_password,
        session_name=session_name,
        bot_username=bot_username,
        button_next_text=button_next_text,
        button_series_text=button_series_text,
        button_quality_text=button_quality_text,
        button_back_text=button_back_text,
        search_results_timeout_seconds=search_results_timeout_seconds,
        after_pick_timeout_seconds=after_pick_timeout_seconds,
        wait_next_media_timeout_seconds=wait_next_media_timeout_seconds,
        max_retries_next=max_retries_next,
        wait_after_click_seconds=wait_after_click_seconds,
        search_delay_seconds=search_delay_seconds,
        search_send_prefix=search_send_prefix,
        target_chat_id=target_chat_id,
        batch_size=batch_size,
        forward_mode=forward_mode,
        state_path=state_path,
        titles_path=titles_path,
        sent_dedup_limit=sent_dedup_limit,
    )
