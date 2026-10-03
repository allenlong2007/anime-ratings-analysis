#!/bin/sh
# Called three times a day by launchd (see scripts/com.allenlong.anime-snapshot.plist).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
echo "--- $(date '+%Y-%m-%d %H:%M:%S')" >> logs/collector.log
.venv/bin/python src/collect_season.py >> logs/collector.log 2>&1
echo "exit code $?" >> logs/collector.log
