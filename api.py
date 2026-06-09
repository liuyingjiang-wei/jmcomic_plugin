from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from jmcomic_plugin.service import download_album_sync, safe_pdf_path, search_albums

router = APIRouter(prefix="/jmcomic", tags=["jmcomic"])


class JmcomicDownloadBody(BaseModel):
    album_id: str = Field(..., min_length=1)


@router.get("/search")
async def jmcomic_search_api(q: str = Query(..., min_length=1), page: int = Query(1, ge=1)):
    try:
        return await asyncio.to_thread(search_albums, q, page)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/download")
async def jmcomic_download_api(body: JmcomicDownloadBody):
    try:
        return await asyncio.to_thread(download_album_sync, body.album_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        return {"ok": False, "album_id": body.album_id, "error": str(exc)}


@router.get("/file")
async def jmcomic_file_api(path: str = Query(..., min_length=1)):
    try:
        pdf_path = await asyncio.to_thread(safe_pdf_path, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )
