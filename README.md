# What Makes an Anime Land?

A data project on MyAnimeList ratings. I'm looking at three things:

1. **The adaptation gap.** Does the time between when a manga or light novel started and when its anime aired relate to how the anime is rated? Is it different for manga and light novels?
2. **Pile-on ratings.** Which genres get an unusually large share of 1/10 ratings compared with what their average score would predict?
3. **Hype vs. reality.** Do shows with the most pre-air hype (people adding them to their lists before episode 1) end up rated better or worse once they air?

## Status

Collecting data. The third question needs numbers from *before* shows air, and MyAnimeList only shows today's numbers, so a script records every Winter and Spring 2027 anime three times a day starting October 2026. Analysis comes once those seasons have aired.

## How the collector works

- `src/collect_season.py` saves one snapshot per day to `data/snapshots/<date>.csv`: members, score, number of raters, status, source type, genres, and studios for every anime in the tracked seasons.
- It uses MyAnimeList's official API when a Client ID is set up, and [Jikan](https://jikan.moe) (an unofficial MyAnimeList API) otherwise. Jikan sometimes can't reach MyAnimeList, so requests are retried with backoff, and a day with failures saves a partial file that a later run can replace.
- `scripts/com.allenlong.anime-snapshot.plist` is the macOS launchd job that runs it at 9am, 3pm, and 9pm. If the Mac is asleep, it runs on wake.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/collect_season.py
```

To use the official API, create a Client ID at https://myanimelist.net/apiconfig and save just the ID in a file called `.mal_client_id` in this folder. It's in `.gitignore`.

## Data

All data comes from [MyAnimeList](https://myanimelist.net), through its official API and Jikan. The collected snapshots stay local and aren't committed to this repo.
