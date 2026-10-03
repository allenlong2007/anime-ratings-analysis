"""Take one daily snapshot of every anime in the seasons being tracked.

MyAnimeList only shows today's numbers. To measure hype *before* a show airs,
the numbers have to be recorded while it's still upcoming, so this runs once a
day and saves what it sees to data/snapshots/<date>.csv.

Run:  python src/collect_season.py            (skips if today's snapshot exists)
      python src/collect_season.py --force    (overwrite today's snapshot)
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import mal_official
from jikan import JikanError, get_all_pages

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "data" / "snapshots"

# Seasons to follow from announcement through airing. Add the next season once
# its shows are announced; keep old ones so post-air numbers keep coming in.
TRACKED_SEASONS = [(2027, "winter"), (2027, "spring")]


def names(items: list[dict] | None) -> str:
    return "; ".join(item["name"] for item in items or [])


def to_row(anime: dict, season: str, taken_at: datetime, api: str) -> dict:
    return {
        "snapshot_date": taken_at.date().isoformat(),
        "snapshot_time_utc": taken_at.isoformat(timespec="seconds"),
        "season": season,
        "mal_id": anime["mal_id"],
        "title": anime["title"],
        "title_english": anime.get("title_english"),
        "type": anime.get("type"),
        "source": anime.get("source"),
        "status": anime.get("status"),
        "aired_from": (anime.get("aired") or {}).get("from"),
        "episodes": anime.get("episodes"),
        "members": anime.get("members"),
        "favorites": anime.get("favorites"),
        "score": anime.get("score"),
        "scored_by": anime.get("scored_by"),
        "rank": anime.get("rank"),
        "popularity": anime.get("popularity"),
        "genres": names(anime.get("genres")),
        "themes": names(anime.get("themes")),
        "demographics": names(anime.get("demographics")),
        "studios": names(anime.get("studios")),
        "api": api,
    }


def fetch_season(year: int, season: str) -> tuple[list[dict], str]:
    """Use the official API when a Client ID is set up, and Jikan otherwise or as a fallback."""
    if mal_official.client_id():
        try:
            return mal_official.season_anime(year, season), "official"
        except mal_official.MALError as error:
            print(f"{year}-{season}: official API failed ({error}), trying Jikan", file=sys.stderr)
    return get_all_pages(f"seasons/{year}/{season}"), "jikan"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite today's snapshot")
    args = parser.parse_args()

    taken_at = datetime.now(timezone.utc)
    out_path = SNAPSHOTS / f"{taken_at.date().isoformat()}.csv"
    partial_path = out_path.with_suffix(".partial.csv")
    if out_path.exists() and not args.force:
        print(f"{out_path.name} already exists, skipping")
        return

    rows, failures = [], []
    for year, season in TRACKED_SEASONS:
        label = f"{year}-{season}"
        try:
            anime_list, api = fetch_season(year, season)
            rows.extend(to_row(anime, label, taken_at, api) for anime in anime_list)
            print(f"{label}: ok via {api} ({len(anime_list)} anime)")
        except (JikanError, mal_official.MALError) as error:
            failures.append(label)
            print(f"{label}: FAILED ({error})", file=sys.stderr)

    if not rows:
        print("no data collected today", file=sys.stderr)
        sys.exit(1)

    snapshot = pd.DataFrame(rows).drop_duplicates(["season", "mal_id"])
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    if failures:
        # Keep what we got, but let a later run today try again for a full snapshot.
        snapshot.to_csv(partial_path, index=False)
        print(f"saved partial snapshot ({len(snapshot)} anime) to {partial_path.name}")
        sys.exit(2)
    snapshot.to_csv(out_path, index=False)
    partial_path.unlink(missing_ok=True)
    print(f"saved {len(snapshot)} anime to {out_path.name}")


if __name__ == "__main__":
    main()
