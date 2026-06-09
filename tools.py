from __future__ import annotations

import asyncio

from ly_next.tools.base import tool

from jmcomic_plugin.service import download_album_sync, search_albums


@tool(
    name="jmcomic_search",
    description="Search JMComic albums by keyword or numeric album id",
    category="media",
)
async def jmcomic_search_tool(query: str, page: int = 1) -> dict:
    return await asyncio.to_thread(search_albums, query, page)


@tool(
    name="jmcomic_download",
    description="Download a JMComic album by numeric id and export PDF",
    category="media",
)
async def jmcomic_download_tool(album_id: str) -> dict:
    return await asyncio.to_thread(download_album_sync, album_id)
