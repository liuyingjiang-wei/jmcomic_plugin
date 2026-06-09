from __future__ import annotations

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from ly_next.api.base import APIRegistry
from ly_next.api.plugin_router import PluginRouterAPI
from ly_next.core.app_context import AppContext
from ly_next.core.config import get_project_root
from ly_next.core.plugin.protocol import LyNextPlugin

from jmcomic_plugin.api import router as jmcomic_router
from jmcomic_plugin.jm_help import install_telegram_help_hook, register_jm_help_commands
from jmcomic_plugin.qq_chepai import register_chepai_command
from jmcomic_plugin.tools import jmcomic_download_tool, jmcomic_search_tool


class JmcomicPlugin(LyNextPlugin):
    name = "jmcomic"
    version = "1.1.0"
    description = "JMComic search, download, PDF export, QQ #车牌 and jm帮助"

    def register_tools(self, registry, ctx: AppContext) -> None:
        registry.register(jmcomic_search_tool)
        registry.register(jmcomic_download_tool)
        register_chepai_command()
        register_jm_help_commands()

    def register_apis(self, api_registry: APIRegistry, ctx: AppContext) -> None:
        api_registry.register(
            PluginRouterAPI(
                name="jmcomic",
                description="JMComic search and PDF download API",
                router=jmcomic_router,
                enabled=lambda: True,
            )
        )

    async def on_startup(self, app: FastAPI, ctx: AppContext) -> None:
        install_telegram_help_hook()
        media_root = get_project_root() / "data" / "media"
        media_root.mkdir(parents=True, exist_ok=True)
        jm_media = media_root / "jmcomic"
        jm_media.mkdir(parents=True, exist_ok=True)
        mounted = any(getattr(route, "path", None) == "/media" for route in app.routes)
        if not mounted:
            app.mount("/media", StaticFiles(directory=str(media_root)), name="jmcomic_media")


plugin = JmcomicPlugin()
