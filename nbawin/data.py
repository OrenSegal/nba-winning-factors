"""Load raw team game logs and reshape them to one row per game."""

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Box-score columns kept for each side of a game.
STATS = ["FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF", "PTS"]


def load_team_logs(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """All team-game rows (two per game) from every gamelog_*.csv, tagged with season."""
    frames = []
    for path in sorted(raw_dir.glob("gamelog_*.csv")):
        df = pd.read_csv(path, dtype={"GAME_ID": str})
        df["SEASON"] = path.stem.removeprefix("gamelog_")
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"no gamelog_*.csv in {raw_dir}")
    logs = pd.concat(frames, ignore_index=True)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"])
    return logs


def to_games(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per game: home_* and away_* box scores, home_win, margin.

    MATCHUP reads 'LAL vs. MIN' for the home team and 'MIN @ LAL' for the away team.
    Neutral-site games (both rows use '@', e.g. Paris, Mexico City, NBA Cup
    semifinals) have no home team and are dropped.
    """
    is_home = logs["MATCHUP"].str.contains(" vs. ", regex=False)
    n_home = is_home.groupby(logs["GAME_ID"]).transform("sum")
    logs, is_home = logs[n_home == 1], is_home[n_home == 1]
    keys = ["GAME_ID", "SEASON", "GAME_DATE"]
    cols = keys + ["TEAM_ABBREVIATION"] + STATS
    home = logs.loc[is_home, cols].rename(columns=lambda c: c if c in keys else f"home_{c}")
    away = logs.loc[~is_home, cols].rename(columns=lambda c: c if c in keys else f"away_{c}")
    games = home.merge(away, on=keys, how="inner", validate="one_to_one")
    if len(games) != logs["GAME_ID"].nunique():
        raise ValueError("some games lack a matching away row")
    games = games.rename(columns={"home_TEAM_ABBREVIATION": "home_team", "away_TEAM_ABBREVIATION": "away_team"})
    games["margin"] = games["home_PTS"] - games["away_PTS"]
    games["home_win"] = (games["margin"] > 0).astype(int)
    return games.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)
