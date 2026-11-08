"""Download NBA regular-season team game logs into data/raw/.

The analysis never calls this; it reads the committed CSVs. Run it only to
refresh the snapshot:  uv run --group fetch python scripts/fetch_data.py
"""

import time
from pathlib import Path

from nba_api.stats.endpoints import leaguegamelog

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
FIRST_SEASON, LAST_SEASON = 2000, 2025  # start years: 2000-01 .. 2025-26


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for year in range(FIRST_SEASON, LAST_SEASON + 1):
        season = f"{year}-{str(year + 1)[2:]}"
        if (OUT / f"gamelog_{season}.csv").exists():
            continue  # delete a file to refetch it
        df = leaguegamelog.LeagueGameLog(season=season, timeout=60).get_data_frames()[0]
        df.to_csv(OUT / f"gamelog_{season}.csv", index=False)
        print(season, len(df), "team rows,", df["GAME_ID"].nunique(), "games")
        time.sleep(1)  # stats.nba.com throttles bursts


if __name__ == "__main__":
    main()
