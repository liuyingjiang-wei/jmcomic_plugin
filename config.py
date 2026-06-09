from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ly_next.core.config import config, get_project_root

_PLUGIN_DIR = Path(__file__).resolve().parent
_DEFAULT_FILE = _PLUGIN_DIR / "default_config.yaml"


def _builtin_default() -> dict[str, Any]:
    return {
        "download_dir": "data/jmcomic/download",
        "pdf_dir": "data/jmcomic/pdf",
        "delete_original": True,
        "reuse_existing_pdf": True,
        "client": {"impl": "api", "proxy": "", "use_system_proxy": False},
        "public_base_url": "",
        "qq": {
            "chepai_enabled": True,
            "recall_delay_sec": 120,
            "download_timeout_sec": 600,
        },
    }


def _merge(default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _runtime_config_file() -> Path:
    return get_project_root() / "data" / "jmcomic" / "config.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _ensure_runtime_file() -> Path:
    runtime = _runtime_config_file()
    runtime.parent.mkdir(parents=True, exist_ok=True)
    if runtime.exists():
        return runtime
    if _DEFAULT_FILE.is_file():
        shutil.copy2(_DEFAULT_FILE, runtime)
        return runtime
    with open(runtime, "w", encoding="utf-8") as handle:
        yaml.dump(
            _builtin_default(),
            handle,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    return runtime


def _load_merged_config() -> dict[str, Any]:
    _ensure_runtime_file()
    merged = _merge(_builtin_default(), _load_yaml_file(_runtime_config_file()))
    override = config.get("plugins.jmcomic", {}) or {}
    if isinstance(override, dict) and override:
        merged = _merge(merged, override)
    return merged


@dataclass(frozen=True)
class JmcomicQqSettings:
    chepai_enabled: bool
    recall_delay_sec: int
    download_timeout_sec: int


@dataclass(frozen=True)
class JmcomicSettings:
    download_dir: str
    pdf_dir: str
    delete_original: bool
    reuse_existing_pdf: bool
    client_impl: str
    client_proxy: str
    use_system_proxy: bool
    public_base_url: str
    qq: JmcomicQqSettings


def _normalize_client_impl(raw: str) -> str:
    text = str(raw or "api").strip().lower()
    if text in ("mobile", "app"):
        return "api"
    if text in ("web", "html"):
        return "html"
    return text or "api"


def get_jmcomic_settings() -> JmcomicSettings:
    raw = _load_merged_config()
    client = raw.get("client", {}) or {}
    if not isinstance(client, dict):
        client = {}
    qq_raw = raw.get("qq", {}) or {}
    if not isinstance(qq_raw, dict):
        qq_raw = {}
    recall = int(qq_raw.get("recall_delay_sec", 120) or 120)
    timeout = int(qq_raw.get("download_timeout_sec", 600) or 600)
    return JmcomicSettings(
        download_dir=str(raw.get("download_dir") or "data/jmcomic/download"),
        pdf_dir=str(raw.get("pdf_dir") or "data/jmcomic/pdf"),
        delete_original=bool(raw.get("delete_original", True)),
        reuse_existing_pdf=bool(raw.get("reuse_existing_pdf", True)),
        client_impl=_normalize_client_impl(str(client.get("impl") or "api")),
        client_proxy=str(client.get("proxy") or "").strip(),
        use_system_proxy=bool(client.get("use_system_proxy", False)),
        public_base_url=str(raw.get("public_base_url") or "").strip(),
        qq=JmcomicQqSettings(
            chepai_enabled=bool(qq_raw.get("chepai_enabled", True)),
            recall_delay_sec=max(30, min(recall, 3600)),
            download_timeout_sec=max(60, min(timeout, 3600)),
        ),
    )


def get_config_value(key: str, default: Any = None) -> Any:
    value: Any = _load_merged_config()
    for part in key.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value
