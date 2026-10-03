"""A small, polite client for the Jikan API (an unofficial MyAnimeList API).

Jikan allows about 3 requests a second and 60 a minute. This client waits a
little over a second between requests and retries when Jikan or MyAnimeList
is temporarily down, which happens often enough to plan for.
"""
import time

import certifi
import requests

BASE = "https://api.jikan.moe/v4"
MIN_SECONDS_BETWEEN_REQUESTS = 1.1
RETRY_WAITS = [5, 15, 30, 60, 120]  # seconds to wait before each retry

_session = requests.Session()
_session.headers["User-Agent"] = "anime-ratings-analysis (student research project)"
_last_request = 0.0


class JikanError(RuntimeError):
    pass


def get(path: str, params: dict | None = None) -> dict:
    """GET a Jikan endpoint, e.g. get("seasons/2027/winter", {"page": 2})."""
    global _last_request
    url = f"{BASE}/{path.lstrip('/')}"
    last_problem = None

    for attempt in range(len(RETRY_WAITS) + 1):
        wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()

        try:
            response = _session.get(url, params=params, timeout=30, verify=certifi.where())
        except requests.RequestException as error:
            last_problem = f"network error: {error}"
        else:
            if response.status_code == 200:
                return response.json()
            # 429 = too many requests, 5xx = Jikan or MyAnimeList is having trouble.
            last_problem = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in (429, 500, 502, 503, 504):
                break

        if attempt < len(RETRY_WAITS):
            time.sleep(RETRY_WAITS[attempt])

    raise JikanError(f"{url} failed: {last_problem}")


def get_all_pages(path: str, params: dict | None = None) -> list[dict]:
    """Follow Jikan's pagination and return every item in `data`."""
    items, page = [], 1
    while True:
        body = get(path, {**(params or {}), "page": page})
        items.extend(body["data"])
        if not body.get("pagination", {}).get("has_next_page"):
            return items
        page += 1
