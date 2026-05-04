from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
import urllib.parse
import uvicorn

from fetcher import ShowFetcher, load_config, save_config

app = FastAPI(title="ConcertArr", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scan_state = {
    "running": False,
    "total": 0,
    "current": 0,
    "current_name": "",
    "results": [],
    "not_found": [],
    "stats": {"tmdb": 0, "discogs": 0, "skip": 0, "not_found": 0},
    "done": False,
}

class ConfigModel(BaseModel):
    shows_dir: str
    tmdb_key: str
    discogs_token: str

class ManualFetchModel(BaseModel):
    filename: str
    discogs_url: str

class ScanRequest(BaseModel):
    shows_dir: str
    tmdb_key: str
    discogs_token: str

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def set_config(config: ConfigModel):
    save_config(config.dict())
    return {"ok": True}

@app.get("/api/browse")
def browse(path: str = "/"):
    if not os.path.isdir(path):
        raise HTTPException(400, "Caminho invalido")
    items = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            items.append({
                "name": name,
                "path": full,
                "is_dir": os.path.isdir(full),
            })
    except PermissionError:
        raise HTTPException(403, "Sem permissao para acessar esta pasta")
    parent = str(Path(path).parent) if path != "/" else None
    return {"current": path, "parent": parent, "items": items}

@app.get("/api/shows")
def list_shows(shows_dir: str = None):
    cfg = load_config()
    folder = shows_dir or cfg.get("shows_dir", "")
    if not folder or not os.path.isdir(folder):
        raise HTTPException(400, "Pasta nao encontrada")
    exts = {".mkv", ".mp4", ".avi", ".m4v", ".mov"}
    shows = []
    for f in sorted(os.listdir(folder)):
        ext = os.path.splitext(f)[1].lower()
        if ext not in exts:
            continue
        base = os.path.splitext(f)[0]
        has_poster    = os.path.exists(os.path.join(folder, f"{base}-poster.png"))
        has_backdrop  = os.path.exists(os.path.join(folder, f"{base}-backdrop1.png"))
        has_landscape = os.path.exists(os.path.join(folder, f"{base}-landscape.png"))
        # Encoda o nome do arquivo corretamente para URL
        encoded_folder = urllib.parse.quote(folder, safe='/')
        encoded_file   = urllib.parse.quote(f"{base}-poster.png", safe='')
        shows.append({
            "filename": f,
            "name": base,
            "has_poster": has_poster,
            "has_backdrop": has_backdrop,
            "has_landscape": has_landscape,
            "complete": has_poster and has_backdrop and has_landscape,
            "poster_path": f"/api/image?folder={encoded_folder}&file={encoded_file}" if has_poster else None,
        })
    return shows

@app.get("/api/image")
def get_image(folder: str, file: str):
    path = os.path.join(folder, file)
    if not os.path.exists(path):
        raise HTTPException(404, "Imagem nao encontrada")
    return FileResponse(path)

def run_scan(shows_dir: str, tmdb_key: str, discogs_token: str):
    global scan_state
    scan_state.update({
        "running": True, "done": False, "results": [], "not_found": [],
        "stats": {"tmdb": 0, "discogs": 0, "skip": 0, "not_found": 0},
    })
    fetcher = ShowFetcher(tmdb_key, discogs_token)
    exts = {".mkv", ".mp4", ".avi", ".m4v", ".mov"}
    files = sorted([f for f in os.listdir(shows_dir)
                    if os.path.splitext(f)[1].lower() in exts])
    scan_state["total"] = len(files)
    scan_state["current"] = 0
    for i, f in enumerate(files):
        scan_state["current"] = i + 1
        scan_state["current_name"] = f
        path = os.path.join(shows_dir, f)
        result = fetcher.process_show(path)
        scan_state["stats"][result] += 1
        base = os.path.splitext(f)[0]
        encoded_folder = urllib.parse.quote(shows_dir, safe='/')
        encoded_file   = urllib.parse.quote(f"{base}-poster.png", safe='')
        scan_state["results"].append({
            "filename": f,
            "status": result,
            "poster_path": f"/api/image?folder={encoded_folder}&file={encoded_file}" if result != "not_found" else None,
        })
        if result == "not_found":
            scan_state["not_found"].append(f)
    scan_state["running"] = False
    scan_state["done"] = True
# Notifica o Jellyfin pra atualizar a biblioteca de Shows
    try:
        import requests
        jellyfin_url = "http://localhost:8096"
        jellyfin_key = "9f6696477c0c41e8b23d676c400f971b432911a9ec5e44d9a8a139faffd2fd8b"
        requests.post(
            f"{jellyfin_url}/Library/Refresh",
            headers={"X-Emby-Token": jellyfin_key},
            timeout=10
        )
    except Exception:
        pass

@app.post("/api/scan")
def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    global scan_state
    if scan_state["running"]:
        raise HTTPException(409, "Scan ja em andamento")
    if not os.path.isdir(req.shows_dir):
        raise HTTPException(400, "Pasta nao encontrada")
    save_config({"shows_dir": req.shows_dir, "tmdb_key": req.tmdb_key, "discogs_token": req.discogs_token})
    background_tasks.add_task(run_scan, req.shows_dir, req.tmdb_key, req.discogs_token)
    return {"ok": True}

@app.get("/api/scan/status")
def scan_status():
    return scan_state

@app.post("/api/scan/stop")
def stop_scan():
    scan_state["running"] = False
    return {"ok": True}

@app.post("/api/manual")
def manual_fetch(req: ManualFetchModel):
    cfg = load_config()
    shows_dir = cfg.get("shows_dir", "")
    tmdb_key = cfg.get("tmdb_key", "")
    discogs_token = cfg.get("discogs_token", "")
    if not shows_dir:
        raise HTTPException(400, "Configure a pasta primeiro")
    path = os.path.join(shows_dir, req.filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Arquivo nao encontrado")
    fetcher = ShowFetcher(tmdb_key, discogs_token)
    ok = fetcher.fetch_from_discogs_url(req.discogs_url,
                                         os.path.splitext(req.filename)[0],
                                         shows_dir, force=True)
    if not ok:
        raise HTTPException(500, "Nao foi possivel baixar as imagens")
    base = os.path.splitext(req.filename)[0]
    encoded_folder = urllib.parse.quote(shows_dir, safe='/')
    encoded_file   = urllib.parse.quote(f"{base}-poster.png", safe='')
    return {"ok": True, "poster_path": f"/api/image?folder={encoded_folder}&file={encoded_file}"}

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8090, reload=False)
