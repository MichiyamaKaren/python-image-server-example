import asyncio
import json
import os
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from PIL import Image

from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

current_directory = os.path.dirname(os.path.realpath(__file__))
parent_directory = os.path.dirname(current_directory)
BASE_DIRECTORY = os.path.join(parent_directory, "static")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
TEMPLATE_FILE = os.path.join(parent_directory, "templates", "file_list.html")


def is_safe_path(base_directory: str, subdirectory: str) -> bool:
    full_path = os.path.abspath(os.path.join(base_directory, subdirectory))
    return os.path.commonpath([full_path, base_directory]) == base_directory


def is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def serialize_metadata(info: dict) -> dict:
    result = {}
    for k, v in info.items():
        try:
            json.dumps(v)
            result[str(k)] = v
        except (TypeError, ValueError):
            if not isinstance(v, bytes):
                result[str(k)] = str(v)
    return result


def list_directory(path: str) -> dict:
    full_path = os.path.join(BASE_DIRECTORY, path)
    files, dirs = [], []
    for item in os.listdir(full_path):
        item_path = os.path.join(full_path, item)
        rel = os.path.relpath(item_path, BASE_DIRECTORY).replace("\\", "/")
        if os.path.isfile(item_path) and is_image_file(item_path):
            with Image.open(item_path) as img:
                metadata = serialize_metadata(img.info)
            files.append({"filename": rel, "metadata": metadata})
        elif os.path.isdir(item_path):
            dirs.append(rel)
    return {"files": files, "dirs": dirs, "path": path}


# ── file serving ──────────────────────────────────────────────────────────────

@app.get("/files/{path:path}")
async def read_files_or_download(path: str):
    if not is_safe_path(BASE_DIRECTORY, path):
        raise HTTPException(status_code=400, detail="Invalid path")
    full_path = os.path.join(BASE_DIRECTORY, path)
    if os.path.isfile(full_path) and is_image_file(full_path):
        return FileResponse(full_path)
    if os.path.isdir(full_path):
        return FileResponse(TEMPLATE_FILE, media_type="text/html")
    raise HTTPException(status_code=404, detail="Path not found")


@app.delete("/files/{path:path}")
async def delete_file(path: str):
    if not is_safe_path(BASE_DIRECTORY, path):
        raise HTTPException(status_code=403, detail="Access denied")
    full_path = os.path.join(BASE_DIRECTORY, path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    if not is_image_file(full_path):
        raise HTTPException(status_code=400, detail="Not an image file")
    os.remove(full_path)
    return {"status": "deleted"}


# ── REST API ───────────────────────────────────────────────────────────────────

async def _api_list(path: str):
    if not is_safe_path(BASE_DIRECTORY, path):
        raise HTTPException(status_code=403, detail="Access denied")
    full_path = os.path.join(BASE_DIRECTORY, path)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    return list_directory(path)


@app.get("/api/files")
@app.get("/api/files/")
async def api_list_root():
    return await _api_list("")


@app.get("/api/files/{path:path}")
async def api_list_files(path: str):
    return await _api_list(path)


# ── SSE ────────────────────────────────────────────────────────────────────────

def _get_image_set(directory: str) -> set:
    try:
        return {
            item for item in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, item)) and is_image_file(item)
        }
    except OSError:
        return set()


async def _sse_generator(path: str, directory: str):
    current = _get_image_set(directory)
    try:
        while True:
            await asyncio.sleep(2)
            new = _get_image_set(directory)
            added = new - current
            removed = current - new
            if added:
                files_data = []
                for name in sorted(added):
                    item_path = os.path.join(directory, name)
                    rel = os.path.relpath(item_path, BASE_DIRECTORY).replace("\\", "/")
                    try:
                        with Image.open(item_path) as img:
                            metadata = serialize_metadata(img.info)
                    except Exception:
                        metadata = {}
                    files_data.append({"filename": rel, "metadata": metadata})
                yield f"data: {json.dumps({'type': 'added', 'files': files_data})}\n\n"
            if removed:
                removed_paths = [
                    os.path.relpath(os.path.join(directory, n), BASE_DIRECTORY).replace("\\", "/")
                    for n in removed
                ]
                yield f"data: {json.dumps({'type': 'removed', 'filenames': removed_paths})}\n\n"
            current = new
    except asyncio.CancelledError:
        return


def _sse_response(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _api_sse(path: str):
    if not is_safe_path(BASE_DIRECTORY, path):
        raise HTTPException(status_code=403, detail="Access denied")
    directory = os.path.join(BASE_DIRECTORY, path)
    if not os.path.isdir(directory):
        raise HTTPException(status_code=404, detail="Directory not found")
    return _sse_response(_sse_generator(path, directory))


@app.get("/api/sse")
@app.get("/api/sse/")
async def api_sse_root():
    return await _api_sse("")


@app.get("/api/sse/{path:path}")
async def api_sse(path: str):
    return await _api_sse(path)


# ── root redirect ──────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return RedirectResponse(url="/files")
