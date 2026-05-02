import json
import logging
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("linux-upload")

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CONFIG_FILE = BASE_DIR / "config.json"

UPLOAD_DIR = BASE_DIR / "uploads"
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB per file
BROWSE_ROOT = Path.home()  # 目录浏览限制在用户 home 目录内

if CONFIG_FILE.exists():
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        UPLOAD_DIR = Path(cfg.get("upload_dir", str(UPLOAD_DIR)))
    except Exception:
        logger.warning("config.json 解析失败，使用默认上传目录", exc_info=True)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    port = int(os.environ.get("UVICORN_PORT", "8787"))
    logger.info("服务启动")
    logger.info("  Local:   http://127.0.0.1:%s", port)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        logger.info("  Network: http://%s:%s", lan_ip, port)
    except Exception:
        logger.warning("局域网 IP 检测失败")
    yield


app = FastAPI(title="Linux File Upload Tool", lifespan=lifespan)


class ConfigPayload(BaseModel):
    upload_dir: str


@app.get("/api/browse")
async def browse_dir(path: str = ""):
    p = Path(path or str(BROWSE_ROOT)).expanduser().resolve()
    if not p.is_relative_to(BROWSE_ROOT):
        return JSONResponse({"error": "浏览范围限于用户目录"}, status_code=403)
    try:
        if not p.exists() or not p.is_dir():
            return JSONResponse({"error": "目录不存在"}, status_code=400)
        entries = []
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith("."):
                continue
            try:
                st = entry.stat()
                entries.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "size": st.st_size if entry.is_file() else 0,
                    "modified": st.st_mtime,
                })
            except OSError:
                pass
        parent = str(p.parent) if p.parent.is_relative_to(BROWSE_ROOT) else None
        return {"path": str(p), "parent": parent, "entries": entries}
    except PermissionError:
        return JSONResponse({"error": "无权限访问"}, status_code=403)


@app.get("/api/config")
async def get_config():
    return {"upload_dir": str(UPLOAD_DIR.resolve())}


@app.post("/api/config")
async def set_config(payload: ConfigPayload):
    global UPLOAD_DIR
    new_dir = Path(payload.upload_dir).expanduser().resolve()
    try:
        new_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return JSONResponse({"error": f"无法创建目录: {e}"}, status_code=400)
    UPLOAD_DIR = new_dir
    CONFIG_FILE.write_text(json.dumps({"upload_dir": str(new_dir)}, indent=2))
    return {"ok": True, "upload_dir": str(new_dir)}


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    paths: str = Form(default="[]"),
):
    uploaded = []
    failed = []
    try:
        paths_list = json.loads(paths)
    except (json.JSONDecodeError, TypeError):
        paths_list = []

    for i, file in enumerate(files):
        rel_path = paths_list[i] if i < len(paths_list) else file.filename
        if not rel_path:
            rel_path = file.filename
        try:
            file_path = (UPLOAD_DIR / rel_path).resolve()
            if not file_path.is_relative_to(UPLOAD_DIR.resolve()):
                failed.append({"name": rel_path, "error": "非法路径"})
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            with open(file_path, "wb") as f:
                while chunk := file.file.read(64 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_SIZE:
                        f.close()
                        os.remove(file_path)
                        failed.append({"name": rel_path, "error": f"超过文件大小限制 ({MAX_UPLOAD_SIZE // (1024*1024)}MB)"})
                        break
                    f.write(chunk)
                else:
                    uploaded.append({"name": rel_path, "size": total})
        except Exception as e:
            try:
                os.remove(file_path)
            except Exception:
                pass
            failed.append({"name": rel_path, "error": str(e)})

    return {"uploaded": uploaded, "failed": failed}


@app.get("/api/files")
async def list_files():
    files = []
    entries = []
    for p in UPLOAD_DIR.rglob("*"):
        try:
            if p.is_file():
                st = p.stat()
                entries.append((p, st))
        except OSError:
            continue
    entries.sort(key=lambda x: x[1].st_mtime, reverse=True)
    for p, st in entries:
        rel = str(p.relative_to(UPLOAD_DIR))
        files.append({
            "name": rel,
            "size": st.st_size,
            "modified": st.st_mtime,
        })
    return {"files": files}


def _safe_path(base: Path, rel: str) -> Optional[Path]:
    """Resolve a relative path within base. Returns None on escape attempt."""
    resolved = (base / rel).resolve()
    if resolved.is_relative_to(base):
        return resolved
    return None


@app.get("/api/download/{filename:path}")
async def download_file(filename: str):
    file_path = _safe_path(UPLOAD_DIR, filename)
    if file_path is None:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(file_path, filename=filename)
