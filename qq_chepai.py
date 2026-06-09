from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from ly_next.core.config import config, get_project_root
from ly_next.core.logger import get_logger
from ly_next.messaging.onebot_commands import OneBotCommandEvent, register_onebot_command_handler

from jmcomic_plugin.config import get_jmcomic_settings
from jmcomic_plugin.service import (
    download_album_sync,
    find_pdf,
    pdf_belongs_to_album,
    storage_dirs,
)

logger = get_logger(__name__)

_CHEPAI_RE = re.compile(r"^#车牌\s*(\d+)\s*$", re.IGNORECASE)
_LOOPBACK_RE = re.compile(r"://(127(?:\.\d+){3}|localhost)(?:[:/]|$)", re.IGNORECASE)


def register_chepai_command() -> None:
    register_onebot_command_handler(handle_chepai_command, priority=50)


def _parse_album_id(text: str) -> str | None:
    match = _CHEPAI_RE.match(text.strip())
    if not match:
        return None
    return match.group(1)


def _normalize_base_url(raw: str) -> str:
    text = str(raw or "").strip().rstrip("/")
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return f"http://{text.lstrip('/')}"


def resolve_public_base_url() -> str:
    settings = get_jmcomic_settings()
    if settings.public_base_url:
        normalized = _normalize_base_url(settings.public_base_url)
        if normalized and not _LOOPBACK_RE.search(normalized):
            return normalized

    configured = str(config.get("server.public_url") or config.get("server.url") or "").strip()
    if configured:
        normalized = _normalize_base_url(configured)
        if normalized and not _LOOPBACK_RE.search(normalized):
            return normalized

    host = str(config.get("server.host", "127.0.0.1") or "127.0.0.1").strip()
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    port = int(config.get("server.port", 8000) or 8000)
    candidate = _normalize_base_url(f"{host}:{port}")
    if candidate and not _LOOPBACK_RE.search(candidate):
        return candidate
    return ""


def _media_publish_path(pdf_path: Path, album_id: str, file_name: str) -> str:
    safe_base = Path(file_name).name.replace(" ", "_")
    safe_name = f"{album_id}_{safe_base}" if safe_base else f"{album_id}.pdf"
    media_dir = get_project_root() / "data" / "media" / "jmcomic"
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / safe_name
    shutil.copy2(pdf_path, dest)
    return safe_name


async def _send_text(event: OneBotCommandEvent, text: str) -> None:
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


async def _schedule_recall(event: OneBotCommandEvent, message_id: int | None, delay_sec: int) -> None:
    if message_id is None or delay_sec <= 0:
        return

    async def _recall() -> None:
        await asyncio.sleep(delay_sec)
        try:
            await event.session.delete_message(message_id)
        except Exception as exc:
            logger.debug("[jmcomic/chepai] recall failed msg_id=%s: %s", message_id, exc)

    asyncio.create_task(_recall())


async def _deliver_pdf(
    event: OneBotCommandEvent,
    pdf_path: Path,
    file_name: str,
    album_id: str,
    timeout: float,
    recall_sec: int,
) -> None:
    size_mb = pdf_path.stat().st_size / 1024 / 1024
    logger.info(
        "[jmcomic/chepai] pdf ready album=%s file=%s size=%.2fMB",
        album_id,
        file_name,
        size_mb,
    )

    message_id: int | None = None
    try:
        if event.message_type == "group" and event.group_id is not None:
            message_id = await event.session.send_file_message(
                message_type="group",
                group_id=event.group_id,
                file_path=str(pdf_path),
                file_name=file_name,
                timeout=timeout,
            )
        else:
            message_id = await event.session.send_file_message(
                message_type="private",
                user_id=event.user_id,
                file_path=str(pdf_path),
                file_name=file_name,
                timeout=timeout,
            )
    except Exception as exc:
        logger.warning("[jmcomic/chepai] file segment failed album=%s: %s", album_id, exc)
        message_id = None

    if message_id is not None:
        await _schedule_recall(event, message_id, recall_sec)
        return

    if event.message_type == "group" and event.group_id is not None:
        try:
            await event.session.upload_group_file(
                group_id=event.group_id,
                file_path=str(pdf_path),
                file_name=file_name,
                timeout=timeout,
            )
            await _send_text(event, f"PDF 已上传到群文件（{size_mb:.2f}MB）：{file_name}")
            return
        except Exception as exc:
            logger.warning("[jmcomic/chepai] upload_group_file failed album=%s: %s", album_id, exc)

    base = resolve_public_base_url()
    if base:
        media_name = _media_publish_path(pdf_path, album_id, file_name)
        url = f"{base}/media/jmcomic/{quote(media_name)}"
        try:
            message_id = await event.session.send_text_message(
                message_type=event.message_type,
                user_id=event.user_id if event.message_type != "group" else None,
                group_id=event.group_id if event.message_type == "group" else None,
                text=url,
            )
            await _schedule_recall(event, message_id, recall_sec)
            return
        except Exception as exc:
            logger.warning("[jmcomic/chepai] url reply failed album=%s: %s", album_id, exc)

    await _send_text(
        event,
        f"PDF 已生成（{size_mb:.2f}MB）但发送失败。请配置 public_base_url 或 server.public_url 后重试。",
    )


async def handle_chepai_command(event: OneBotCommandEvent) -> bool:
    settings = get_jmcomic_settings()
    if not settings.qq.chepai_enabled:
        return False

    album_id = _parse_album_id(event.text)
    if not album_id:
        return False

    timeout = float(settings.qq.download_timeout_sec)
    recall_sec = settings.qq.recall_delay_sec

    await _send_text(event, "正在处理，请稍候…")

    try:
        result = await asyncio.to_thread(download_album_sync, album_id)
    except Exception as exc:
        logger.exception("[jmcomic/chepai] download failed album=%s", album_id)
        await _send_text(event, f"处理失败：{exc}")
        return True

    if not result.get("ok"):
        await _send_text(event, str(result.get("error") or "处理失败"))
        return True

    pdf_rel = str(result.get("pdf_path") or "")
    pdf_path = get_project_root() / pdf_rel if pdf_rel else None
    if pdf_path is None or not pdf_path.is_file():
        _, pdf_dir = storage_dirs()
        pdf_path = find_pdf(pdf_dir, album_id)
    if pdf_path is None or not pdf_path.is_file():
        await _send_text(event, "PDF 文件不存在，请稍后重试")
        return True

    file_name = str(result.get("pdf_name") or pdf_path.name)
    if not pdf_belongs_to_album(pdf_path, album_id):
        await _send_text(
            event,
            f"PDF 与本子 ID 不匹配（请求 {album_id}，得到 {file_name}）",
        )
        return True

    if result.get("cached"):
        logger.info("[jmcomic/chepai] cache hit album=%s", album_id)

    await _deliver_pdf(
        event,
        pdf_path,
        file_name,
        album_id,
        timeout=timeout,
        recall_sec=recall_sec,
    )
    return True
