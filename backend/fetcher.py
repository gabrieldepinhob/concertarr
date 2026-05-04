"""
ConcertArr - Fetcher
Lógica de busca de capas via TMDb e Discogs
"""

import os
import re
import time
import json
import requests
from pathlib import Path

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")

TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p/original"
DISCOGS_BASE = "https://api.discogs.com"


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    existing = load_config()
    existing.update(data)
    with open(CONFIG_PATH, "w") as f:
        json.dump(existing, f, indent=2)


class ShowFetcher:
    def __init__(self, tmdb_key: str, discogs_token: str):
        self.tmdb_key = tmdb_key
        self.discogs_headers = {
            "Authorization": f"Discogs token={discogs_token}",
            "User-Agent": "ConcertArr/1.0"
        }

    # ─── Helpers ─────────────────────────────────────────────

    def clean_title(self, filename: str):
        name = Path(filename).stem
        year_match = re.search(r'\((\d{4})\)', name)
        year = year_match.group(1) if year_match else None
        title = re.sub(r'\s*\(\d{4}\)', '', name).strip()
        title = re.sub(r'\s*[-–]\s*[Dd]isk?\s*\d+$', '', title).strip()
        return title, year

    def download_image(self, url: str, dest_path: str, headers=None, force=False) -> bool:
        if os.path.exists(dest_path) and not force:
            return True
        try:
            r = requests.get(url, timeout=30, stream=True, headers=headers)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                return True
            return False
        except Exception:
            return False

    def delete_images(self, base_name: str, show_dir: str):
        for suffix in ["-poster.png", "-backdrop1.png", "-landscape.png", "-logo.png"]:
            p = os.path.join(show_dir, base_name + suffix)
            if os.path.exists(p):
                os.remove(p)

    # ─── TMDb ────────────────────────────────────────────────

    def search_tmdb(self, title: str, year: str = None):
        params = {"api_key": self.tmdb_key, "query": title, "language": "pt-BR"}
        if year:
            params["year"] = year
        for endpoint in ["/search/movie", "/search/tv"]:
            try:
                r = requests.get(f"{TMDB_BASE}{endpoint}", params=params, timeout=10)
                results = r.json().get("results", [])
                if results:
                    mtype = "movie" if "movie" in endpoint else "tv"
                    return results[0], mtype
                if year and "year" in params:
                    params.pop("year")
                    r = requests.get(f"{TMDB_BASE}{endpoint}", params=params, timeout=10)
                    results = r.json().get("results", [])
                    if results:
                        mtype = "movie" if "movie" in endpoint else "tv"
                        return results[0], mtype
            except Exception:
                continue
        return None, None

    def fetch_tmdb_images(self, tmdb_id: int, media_type: str,
                          base_name: str, show_dir: str, force=False) -> bool:
        try:
            r = requests.get(f"{TMDB_BASE}/{media_type}/{tmdb_id}/images",
                             params={"api_key": self.tmdb_key}, timeout=10)
            images = r.json()
        except Exception:
            return False

        got_poster = False

        posters = images.get("posters", [])
        if posters:
            pt = [p for p in posters if p.get("iso_639_1") == "pt"]
            poster = pt[0] if pt else posters[0]
            got_poster = self.download_image(
                TMDB_IMG + poster["file_path"],
                os.path.join(show_dir, f"{base_name}-poster.png"), force=force
            )

        backdrops = images.get("backdrops", [])
        if backdrops:
            self.download_image(TMDB_IMG + backdrops[0]["file_path"],
                                os.path.join(show_dir, f"{base_name}-backdrop1.png"), force=force)
            self.download_image(TMDB_IMG + backdrops[0]["file_path"],
                                os.path.join(show_dir, f"{base_name}-landscape.png"), force=force)

        logos = images.get("logos", [])
        if logos:
            pt_l = [l for l in logos if l.get("iso_639_1") == "pt"]
            en_l = [l for l in logos if l.get("iso_639_1") == "en"]
            logo = pt_l[0] if pt_l else (en_l[0] if en_l else logos[0])
            self.download_image(TMDB_IMG + logo["file_path"],
                                os.path.join(show_dir, f"{base_name}-logo.png"), force=force)

        return got_poster

    # ─── Discogs ─────────────────────────────────────────────

    def search_discogs(self, title: str, year: str = None):
        params = {"q": title, "type": "release", "per_page": 5}
        if year:
            params["year"] = year
        for fmt in ["DVD", "Blu-ray", None]:
            if fmt:
                params["format"] = fmt
            else:
                params.pop("format", None)
                params.pop("year", None)
            try:
                r = requests.get(f"{DISCOGS_BASE}/database/search",
                                 params=params, headers=self.discogs_headers, timeout=10)
                results = r.json().get("results", [])
                if results:
                    return results[0]
            except Exception:
                continue
        return None

    def fetch_discogs_images(self, result: dict, base_name: str,
                             show_dir: str, force=False):
        cover_url = result.get("cover_image") or result.get("thumb")
        if cover_url and "spacer" not in cover_url:
            self.download_image(cover_url, os.path.join(show_dir, f"{base_name}-poster.png"),
                                headers=self.discogs_headers, force=force)
            self.download_image(cover_url, os.path.join(show_dir, f"{base_name}-backdrop1.png"),
                                headers=self.discogs_headers, force=force)
            self.download_image(cover_url, os.path.join(show_dir, f"{base_name}-landscape.png"),
                                headers=self.discogs_headers, force=force)

        resource_url = result.get("resource_url")
        if resource_url:
            try:
                r = requests.get(resource_url, headers=self.discogs_headers, timeout=10)
                images = r.json().get("images", [])
                all_imgs = ([i for i in images if i.get("type") == "primary"] +
                            [i for i in images if i.get("type") == "secondary"])
                if all_imgs:
                    self.download_image(all_imgs[0]["uri"],
                                        os.path.join(show_dir, f"{base_name}-poster.png"),
                                        headers=self.discogs_headers, force=force)
                if len(all_imgs) > 1:
                    self.download_image(all_imgs[1]["uri"],
                                        os.path.join(show_dir, f"{base_name}-backdrop1.png"),
                                        headers=self.discogs_headers, force=force)
                    self.download_image(all_imgs[1]["uri"],
                                        os.path.join(show_dir, f"{base_name}-landscape.png"),
                                        headers=self.discogs_headers, force=force)
            except Exception:
                pass

    def fetch_from_discogs_url(self, url: str, base_name: str,
                               show_dir: str, force=True) -> bool:
        match_master  = re.search(r'/master/(\d+)', url)
        match_release = re.search(r'/release/(\d+)', url)
        if match_master:
            api_url = f"{DISCOGS_BASE}/masters/{match_master.group(1)}"
        elif match_release:
            api_url = f"{DISCOGS_BASE}/releases/{match_release.group(1)}"
        else:
            return False
        try:
            r = requests.get(api_url, headers=self.discogs_headers, timeout=10)
            data = r.json()
            images = data.get("images", [])
            if not images:
                versions_url = data.get("versions_url")
                if versions_url:
                    rv = requests.get(versions_url, headers=self.discogs_headers, timeout=10)
                    versions = rv.json().get("versions", [])
                    if versions:
                        r2 = requests.get(versions[0]["resource_url"],
                                          headers=self.discogs_headers, timeout=10)
                        images = r2.json().get("images", [])
            if not images:
                return False

            all_imgs = ([i for i in images if i.get("type") == "primary"] +
                        [i for i in images if i.get("type") == "secondary"])
            if not all_imgs:
                all_imgs = images

            self.delete_images(base_name, show_dir)
            self.download_image(all_imgs[0]["uri"],
                                os.path.join(show_dir, f"{base_name}-poster.png"),
                                headers=self.discogs_headers, force=force)
            src = all_imgs[1]["uri"] if len(all_imgs) > 1 else all_imgs[0]["uri"]
            self.download_image(src, os.path.join(show_dir, f"{base_name}-backdrop1.png"),
                                headers=self.discogs_headers, force=force)
            self.download_image(src, os.path.join(show_dir, f"{base_name}-landscape.png"),
                                headers=self.discogs_headers, force=force)
            return True
        except Exception:
            return False

    # ─── Process ─────────────────────────────────────────────

    def process_show(self, mkv_path: str) -> str:
        filename  = os.path.basename(mkv_path)
        title, year = self.clean_title(filename)
        base_name = Path(mkv_path).stem
        show_dir  = os.path.dirname(mkv_path)

        needed = ["-poster.png", "-backdrop1.png", "-landscape.png"]
        if all(os.path.exists(os.path.join(show_dir, base_name + s)) for s in needed):
            return "skip"

        result, media_type = self.search_tmdb(title, year)
        if result:
            if self.fetch_tmdb_images(result["id"], media_type, base_name, show_dir):
                time.sleep(0.3)
                return "tmdb"

        disc = self.search_discogs(title, year)
        if disc:
            self.fetch_discogs_images(disc, base_name, show_dir)
            if os.path.exists(os.path.join(show_dir, f"{base_name}-poster.png")):
                time.sleep(0.5)
                return "discogs"

        return "not_found"
