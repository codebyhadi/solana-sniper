"""
General helper functions:
- ISO datetime parsing
- Telegram message sending
"""
from telegram import Bot
from config import BOT_TOKEN, CHAT_ID, BRIGHT_YELLOW, RESET
from datetime import datetime
from typing import Optional

def parse_iso_datetime(value: str | None) -> Optional[datetime]:
    """
    Safely parse ISO datetime string (with or without Z).

    Args:
        value: ISO string or None

    Returns:
        datetime object (UTC) or None
    """
    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value or value == "-":
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def send_telegram_message(text: str) -> None:
    """
    Send formatted message to configured Telegram chat.

    Args:
        text: HTML-formatted message content
    """
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode="HTML"
        )
        print(f"{BRIGHT_YELLOW}Message sent successfully to Telegram.{RESET}")
    except Exception as e:
        print(f"Failed to send message: {e}")