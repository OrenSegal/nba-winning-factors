"""Download NBA regular-season team game logs into data/raw/.

The analysis never calls this; it reads the committed CSVs. Run it only to
refresh the snapshot:  uv run --group fetch python scripts/fetch_data.py
"""

import time
from pathlib import Path

from nba_api.stats.endpoints import leaguegamelog

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
FIRST_SEASON, LAST_SEASON = 2015, 2024  # start years: 2015-16 .. 2024-25


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for year in range(FIRST_SEASON, LAST_SEASON + 1):
        season = f"{year}-{str(year + 1)[2:]}"
        df = leaguegamelog.LeagueGameLog(season=season, timeout=60).get_data_frames()[0]
        df.to_csv(OUT / f"gamelog_{season}.csv", index=False)
        print(season, len(df), "team rows,", df["GAME_ID"].nunique(), "games")
        time.sleep(1)  # stats.nba.com throttles bursts


if __name__ == "__main__":
    main()
