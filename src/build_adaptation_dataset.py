"""Build the dataset for question 1: how long after its source started did each anime air?

Steps:
  1. List every TV anime from 2005-2024 that MyAnimeList says is adapted from a
     manga, web manga, 4-koma manga, or light novel, and has at least 1,000 ratings.
  2. Drop sequels (anything with a "prequel" or "parent story" relation), so each
     anime is the first adaptation of its source.
  3. Find the source. MyAnimeList's API doesn't expose anime-to-manga links, so
     this searches manga titles and only accepts a match when the titles match
     closely, the type fits (light novel vs. manga), and the source started first.

Every API response is cached in data/cache, so this can be stopped and re-run.
Each run works for at most --max-minutes and then exits; run it again to continue.

Writes data/adaptation.csv (matched) and data/adaptation_unmatched.csv (for checking).
"""
import argparse
import difflib
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

import mal_official as mal

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
YEARS = range(2005, 2025)
SEASONS = ["winter", "spring", "summer", "fall"]
MIN_RATERS = 1000
ANIME_FIELDS = ("id,title,alternative_titles,media_type,source,start_date,mean,num_scoring_users,"
                "num_list_users,num_episodes,genres,studios")
MANGA_FIELDS = "id,title,alternative_titles,media_type,start_date,mean,num_scoring_users,num_list_users"

# Which MyAnimeList manga types count as the right kind of source.
SOURCE_TYPES = {
    "manga": {"manga", "manhwa", "manhua", "one_shot"},
    "web_manga": {"manga", "manhwa", "manhua"},
    "4_koma_manga": {"manga"},
    "light_novel": {"light_novel"},
}
MIN_TITLE_SIMILARITY = 0.9


def search_text(title: str) -> str:
    """Strip things that break MyAnimeList's search: a year in parentheses, "S1", symbols."""
    title = re.sub(r"\(\d{4}\)", "", title)
    title = re.sub(r"\bS\d+\b", "", title)
    title = re.sub(r"[%☆★♥♪]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def normalize(title: str) -> str:
    title = unicodedata.normalize("NFKC", title or "").lower()
    title = re.sub(r"\(tv\)|\(\d{4}\)", "", title)
    title = re.sub(r"[^\w\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def all_titles(node: dict) -> list[str]:
    alt = node.get("alternative_titles") or {}
    titles = [node.get("title"), alt.get("en"), alt.get("ja"), *(alt.get("synonyms") or [])]
    return [normalize(t) for t in titles if t]


def similarity(a: dict, b: dict) -> float:
    return max((difflib.SequenceMatcher(None, x, y).ratio() for x in all_titles(a) for y in all_titles(b)),
               default=0.0)


def list_candidates() -> pd.DataFrame:
    rows = []
    for year in YEARS:
        for season in SEASONS:
            body = mal.get(f"anime/season/{year}/{season}",
                           {"fields": ANIME_FIELDS, "limit": 500, "nsfw": "true"})
            for item in body["data"]:
                node = item["node"]
                started = node.get("start_date") or ""
                # Long-running shows show up in later seasons' listings, so check the real start year.
                if (node.get("media_type") == "tv" and node.get("source") in SOURCE_TYPES
                        and (node.get("num_scoring_users") or 0) >= MIN_RATERS
                        and started[:4].isdigit() and int(started[:4]) in YEARS):
                    rows.append(node)
    nodes = {node["id"]: node for node in rows}  # a show can be listed in more than one season
    return list(nodes.values())


def is_sequel(anime_id: int) -> bool:
    detail = mal.get(f"anime/{anime_id}", {"fields": "related_anime"})
    return any(r["relation_type"] in ("prequel", "parent_story") for r in detail.get("related_anime", []))


def find_source(anime: dict) -> tuple[dict | None, float]:
    allowed = SOURCE_TYPES[anime["source"]]
    queries = [anime["title"]]
    english = (anime.get("alternative_titles") or {}).get("en")
    if english and normalize(english) != normalize(anime["title"]):
        queries.append(english)

    best, best_score = None, 0.0
    for query in queries:
        query = search_text(query)[:64]  # the API rejects long queries
        if len(query) < 3:
            continue
        try:
            results = mal.get("manga", {"q": query, "limit": 10, "fields": MANGA_FIELDS})["data"]
        except mal.MALError:
            continue
        for item in results:
            manga = item["node"]
            if manga.get("media_type") not in allowed or not manga.get("start_date"):
                continue
            if manga["start_date"] > anime["start_date"]:
                continue
            score = similarity(anime, manga)
            if score > best_score or (score == best_score and best and
                                      (manga.get("num_list_users") or 0) > (best.get("num_list_users") or 0)):
                best, best_score = manga, score
        if best_score >= MIN_TITLE_SIMILARITY:
            break
    return (best, best_score) if best_score >= MIN_TITLE_SIMILARITY else (None, best_score)


def names(items) -> str:
    return "; ".join(i["name"] for i in items or [])


def save(matched: list[dict], unmatched: list[dict]):
    pd.DataFrame(matched).to_csv(DATA / "adaptation.csv", index=False)
    pd.DataFrame(unmatched).to_csv(DATA / "adaptation_unmatched.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-minutes", type=float, default=9)
    args = parser.parse_args()
    deadline = time.time() + args.max_minutes * 60

    candidates = list_candidates()
    print(f"{len(candidates)} TV adaptations with {MIN_RATERS}+ ratings, 2005-2024")

    matched, unmatched, sequels = [], [], 0
    for n, anime in enumerate(candidates, start=1):
        if time.time() > deadline:
            save(matched, unmatched)
            print(f"time limit reached at {n - 1}/{len(candidates)}; partial results saved, run again to continue")
            sys.exit(3)
        if is_sequel(anime["id"]):
            sequels += 1
            continue
        manga, score = find_source(anime)
        row = {
            "anime_id": anime["id"],
            "anime_title": anime["title"],
            "anime_title_english": (anime.get("alternative_titles") or {}).get("en") or None,
            "source": anime["source"],
            "anime_start": anime["start_date"],
            "anime_score": anime.get("mean"),
            "anime_raters": anime.get("num_scoring_users"),
            "anime_members": anime.get("num_list_users"),
            "episodes": anime.get("num_episodes"),
            "genres": names(anime.get("genres")),
            "studios": names(anime.get("studios")),
            "title_match": round(score, 3),
        }
        if manga:
            row.update({
                "source_id": manga["id"],
                "source_title": manga["title"],
                "source_type": manga["media_type"],
                "source_start": manga["start_date"],
                "source_score": manga.get("mean"),
                "source_members": manga.get("num_list_users"),
            })
            matched.append(row)
        else:
            unmatched.append(row)
        if n % 100 == 0:
            print(f"{n}/{len(candidates)} checked", flush=True)

    save(matched, unmatched)
    print(f"done: {len(matched)} matched, {len(unmatched)} unmatched, {sequels} sequels skipped")


if __name__ == "__main__":
    main()
