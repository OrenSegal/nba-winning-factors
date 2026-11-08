"""Pre-game features (knowable at tipoff) and same-game four factors (outcomes).

Pre-game features are season-to-date means over a team's *earlier* games only:
each team's per-game values are shifted by one game before the expanding mean,
so a game's own box score never reaches its own features.
"""

import numpy as np
import pandas as pd

from nbawin.data import STATS

MIN_PRIOR_GAMES = 10  # drop games where either team has fewer earlier games this season


def possessions(fga, fta, oreb, tov):
    """Standard possession estimate: FGA + 0.44*FTA - OREB + TOV."""
    return fga + 0.44 * fta - oreb + tov


def four_factors(own: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    """Dean Oliver's four factors for one side of a game, from box-score columns."""
    poss = possessions(own["FGA"], own["FTA"], own["OREB"], own["TOV"])
    return pd.DataFrame(
        {
            "efg": (own["FGM"] + 0.5 * own["FG3M"]) / own["FGA"],
            "tov_rate": own["TOV"] / poss,
            "orb_rate": own["OREB"] / (own["OREB"] + opp["DREB"]),
            "ft_rate": own["FTM"] / own["FGA"],
        }
    )


def _box(games: pd.DataFrame, side: str) -> pd.DataFrame:
    """One side's box score with unprefixed column names (FGM, ..., team)."""
    cols = {f"{side}_{c}": c for c in STATS} | {f"{side}_team": "team"}
    return games[list(cols)].rename(columns=cols)


def _side(games: pd.DataFrame, side: str) -> pd.DataFrame:
    own, opp = _box(games, side), _box(games, "away" if side == "home" else "home")
    off, dfn = four_factors(own, opp), four_factors(opp, own)
    poss = (possessions(own["FGA"], own["FTA"], own["OREB"], own["TOV"])
            + possessions(opp["FGA"], opp["FTA"], opp["OREB"], opp["TOV"])) / 2
    return pd.DataFrame(
        {
            "GAME_ID": games["GAME_ID"],
            "SEASON": games["SEASON"],
            "GAME_DATE": games["GAME_DATE"],
            "team": own["team"],
            "side": side,
            "win": (own["PTS"] > opp["PTS"]).astype(float),
            "net_rtg": 100 * (own["PTS"] - opp["PTS"]) / poss,
            **{f"off_{k}": v for k, v in off.items()},
            **{f"def_{k}": v for k, v in dfn.items()},
        }
    )


TEAM_STATS = ["win", "net_rtg"] + [f"{p}_{k}" for p in ("off", "def") for k in ("efg", "tov_rate", "orb_rate", "ft_rate")]


def team_pregame(games: pd.DataFrame) -> pd.DataFrame:
    """Per team-game: season-to-date means of TEAM_STATS over earlier games, plus rest."""
    long = pd.concat([_side(games, "home"), _side(games, "away")], ignore_index=True)
    long = long.sort_values(["SEASON", "team", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    g = long.groupby(["SEASON", "team"], sort=False)
    pre = pd.DataFrame({"GAME_ID": long["GAME_ID"], "side": long["side"]})
    for col in TEAM_STATS:
        pre[f"pre_{col}"] = g[col].transform(lambda s: s.shift(1).expanding().mean())
    pre["prior_games"] = g.cumcount()
    pre["rest_days"] = g["GAME_DATE"].diff().dt.days.clip(upper=7)  # NaN for a season opener
    return pre


def pregame_features(games: pd.DataFrame) -> pd.DataFrame:
    """One row per game: home-minus-away pre-game differences plus back-to-back flags.

    Rows where either team has fewer than MIN_PRIOR_GAMES earlier games are dropped.
    """
    pre = team_pregame(games)
    home = pre[pre["side"] == "home"].drop(columns="side").set_index("GAME_ID")
    away = pre[pre["side"] == "away"].drop(columns="side").set_index("GAME_ID")
    out = games[["GAME_ID", "SEASON", "GAME_DATE", "home_team", "away_team", "home_win", "margin"]].set_index("GAME_ID")
    for col in TEAM_STATS:
        out[f"d_{col}"] = home[f"pre_{col}"] - away[f"pre_{col}"]
    out["d_rest"] = home["rest_days"] - away["rest_days"]
    out["home_b2b"] = (home["rest_days"] == 1).astype(int)
    out["away_b2b"] = (away["rest_days"] == 1).astype(int)
    keep = (home["prior_games"] >= MIN_PRIOR_GAMES) & (away["prior_games"] >= MIN_PRIOR_GAMES)
    return out[keep.reindex(out.index)].reset_index()


FEATURES = [f"d_{c}" for c in TEAM_STATS] + ["d_rest", "home_b2b", "away_b2b"]


def same_game_factor_diffs(games: pd.DataFrame) -> pd.DataFrame:
    """Home-minus-away four factors *from the game itself*. Outcomes, not predictors."""
    home, away = _box(games, "home"), _box(games, "away")
    diff = four_factors(home, away) - four_factors(away, home)
    diff.columns = [f"d_{c}" for c in diff.columns]
    diff.insert(0, "SEASON", games["SEASON"].to_numpy())
    diff.insert(0, "GAME_ID", games["GAME_ID"].to_numpy())
    diff["margin"] = games["margin"].to_numpy()
    diff["home_win"] = games["home_win"].to_numpy()
    return diff.replace([np.inf, -np.inf], np.nan).dropna()
