from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from ly_next.core.config import get_project_root
from ly_next.core.logger import get_logger

from jmcomic_plugin.config import get_jmcomic_settings

logger = get_logger(__name__)

_ALBUM_ID_RE = re.compile(r"^\d+$")


def _resolve_dir(raw: str, fallback: Path) -> Path:
    path = Path(raw) if raw else fallback
    if not path.is_absolute():
        path = get_project_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def storage_dirs() -> tuple[Path, Path]:
    settings = get_jmcomic_settings()
    base = get_project_root() / "data" / "jmcomic"
    download_dir = _resolve_dir(settings.download_dir, base / "download")
    pdf_dir = _resolve_dir(settings.pdf_dir, base / "pdf")
    return download_dir, pdf_dir


def pdf_belongs_to_album(path: Path, album_id: str) -> bool:
    name = path.name
    stem = path.stem
    jm_prefix = f"[JM{album_id}]"
    if name == f"{album_id}.pdf" or stem == album_id:
        return True
    if stem.startswith(jm_prefix) or name.startswith(jm_prefix):
        return True
    return False


def find_pdf(pdf_dir: Path, album_id: str) -> Path | None:
    candidates = [
        item
        for item in pdf_dir.glob("*.pdf")
        if item.is_file() and pdf_belongs_to_album(item, album_id)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def extract_title(pdf_path: Path, album_id: str) -> str:
    title = pdf_path.stem
    prefix = f"[JM{album_id}]"
    if title.startswith(prefix):
        title = title[len(prefix) :]
    return title or pdf_path.stem


def to_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(get_project_root().resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def pdf_result(
    pdf_path: Path,
    album_id: str,
    *,
    cached: bool,
    elapsed: float = 0,
) -> dict[str, Any]:
    return {
        "ok": True,
        "cached": cached,
        "album_id": album_id,
        "title": extract_title(pdf_path, album_id),
        "pdf_path": to_relative(pdf_path),
        "pdf_name": pdf_path.name,
        "size": pdf_path.stat().st_size,
        "elapsed": elapsed,
    }


def ensure_pdf_export_deps() -> None:
    """jmcomic Feature.export_pdf uses Img2pdfPlugin; without img2pdf it silently skips."""
    try:
        import img2pdf  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "PDF 导出依赖 img2pdf 未安装。请在 LY-NEXT 项目根目录执行: "
            "uv pip install -r plugins/local/jmcomic_plugin/requirements.txt"
        ) from exc


def build_option(download_dir: Path):
    import jmcomic

    settings = get_jmcomic_settings()
    option = jmcomic.JmOption.default()
    option.dir_rule.base_dir = str(download_dir)
    option.client.impl = settings.client_impl
    postman = option.client.postman
    if postman is not None:
        meta = postman.get("meta_data") if hasattr(postman, "get") else None
        if meta is not None and hasattr(meta, "__setitem__"):
            if settings.client_proxy:
                proxy = settings.client_proxy
                if "://" not in proxy:
                    proxy = f"http://{proxy}"
                meta["proxies"] = {"http": proxy, "https": proxy}
            elif not settings.use_system_proxy:
                meta["proxies"] = None
    return option


def new_client():
    option = build_option(storage_dirs()[0])
    return option.new_jm_client()


def search_albums(query: str, page: int = 1) -> dict[str, Any]:
    text = str(query or "").strip()
    if not text:
        raise ValueError("search query is required")

    page_num = max(1, int(page or 1))
    client = new_client()
    search_page = client.search_site(search_query=text, page=page_num)

    items: list[dict[str, Any]] = []
    for album_id, title in search_page:
        items.append({"album_id": str(album_id), "title": str(title)})

    if not items and _ALBUM_ID_RE.fullmatch(text):
        detail = client.get_album_detail(text)
        items.append({"album_id": str(detail.album_id), "title": str(detail.name)})

    return {
        "ok": True,
        "query": text,
        "page": page_num,
        "total": getattr(search_page, "total", len(items)),
        "page_size": getattr(search_page, "page_size", len(items)),
        "page_count": getattr(search_page, "page_count", 1),
        "items": items,
    }


def download_album_sync(album_id: str) -> dict[str, Any]:
    album_text = str(album_id or "").strip()
    if not _ALBUM_ID_RE.fullmatch(album_text):
        raise ValueError("album_id must be numeric")

    settings = get_jmcomic_settings()
    download_dir, pdf_dir = storage_dirs()

    if settings.reuse_existing_pdf:
        existing = find_pdf(pdf_dir, album_text)
        if existing:
            logger.info("jmcomic album %s hit cached pdf: %s", album_text, existing.name)
            return pdf_result(existing, album_text, cached=True)

    ensure_pdf_export_deps()

    from jmcomic import Feature, download_album

    option = build_option(download_dir)
    started = time.time()
    logger.info("jmcomic album %s download started", album_text)

    download_album(
        album_text,
        option,
        extra=Feature.export_pdf(
            pdf_dir=str(pdf_dir),
            filename_rule="Aid",
            delete_original_file=settings.delete_original,
        ),
    )

    pdf_path = find_pdf(pdf_dir, album_text)
    if not pdf_path:
        raise RuntimeError(
            f"PDF 导出失败：在 {pdf_dir} 未找到相册 {album_text} 的 PDF。"
            " 若日志出现 img2pdf 依赖警告，请执行: "
            "uv pip install -r plugins/local/jmcomic_plugin/requirements.txt"
        )

    elapsed = round(time.time() - started, 2)
    logger.info("jmcomic album %s download done pdf=%s elapsed=%.2fs", album_text, pdf_path.name, elapsed)
    return pdf_result(pdf_path, album_text, cached=False, elapsed=elapsed)


def safe_pdf_path(raw: str) -> Path:
    if not raw or ".." in raw.replace("\\", "/"):
        raise ValueError("invalid file path")

    _, pdf_dir = storage_dirs()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = get_project_root() / raw

    resolved = candidate.resolve()
    pdf_root = pdf_dir.resolve()
    if pdf_root not in resolved.parents and resolved != pdf_root:
        raise PermissionError("path is outside pdf_dir")

    if not resolved.is_file():
        raise FileNotFoundError("file not found")

    return resolved
