from __future__ import annotations

import re
from typing import Any

from ly_next.core.logger import get_logger
from ly_next.messaging.onebot_commands import OneBotCommandEvent, register_onebot_command_handler

from jmcomic_plugin.help_text import build_jm_help_message

logger = get_logger(__name__)

_HELP_RE = re.compile(
    r"^(?:/)?jm\s*帮助$|^(?:/)?jm\s+help$",
    re.IGNORECASE,
)

_TG_HOOK_INSTALLED = False


def is_jm_help_trigger(text: str) -> bool:
    return bool(_HELP_RE.match(str(text or "").strip()))


def _import_telegram_commands() -> Any | None:
    try:
        import ly_next.messaging.telegram_commands as mod

        return mod
    except ImportError:
        return None


async def _send_onebot_text(event: OneBotCommandEvent, text: str) -> None:
    if event.message_type == "group" and event.group_id is not None:
        await event.session.send_text_message(
            message_type="group",
            group_id=event.group_id,
            text=text,
        )
    else:
        await event.session.send_text_message(
            message_type="private",
            user_id=event.user_id,
            text=text,
        )


async def handle_jm_help_onebot(event: OneBotCommandEvent) -> bool:
    if not is_jm_help_trigger(event.text):
        return False
    await _send_onebot_text(event, build_jm_help_message(channel="qq"))
    return True


async def handle_jm_help_telegram(event: Any) -> bool:
    if not is_jm_help_trigger(event.text):
        return False
    try:
        import telegram_bot.handler as tg_handler
    except ImportError:
        logger.warning("[jmcomic/help] telegram_bot not loaded")
        return True
    await tg_handler._send_message(
        event.client,
        event.token,
        event.chat_id,
        build_jm_help_message(channel="telegram"),
    )
    return True


def register_jm_help_commands() -> None:
    register_onebot_command_handler(handle_jm_help_onebot, priority=40)

    tg_commands = _import_telegram_commands()
    if tg_commands is None:
        logger.warning(
            "[jmcomic/help] ly_next.messaging.telegram_commands not found; "
            "QQ jm帮助 / #车牌 still work, Telegram jm帮助 needs a newer LY-NEXT core "
            "(file ly_next/messaging/telegram_commands.py)"
        )
        return

    tg_commands.register_telegram_command_handler(handle_jm_help_telegram, priority=40)
    install_telegram_help_hook()


def install_telegram_help_hook() -> None:
    """Attach telegram_commands dispatch without modifying telegram_bot plugin."""
    global _TG_HOOK_INSTALLED
    if _TG_HOOK_INSTALLED:
        return

    tg_commands = _import_telegram_commands()
    if tg_commands is None:
        return

    try:
        import telegram_bot.handler as tg_handler
    except ImportError:
        return

    original = tg_handler.handle_update

    async def wrapped(client, token: str, update: dict) -> None:
        settings = tg_handler.get_telegram_settings()

        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            await original(client, token, update)
            return
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            await original(client, token, update)
            return

        user = message.get("from") or {}
        user_id = int(user.get("id") or 0)
        chat_id = int(chat.get("id") or 0)
        text = str(message.get("text") or "").strip()
        if not chat_id:
            await original(client, token, update)
            return

        if not tg_handler.is_user_allowed(user_id, settings):
            await original(client, token, update)
            return

        if text:
            if await tg_commands.dispatch_telegram_commands(
                tg_commands.TelegramCommandEvent(
                    client=client,
                    token=token,
                    chat_id=chat_id,
                    user_id=user_id,
                    text=text,
                    update=update,
                )
            ):
                return

        await original(client, token, update)

    tg_handler.handle_update = wrapped
    _TG_HOOK_INSTALLED = True
