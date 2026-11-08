"""Data for the interactive dashboard: every team-season from 2000-01 to 2025-26.

Writes results/dashboard.json (per season: league pulse, each factor's correlation with winning, every team's
factor values). No model fitting beyond Elo, so it runs in about a minute:  uv run python -m nbawin.dashboard
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nbawin import style
from nbawin.data import load_team_logs, to_games
from nbawin.factors import elo_pregame

OUT = Path(__file__).resolve().parent.parent / "results" / "dashboard.json"
SCATTER = ["fg3a_rate", "fg3_pct", "corner3_share", "rim_share", "mid_share", "pace", "efg", "opp_efg", "tov_rate",
           "oreb_pct", "ft_rate", "ast_pct", "drives_100", "drive_fg", "cs_share", "opp_rim_fg", "deflections_100", "speed_def"]
r4 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 4)
# Eight four-factor rates, offence then defence; each regression weight turns a team's gap to its season's league into net-rating points
FF = {"o_shoot": "ff_EFG_PCT", "o_tov": "ff_TM_TOV_PCT", "o_reb": "ff_OREB_PCT", "o_ft": "ff_FTA_RATE",
      "d_shoot": "ff_OPP_EFG_PCT", "d_tov": "ff_OPP_TOV_PCT", "d_reb": "ff_OPP_OREB_PCT", "d_ft": "ff_OPP_FTA_RATE"}
METRICS = Path(__file__).resolve().parent.parent / "results" / "metrics.json"


def six_factors(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per team-season: points per 100 from each factor (positive helps), residual, and 3P luck. Returns (table, fit summary)."""
    season = raw["SEASON"]
    dev = pd.DataFrame({k: raw[c] - raw[c].groupby(season).transform("mean") for k, c in FF.items()})
    net = raw["adv_NET_RATING"] - raw["adv_NET_RATING"].groupby(season).transform("mean")
    coef, *_ = np.linalg.lstsq(dev.to_numpy(), net.to_numpy(), rcond=None)
    out = dev * coef
    out["resid"] = net - out.sum(axis=1)
    r2 = 1 - (out["resid"] ** 2).sum() / (net ** 2).sum()

    # 3P luck: shrink observed 3P% toward the league by its measured full-season reliability; the rest is luck, in points per 100
    rel = {p["stat"]: p["split_half"] for p in json.loads(METRICS.read_text())["explore"]["persistence"]}
    poss_pg = raw["adv_POSS"] / raw["GP"]
    o3a, o3m = raw["opp_OPP_FG3A"], raw["opp_OPP_FG3A"] * raw["opp_OPP_FG3_PCT"]  # per game
    lg = o3m.groupby(season).transform("sum") / o3a.groupby(season).transform("sum")  # every team's allowed threes are some team's own threes
    # own threes per game, from shares rather than the zone table, whose per-game makes are rounded to 0.1
    fga = sum(raw[f"zone_{z}_FGA"] for z in ["RestrictedArea", "InThePaintNonRA", "MidRange", "LeftCorner3", "RightCorner3", "AbovetheBreak3", "Backcourt"])
    a3, m3 = raw["score_PCT_FGA_3PT"] * fga, raw["score_PCT_PTS_3PT"] * raw["adv_OFF_RATING"] * poss_pg / 100 / 3
    own_pct, own_100 = m3 / a3, a3 / poss_pg * 100
    out["luck_o"] = (1 - rel["fg3_pct"]) * (own_pct - lg) * own_100 * 3
    out["luck_d"] = -(1 - rel["def_fg3_pct"]) * (raw["opp_OPP_FG3_PCT"] - lg) * (o3a / poss_pg * 100) * 3  # opponents hitting more is bad luck
    out["luck"] = out["luck_o"] + out["luck_d"]
    win_slope = np.polyfit(raw["adv_NET_RATING"], raw["W_PCT"], 1)[0]
    fit = {"coef": {k: round(float(c), 3) for k, c in zip(FF, coef)}, "r2": round(float(r2), 4), "n": int(len(raw)),
           "rel_off": round(rel["fg3_pct"], 3), "rel_def": round(rel["def_fg3_pct"], 3), "win_per_point": round(float(win_slope), 5)}
    return out, fit


def main() -> dict:
    logs = load_team_logs()
    games = to_games(logs)
    elo = elo_pregame(games)
    abbr = logs.drop_duplicates(["SEASON", "TEAM_ID"]).set_index(["SEASON", "TEAM_ID"])["TEAM_ABBREVIATION"]

    raw = style.load()
    meta, X = style.build(raw)
    meta["abbr"] = [abbr.get((s, t), "") for s, t in zip(raw["SEASON"], raw["TEAM_ID"])]
    Z = style.zscore(X, meta["SEASON"])
    yz = style.zscore(meta[["win"]], meta["SEASON"])["win"]
    atlas, _ = style.atlas(meta, Z, n_boot=300, n_perm=1000)
    six, six_fit = six_factors(raw)
    SIX = list(FF) + ["resid", "luck"]

    home = games.groupby("SEASON")["home_win"].mean()
    fav = games.join(elo, on="GAME_ID")
    fav = ((fav["elo_home"] + 100 > fav["elo_away"]) == (fav["home_win"] == 1)).groupby(fav["SEASON"]).mean()
    by_season = {}
    for s, idx in meta.groupby("SEASON").groups.items():
        m, x, z = meta.loc[idx], X.loc[idx], Z.loc[idx]
        r = z.mul(yz[idx], axis=0).mean()  # within-season z-scores (ddof 0): the mean product is Pearson's r
        by_season[s] = {
            "kpi": {"fg3a_rate": r4(x["fg3a_rate"].mean()), "pace": r4(x["pace"].mean()), "efg": r4(x["efg"].mean()),
                    "rim_share": r4(x["rim_share"].mean()), "mid_share": r4(x["mid_share"].mean()), "home_win": r4(home.get(s)),
                    "favourite_win": r4(fav.get(s)), "parity_sd": r4(m["win"].std()), "games": int((games["SEASON"] == s).sum())},
            "r": {k: r4(v) for k, v in r.items() if z[k].notna().all()},
            "teams": [{"t": a, "n": n, "w": r4(wp), "net": r4(nt), "f": {k: r4(x.at[i, k]) for k in SCATTER},
                       "six": [r4(six.at[i, k]) for k in SIX]}
                      for i, a, n, wp, nt in zip(idx, m["abbr"], m["TEAM_NAME"], m["win"], m["net"])],
        }
    out = {"seasons": sorted(by_season), "scatter": SCATTER, "by_season": by_season, "six_keys": SIX, "six_fit": six_fit,
           "factors": {r["key"]: {k: r[k] for k in ("label", "family", "role", "definition", "r_win", "ci_low", "ci_high",
                                                     "chance_ceiling", "beats_chance")} for r in atlas}}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    return out


if __name__ == "__main__":
    d = main()
    print(OUT, f"{OUT.stat().st_size / 1e3:.0f} kB;", len(d["seasons"]), "seasons")
