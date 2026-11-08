"""Download team-season advanced, shot-zone, tracking and hustle tables into data/raw/teamseason_<season>.csv.

One row per team per season, columns prefixed by the table they came from. The analysis never calls
this; it reads the committed CSVs. Refresh with:  uv run --group fetch python scripts/fetch_teamseason.py
Delete a file to refetch that season. Tracking tables start in 2013-14, hustle in 2015-16.
"""

import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import (
    leaguedashptstats as pt,
    leaguedashteamshotlocations as zones,
    leaguedashteamstats as ts,
    leaguehustlestatsteam as hustle,
)

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
FIRST_SEASON, LAST_SEASON = 2000, 2025
TRACKING_FROM, HUSTLE_FROM = 2013, 2015

BOX = {"adv": "Advanced", "ff": "Four Factors", "misc": "Misc", "score": "Scoring", "opp": "Opponent"}
TRACK = {"drv": "Drives", "cs": "CatchShoot", "pu": "PullUpShot", "pass": "Passing", "poss": "Possessions",
         "def": "Defense", "paint": "PaintTouch", "post": "PostTouch", "elbow": "ElbowTouch",
         "speed": "SpeedDistance", "reb": "Rebounding"}
KEY = ["TEAM_ID", "TEAM_NAME"]
DROP = {"GP", "W", "L", "W_PCT", "MIN", "TEAM_ABBREVIATION", "CFID", "CFPARAMS"}


def _try(fn, tries=4):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # stats.nba.com drops connections under load
            if i == tries - 1:
                raise
            print("  retry:", type(e).__name__)
            time.sleep(5 * (i + 1))


def _tidy(df: pd.DataFrame, tag: str, keep_record: bool = False) -> pd.DataFrame:
    df = df[[c for c in df.columns if not c.endswith("_RANK")]]
    drop = {"TEAM_NAME"} | (set() if keep_record else DROP)
    cols = {c: f"{tag}_{c}" for c in df.columns if c != "TEAM_ID" and c not in drop}
    return df[["TEAM_ID", *cols]].rename(columns=cols)


def fetch_season(year: int) -> pd.DataFrame:
    season = f"{year}-{str(year + 1)[2:]}"
    parts = []
    for i, (tag, mt) in enumerate(BOX.items()):
        f = lambda: ts.LeagueDashTeamStats(season=season, measure_type_detailed_defense=mt,
                                           per_mode_detailed="PerGame", timeout=60).get_data_frames()[0]
        df = _try(f)
        if i == 0:
            record = df[["TEAM_ID", "TEAM_NAME", "GP", "W", "L", "W_PCT"]]
        parts.append(_tidy(df, tag))
        time.sleep(1)
    z = _try(lambda: zones.LeagueDashTeamShotLocations(season=season, per_mode_detailed="PerGame",
                                                       timeout=60).get_data_frames()[0])
    z.columns = [b if not a else f"{a}_{b}" for a, b in z.columns]
    z.columns = [c.replace(" ", "").replace("(", "").replace(")", "").replace("-", "") for c in z.columns]
    parts.append(_tidy(z, "zone"))
    time.sleep(1)
    if year >= TRACKING_FROM:
        for tag, mt in TRACK.items():
            f = lambda: pt.LeagueDashPtStats(season=season, pt_measure_type=mt, player_or_team="Team",
                                             per_mode_simple="PerGame", timeout=60).get_data_frames()[0]
            parts.append(_tidy(_try(f), tag))
            time.sleep(1)
    if year >= HUSTLE_FROM:
        f = lambda: hustle.LeagueHustleStatsTeam(season=season, per_mode_time="PerGame", timeout=60).get_data_frames()[0]
        parts.append(_tidy(_try(f), "hus"))
    out = record
    for p in parts:
        out = out.merge(p, on="TEAM_ID", how="left")
    out.insert(0, "SEASON", season)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for year in range(FIRST_SEASON, LAST_SEASON + 1):
        path = OUT / f"teamseason_{year}-{str(year + 1)[2:]}.csv"
        if path.exists():
            continue
        df = fetch_season(year)
        df.to_csv(path, index=False)
        print(path.name, df.shape)


if __name__ == "__main__":
    main()
