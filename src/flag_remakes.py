"""Mark which anime in the adaptation dataset are remakes of an earlier anime.

The sequel filter only catches "prequel" links. Remakes like Urusei Yatsura (2022)
are linked to the original as an "alternative version" instead, and their gap
to the source (decades) means something different from a first adaptation's.

Adds two columns to data/adaptation.csv and data/adaptation_unmatched.csv:
  is_remake           True if an earlier TV anime is listed as an alternative version
  earlier_version     title of that earlier anime, if any

Resumable like the dataset builder: re-run until it prints "done".
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

import mal_official as mal

DATA = Path(__file__).resolve().parent.parent / "data"
FIELDS = "related_anime{node{start_date,media_type}}"


def earlier_version(anime_id: int, anime_start: str) -> str | None:
    detail = mal.get(f"anime/{anime_id}", {"fields": FIELDS})
    for related in detail.get("related_anime", []):
        node = related["node"]
        if (related["relation_type"] == "alternative_version" and node.get("media_type") == "tv"
                and node.get("start_date") and node["start_date"] < anime_start):
            return node["title"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-minutes", type=float, default=9)
    args = parser.parse_args()
    deadline = time.time() + args.max_minutes * 60

    for name in ["adaptation.csv", "adaptation_unmatched.csv"]:
        table = pd.read_csv(DATA / name)
        versions = []
        for n, row in enumerate(table.itertuples(), start=1):
            if time.time() > deadline:
                print(f"{name}: time limit at {n - 1}/{len(table)}; run again to continue")
                sys.exit(3)
            versions.append(earlier_version(row.anime_id, row.anime_start))
        table["earlier_version"] = versions
        table["is_remake"] = table["earlier_version"].notna()
        table.to_csv(DATA / name, index=False)
        print(f"{name}: {table['is_remake'].sum()} remakes flagged")
    print("done")


if __name__ == "__main__":
    main()
