"""A wide candidate-factor table. Every factor is knowable at tipoff.

Team-level factors are season-to-date means over *earlier* games only (shift one game
before aggregating), the same discipline as features.py. Elo carries rating across
seasons, so it is also defined for opening-week games.
"""

import numpy as np
import pandas as pd

from nbawin.features import MIN_PRIOR_GAMES, _box, four_factors, possessions
from nbawin.teams import ARENAS, franchise, haversine_km

EWM_HALFLIVES = (2, 3, 5, 8, 12, 20, 30, 50, 80)  # in games
FF = [f"{p}_{k}" for p in ("off", "def") for k in ("efg", "tov_rate", "orb_rate", "ft_rate")]
STYLE = ["pace", "fg3a_rate", "fg3_pct", "def_fg3a_rate", "def_fg3_pct", "ft_pct", "ast_rate",
         "stl_rate", "blk_rate", "pf_rate", "drawn_fouls"]
SHOT = ["fg3a", "fg3_pts_share", "ts", "reb_share"]
RAW_MEANS = ["win", "net_rtg"] + FF + STYLE + SHOT

FAMILIES = {
    "Strength": ["elo_diff", "d_net_rtg", "d_win"],
    "Recent form": ["d_ewm5", "d_ewm8", "d_ewm20", "d_form10"],
    "Four factors": [f"d_{c}" for c in FF],
    "Pace and style": [f"d_{c}" for c in STYLE],
    "Shot profile": [f"d_{c}" for c in SHOT],
    "Rest and schedule load": ["d_rest", "home_b2b", "away_b2b", "home_g4n3", "away_g4n3", "home_g6n5", "away_g6n5"],
    "Home stands and road trips": ["home_streak", "away_streak"],
    "Travel and time zones": ["home_travel", "away_travel", "home_tz_east", "home_tz_west", "away_tz_east", "away_tz_west"],
    "Altitude": ["home_alt_km", "d_alt"],
    "Luck and regression": ["d_luck", "d_close_net"],
    "Volatility and matchup shape": ["vol_sum", "fav_x_vol", "pace_sum_rel", "abs_d_pace"],
    "Era regime": ["league_home_rate"],
    "Calendar and rematches": ["season_day", "is_weekend", "rematch_n"],
}
ALL_FEATURES = [c for cols in FAMILIES.values() for c in cols]
FAMILY_OF = {c: fam for fam, cols in FAMILIES.items() for c in cols}

_FF_TEXT = {"efg": "effective FG%", "tov_rate": "turnover rate", "orb_rate": "offensive rebound rate", "ft_rate": "free-throw rate"}
_STYLE_TEXT = {"pace": "pace (possessions per game)", "fg3a_rate": "three-point attempt rate", "fg3_pct": "three-point %",
               "def_fg3a_rate": "opponent three-point attempt rate", "def_fg3_pct": "opponent three-point % allowed",
               "ft_pct": "free-throw %", "ast_rate": "assists per made field goal", "stl_rate": "steals per opponent possession",
               "blk_rate": "blocks per opponent two-point attempt", "pf_rate": "fouls committed per possession",
               "drawn_fouls": "fouls drawn per possession", "fg3a": "three-point attempts per game",
               "fg3_pts_share": "share of points from threes", "ts": "true shooting %", "reb_share": "share of all rebounds"}
_DIFF = "Home minus away season-to-date "
DEFINITIONS = {
    "elo_diff": "Home minus away Elo rating (margin-adjusted, carried across seasons)",
    "d_net_rtg": _DIFF + "net rating (points per 100 possessions)", "d_win": _DIFF + "win %",
    "d_form10": "Home minus away last-10-game net rating relative to the season average",
    **{f"d_ewm{h}": f"Home minus away net rating, recency-weighted with a {h}-game half-life" for h in (5, 8, 20)},
    **{f"d_{p}_{k}": _DIFF + ("own " if p == "off" else "opponent-allowed ") + t for p in ("off", "def") for k, t in _FF_TEXT.items()},
    **{f"d_{k}": _DIFF + t for k, t in _STYLE_TEXT.items()},
    "d_rest": "Home minus away days since the last game (capped at 7)",
    "home_b2b": "Home team played yesterday", "away_b2b": "Away team played yesterday",
    "home_g4n3": "Home team's earlier games in the last 3 days (3-in-4 when 2+)", "away_g4n3": "Away team's earlier games in the last 3 days",
    "home_g6n5": "Home team's earlier games in the last 5 days (4-in-6 when 3+)", "away_g6n5": "Away team's earlier games in the last 5 days",
    "home_streak": "Consecutive earlier home games for the home team", "away_streak": "Consecutive earlier road games for the away team",
    "home_travel": "Home team's travel since its last game, thousand km", "away_travel": "Away team's travel since its last game, thousand km",
    "home_tz_east": "Time zones the home team crossed eastward", "home_tz_west": "Time zones the home team crossed westward",
    "away_tz_east": "Time zones the away team crossed eastward", "away_tz_west": "Time zones the away team crossed westward",
    "home_alt_km": "Altitude of the arena, km", "d_alt": "Home arena altitude minus away arena altitude, km",
    "d_luck": "Home minus away win % above what points scored and allowed imply (Pythagorean)",
    "d_close_net": "Home minus away net wins in games decided by 5 or fewer",
    "vol_sum": "Sum of both teams' game-to-game net-rating volatility", "fav_x_vol": "Elo gap times combined volatility",
    "pace_sum_rel": "Combined pace of both teams relative to the league's recent average", "abs_d_pace": "Absolute pace gap between the teams",
    "league_home_rate": "League-wide home win rate over the previous 1000 games (the era's home-court regime)",
    "season_day": "Share of the season elapsed (0 to 1)", "is_weekend": "Played on a Saturday or Sunday",
    "rematch_n": "Earlier meetings of these two teams this season",
}


def team_games(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game with that game's own (outcome) stats."""
    parts = []
    for side, other in (("home", "away"), ("away", "home")):
        own, opp = _box(games, side), _box(games, other)
        ff, dff = four_factors(own, opp), four_factors(opp, own)
        poss_own = possessions(own["FGA"], own["FTA"], own["OREB"], own["TOV"])
        poss_opp = possessions(opp["FGA"], opp["FTA"], opp["OREB"], opp["TOV"])
        poss = (poss_own + poss_opp) / 2
        parts.append(pd.DataFrame({
            "GAME_ID": games["GAME_ID"], "SEASON": games["SEASON"], "GAME_DATE": games["GAME_DATE"],
            "team": own["team"], "opp": opp["team"], "is_home": side == "home", "venue": games["home_team"],
            "pts": own["PTS"], "opp_pts": opp["PTS"], "fg3a": own["FG3A"],
            "win": (own["PTS"] > opp["PTS"]).astype(float),
            "net_rtg": 100 * (own["PTS"] - opp["PTS"]) / poss,
            "pace": poss,
            "fg3a_rate": own["FG3A"] / own["FGA"], "fg3_pct": own["FG3M"] / own["FG3A"],
            "def_fg3a_rate": opp["FG3A"] / opp["FGA"], "def_fg3_pct": opp["FG3M"] / opp["FG3A"],
            "ft_pct": own["FTM"] / own["FTA"], "ast_rate": own["AST"] / own["FGM"],
            "stl_rate": own["STL"] / poss_opp, "blk_rate": own["BLK"] / (opp["FGA"] - opp["FG3A"]),
            "fg3_pts_share": 3 * own["FG3M"] / own["PTS"], "ts": own["PTS"] / (2 * (own["FGA"] + 0.44 * own["FTA"])),
            "reb_share": (own["OREB"] + own["DREB"]) / (own["OREB"] + own["DREB"] + opp["OREB"] + opp["DREB"]),
            "pf_rate": own["PF"] / poss, "drawn_fouls": opp["PF"] / poss,
            **{f"off_{k}": v for k, v in ff.items()}, **{f"def_{k}": v for k, v in dff.items()},
        }))
    tg = pd.concat(parts, ignore_index=True).replace([np.inf, -np.inf], np.nan)
    tg["fr"] = tg["team"].map(franchise)
    return tg


def elo_pregame(games: pd.DataFrame, k=20.0, carry=0.75, home_adv=100.0) -> pd.DataFrame:
    """Pre-game Elo (margin-of-victory adjusted) for both teams; rating regresses a quarter to 1505 each season."""
    g = games.sort_values(["GAME_DATE", "GAME_ID"])
    rating, season, out = {}, None, []
    for gid, s, ht, at, margin in zip(g["GAME_ID"], g["SEASON"], g["home_team"], g["away_team"],
                                      g["home_PTS"] - g["away_PTS"]):
        if s != season:
            rating = {t: carry * r + (1 - carry) * 1505 for t, r in rating.items()}
            season = s
        fh, fa = franchise(ht), franchise(at)
        rh, ra = rating.setdefault(fh, 1500.0), rating.setdefault(fa, 1500.0)
        out.append((gid, rh, ra))
        dr = rh + home_adv - ra
        home_won = margin > 0
        mult = (abs(margin) + 3) ** 0.8 / (7.5 + 0.006 * (dr if home_won else -dr))
        delta = k * mult * (home_won - 1 / (1 + 10 ** (-dr / 400)))
        rating[fh], rating[fa] = rh + delta, ra - delta
    df = pd.DataFrame(out, columns=["GAME_ID", "elo_home", "elo_away"]).set_index("GAME_ID")
    df.attrs["final"] = rating  # ratings after the last game, by franchise
    return df


def _prior_in_window(s: pd.Series, w: int) -> pd.Series:
    """Earlier games within the w days before each game (days sorted ascending)."""
    d = s.to_numpy()
    return pd.Series(np.arange(len(d)) - np.searchsorted(d, d - w, side="left"), index=s.index)


def _streak(s: pd.Series) -> pd.Series:
    """Consecutive earlier games at the same location type (home/away) as the current game."""
    h, out = s.to_numpy(), np.zeros(len(s), int)
    for i in range(1, len(h)):
        out[i] = out[i - 1] + 1 if h[i - 1] == h[i] else 0
    return pd.Series(out, index=s.index)


def team_pregame(tg: pd.DataFrame) -> pd.DataFrame:
    """Per team-game pre-game factors: season-to-date means, form, volatility, luck, schedule, travel."""
    tg = tg.sort_values(["SEASON", "team", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    g = tg.groupby(["SEASON", "team"], sort=False)
    out = tg[["GAME_ID", "is_home", "team", "venue"]].copy()
    out["prior_games"] = g.cumcount()
    prior = lambda col, fn: g[col].transform(lambda s: fn(s.shift(1)))
    for c in RAW_MEANS:
        out[f"pre_{c}"] = prior(c, lambda s: s.expanding().mean())
    out["pre_sd_net"] = prior("net_rtg", lambda s: s.expanding(min_periods=5).std())
    out["pre_last10"] = prior("net_rtg", lambda s: s.rolling(10, min_periods=5).mean())
    out["pre_form10"] = out["pre_last10"] - out["pre_net_rtg"]
    for h in EWM_HALFLIVES:
        out[f"pre_ewm{h}"] = prior("net_rtg", lambda s, h=h: s.ewm(halflife=h).mean())
    pts = (g["pts"].cumsum() - tg["pts"]).astype(float)
    opp = (g["opp_pts"].cumsum() - tg["opp_pts"]).astype(float)
    pyth = (pts**14 / (pts**14 + opp**14)).where(pts > 0)  # expected win% from points scored and allowed
    out["pre_luck"] = out["pre_win"] - pyth
    close = ((tg["pts"] - tg["opp_pts"]).abs() <= 5) * (2 * tg["win"] - 1)
    out["pre_close_net"] = close.groupby([tg["SEASON"], tg["team"]], sort=False).cumsum() - close
    day = (tg["GAME_DATE"] - pd.Timestamp("2000-01-01")).dt.days
    tg["_day"] = day
    g = tg.groupby(["SEASON", "team"], sort=False)
    out["rest_days"] = g["_day"].diff().clip(upper=7)
    out["g4n3"] = g["_day"].transform(lambda s: _prior_in_window(s, 3))  # 3-in-4 nights when >= 2
    out["g6n5"] = g["_day"].transform(lambda s: _prior_in_window(s, 5))  # 4-in-6 nights when >= 3
    out["streak"] = g["is_home"].transform(_streak)
    prev = g["venue"].shift(1).fillna(tg["team"])  # a season opener starts from home
    lat = lambda v, i: v.map(lambda a: ARENAS[a][i]).astype(float)
    out["travel"] = haversine_km(lat(prev, 0), lat(prev, 1), lat(tg["venue"], 0), lat(tg["venue"], 1)) / 1000
    delta = lat(tg["venue"], 3) - lat(prev, 3)  # + = travelled east
    out["tz_east"], out["tz_west"] = delta.clip(lower=0), (-delta).clip(lower=0)
    return out


def candidate_features(games: pd.DataFrame) -> pd.DataFrame:
    """One row per game: every factor in ALL_FEATURES plus prior-game counts, home_win and margin."""
    pre = team_pregame(team_games(games))
    h = pre[pre["is_home"]].set_index("GAME_ID")
    a = pre[~pre["is_home"]].set_index("GAME_ID")
    gi = games.set_index("GAME_ID")
    out = gi[["SEASON", "GAME_DATE", "home_team", "away_team"]].copy()
    out["home_win"] = gi["home_win"]
    out["margin"] = gi["home_PTS"] - gi["away_PTS"]
    out["home_prior"], out["away_prior"] = h["prior_games"], a["prior_games"]
    elo = elo_pregame(games)
    out["elo_diff"] = elo["elo_home"] - elo["elo_away"]
    for c in RAW_MEANS:
        out[f"d_{c}"] = h[f"pre_{c}"] - a[f"pre_{c}"]
    out["d_form10"] = h["pre_form10"] - a["pre_form10"]
    for hl in EWM_HALFLIVES:
        out[f"d_ewm{hl}"] = h[f"pre_ewm{hl}"] - a[f"pre_ewm{hl}"]
    out["d_luck"] = h["pre_luck"] - a["pre_luck"]
    out["d_close_net"] = h["pre_close_net"] - a["pre_close_net"]
    out["d_rest"] = h["rest_days"] - a["rest_days"]
    for side, t in (("home", h), ("away", a)):
        out[f"{side}_b2b"] = (t["rest_days"] == 1).astype(int)
        out[f"{side}_g4n3"], out[f"{side}_g6n5"], out[f"{side}_streak"] = t["g4n3"], t["g6n5"], t["streak"]
        out[f"{side}_travel"], out[f"{side}_tz_east"], out[f"{side}_tz_west"] = t["travel"], t["tz_east"], t["tz_west"]
    alt = lambda col: out[col].map(lambda t: ARENAS[t][2] / 1000)
    out["home_alt_km"] = alt("home_team") * 0.3048  # km
    out["d_alt"] = (alt("home_team") - alt("away_team")) * 0.3048
    out["vol_sum"] = h["pre_sd_net"] + a["pre_sd_net"]
    out["fav_x_vol"] = out["elo_diff"] * out["vol_sum"]
    out["pace_sum"] = h["pre_pace"] + a["pre_pace"]  # raw level drifts with era: diagnostic only, not a model factor
    # league-wide state over the previous 1000 games (about a third of a season), known at tipoff
    chrono = out.sort_values("GAME_DATE", kind="stable")
    # take each date's first value so same-day games (tipping off at different hours) never inform each other
    roll = lambda s: s.shift(1).rolling(1000, min_periods=20).mean().groupby(chrono["GAME_DATE"]).transform("first")
    out["league_home_rate"] = roll(chrono["home_win"]).reindex(out.index).fillna(0.6)
    out["pace_sum_rel"] = out["pace_sum"] - roll(chrono["pace_sum"]).reindex(out.index).fillna(out["pace_sum"].mean())
    out["abs_d_pace"] = out["d_pace"].abs()
    span = out.groupby("SEASON")["GAME_DATE"].transform(lambda s: (s - s.min()).dt.days / max((s.max() - s.min()).days, 1))
    out["season_day"] = span
    out["is_weekend"] = (out["GAME_DATE"].dt.day_of_week >= 5).astype(int)
    pair = out["SEASON"] + np.where(out["home_team"] < out["away_team"], out["home_team"] + out["away_team"],
                                    out["away_team"] + out["home_team"])
    out["rematch_n"] = out.assign(_k=pair).sort_values("GAME_DATE").groupby("_k").cumcount().reindex(out.index)
    return out.reset_index()


def model_rows(cand: pd.DataFrame) -> pd.DataFrame:
    """Games where both teams have enough history, with every factor present."""
    rows = cand[(cand["home_prior"] >= MIN_PRIOR_GAMES) & (cand["away_prior"] >= MIN_PRIOR_GAMES)].reset_index(drop=True)
    missing = rows[ALL_FEATURES].isna().sum()
    assert not missing.any(), f"unexpected NaNs: {missing[missing > 0].to_dict()}"
    return rows
