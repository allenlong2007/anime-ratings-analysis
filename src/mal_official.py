"""MyAnimeList's official API (v2), used when a Client ID is available.

It's more reliable than Jikan because it doesn't depend on scraping, but it
needs a free Client ID from https://myanimelist.net/apiconfig. Put the ID (just
the ID, nothing else) in a file named `.mal_client_id` at the project root.
That file is in .gitignore so it never gets committed.
"""
import hashlib
import json
import time
from pathlib import Path

import certifi
import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENT_ID_FILE = ROOT / ".mal_client_id"
CACHE = ROOT / "data" / "cache"
BASE = "https://api.myanimelist.net/v2"
FIELDS = ",".join([
    "id", "title", "alternative_titles", "media_type", "source", "status", "start_date",
    "num_episodes", "mean", "num_scoring_users", "num_list_users", "rank", "popularity",
    "genres", "studios",
])


class MALError(RuntimeError):
    pass


def client_id() -> str | None:
    if CLIENT_ID_FILE.exists():
        return CLIENT_ID_FILE.read_text().strip() or None
    return None


_last_request = 0.0


def get(path: str, params: dict | None = None, use_cache: bool = True) -> dict:
    """GET an official-API endpoint, waiting ~1s between calls and caching to disk.

    The cache makes long collection jobs resumable: re-running only pays for
    requests that haven't succeeded before.
    """
    global _last_request
    key = client_id()
    if not key:
        raise MALError("no Client ID in .mal_client_id")

    cache_name = hashlib.sha1(json.dumps([path, params], sort_keys=True).encode()).hexdigest()
    cache_file = CACHE / f"{cache_name}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())

    for wait in [0, 5, 20, 60]:
        time.sleep(max(wait, 1.0 - (time.time() - _last_request)))
        _last_request = time.time()
        try:
            response = requests.get(f"{BASE}/{path.lstrip('/')}", params=params,
                                    headers={"X-MAL-CLIENT-ID": key}, timeout=30, verify=certifi.where())
        except requests.RequestException as error:
            problem = str(error)
            continue
        if response.status_code == 200:
            body = response.json()
            if use_cache:
                CACHE.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(body))
            return body
        problem = f"HTTP {response.status_code}: {response.text[:200]}"
        if response.status_code == 404:
            break
    raise MALError(f"{path} failed: {problem}")


def season_anime(year: int, season: str) -> list[dict]:
    """Every anime MyAnimeList lists for a season, converted to Jikan-like dicts."""
    key = client_id()
    if not key:
        raise MALError("no Client ID in .mal_client_id")

    url = f"{BASE}/anime/season/{year}/{season}"
    params = {"fields": FIELDS, "limit": 500, "nsfw": "true"}
    results = []
    while url:
        response = requests.get(url, params=params, headers={"X-MAL-CLIENT-ID": key},
                                timeout=30, verify=certifi.where())
        if response.status_code != 200:
            raise MALError(f"HTTP {response.status_code}: {response.text[:200]}")
        body = response.json()
        results.extend(_as_jikan(item["node"]) for item in body["data"])
        url, params = body.get("paging", {}).get("next"), None  # `next` already has the params
        time.sleep(1)
    return results


def _as_jikan(node: dict) -> dict:
    """Rename official-API fields to the Jikan names the collector already uses."""
    def named(items):
        return [{"name": item["name"]} for item in items or []]

    source = (node.get("source") or "").replace("_", " ").capitalize() or None
    return {
        "mal_id": node["id"],
        "title": node["title"],
        "title_english": (node.get("alternative_titles") or {}).get("en") or None,
        "type": (node.get("media_type") or "").upper() or None,
        "source": source,
        "status": node.get("status"),
        "aired": {"from": node.get("start_date")},
        "episodes": node.get("num_episodes") or None,
        "members": node.get("num_list_users"),
        "favorites": None,  # not available from the official API
        "score": node.get("mean"),
        "scored_by": node.get("num_scoring_users"),
        "rank": node.get("rank"),
        "popularity": node.get("popularity"),
        "genres": named(node.get("genres")),
        "themes": [],
        "demographics": [],
        "studios": named(node.get("studios")),
    }
