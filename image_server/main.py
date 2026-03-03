from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
import os
from typing import List, Dict
from fastapi.templating import Jinja2Templates
from PIL import Image


app = FastAPI()

# 現在のファイルのディレクトリを取得
current_directory = os.path.dirname(os.path.realpath(__file__))
parent_directory = os.path.dirname(current_directory)
BASE_DIRECTORY = os.path.join(parent_directory, "static")  # 基本ディレクトリを設定
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}  # 画像ファイルの拡張子
templates = Jinja2Templates(directory="templates")  # テンプレートディレクトリの設定


def is_safe_path(base_directory: str, subdirectory: str) -> bool:
    # 完全なパスを生成
    full_path = os.path.abspath(os.path.join(base_directory, subdirectory))  # パスが基本ディレクトリ内にあるかどうかを確認
    return os.path.commonpath([full_path, base_directory]) == base_directory


def list_files_and_dirs(subdirectory: str) -> Dict[str, List[str]]:
    if not is_safe_path(BASE_DIRECTORY, subdirectory):
        raise HTTPException(status_code=400, detail="Invalid subdirectory path")
    directory = os.path.join(BASE_DIRECTORY, subdirectory)
    file_list = []
    dir_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, BASE_DIRECTORY)
            file_list.append(relative_path)
        for dir in dirs:
            full_path = os.path.join(root, dir)
            relative_path = os.path.relpath(full_path, BASE_DIRECTORY)
            dir_list.append(relative_path)
        # 一度の反復でディレクトリをリストに追加したら、それ以上サブディレクトリを探索しない
        break
    return {"files": file_list, "dirs": dir_list}


def is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


@app.get("/files/{path:path}", response_class=HTMLResponse)
async def read_files_or_download(request: Request, path: str):
    if not is_safe_path(BASE_DIRECTORY, path):
        raise HTTPException(status_code=400, detail="Invalid path")

    full_path = os.path.join(BASE_DIRECTORY, path)

    # パスがファイルで、かつ画像の場合はダウンロード
    if os.path.isfile(full_path) and is_image_file(full_path):
        return FileResponse(full_path)

    # パスがディレクトリの場合は画像ファイルのみをリストアップ
    elif os.path.isdir(full_path):
        file_list = []
        dir_list = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isfile(item_path) and is_image_file(item_path):
                with Image.open(item_path) as img:
                    metadata = img.info
                file_list.append(
                    {
                        "filename": os.path.relpath(item_path, BASE_DIRECTORY),
                        "metadata": metadata,
                    }
                )
            elif os.path.isdir(item_path):
                dir_list.append(os.path.relpath(item_path, BASE_DIRECTORY))

        # HTMLテンプレートをレンダリングしてレスポンスを返す
        return templates.TemplateResponse(
            "file_list.html", {"request": request, "files": file_list, "dirs": dir_list, "path": path}
        )
    else:
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


@app.get("/metadata/{filepath:path}")
async def get_image_metadata(filepath: str):
    if not is_safe_path(BASE_DIRECTORY, filepath) or not is_image_file(filepath):
        raise HTTPException(status_code=400, detail="Invalid or non-image file path")

    full_path = os.path.join(BASE_DIRECTORY, filepath)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    with Image.open(full_path) as img:
        metadata = img.info
        return metadata


@app.get("/")
def read_root():
    return RedirectResponse(url="/files")
