"""Team-season factor atlas: ~110 descriptive metrics (shot diet, shot making, drives, passing, rebounding,
defence, hustle) tested against winning.

Question: is winning explained by style (how a team chooses to play) or by execution (how well the shots go
in and the ball stays safe)? Every metric is z-scored within its season, so league-wide trends (the three-point
boom, pace) cannot masquerade as signal. These are explanations of a finished season, not pre-game predictors.
Seasons, not teams, are the unit of resampling: the 30 teams of one season are not independent of each other.
"""

import glob

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV

from nbawin.data import RAW_DIR

TRACKING_ERA = "2016-17"  # first season with every tracking and hustle table; earlier tracking starts 2013-14
ALPHAS = np.logspace(-1, 3.5, 20)
P = lambda c: (lambda d: d[c])
R100 = lambda c: (lambda d: 100 * d[c] / d["adv_POSS"])  # per 100 team possessions, so pace cannot inflate counts
SHARE = lambda c: (lambda d: d[c] / d["_fga"])  # share of all field-goal attempts
OPP = lambda c: (lambda d: d[c] / d["opp_OPP_FGA"])

# key, label, family, role, definition, function of the merged frame
SPECS = [
    ("fg3a_rate", "3-point attempt rate", "Shot diet", "style", "Share of field-goal attempts that are threes", P("score_PCT_FGA_3PT")),
    ("fg3a_100", "3PA per 100 possessions", "Shot diet", "style", "Three-point attempts per 100 possessions", lambda d: 100 * d["_fg3a"] / d["adv_POSS"]),
    ("rim_share", "Rim attempt share", "Shot diet", "style", "Share of attempts in the restricted area", SHARE("zone_RestrictedArea_FGA")),
    ("paint_share", "Paint (non-rim) share", "Shot diet", "style", "Share of attempts in the paint outside the restricted area", SHARE("zone_InThePaintNonRA_FGA")),
    ("mid_share", "Mid-range share", "Shot diet", "style", "Share of attempts from mid-range", SHARE("zone_MidRange_FGA")),
    ("corner3_share", "Corner-three share", "Shot diet", "style", "Share of attempts from the corners beyond the arc", SHARE("zone_Corner3_FGA")),
    ("atb3_share", "Above-the-break three share", "Shot diet", "style", "Share of attempts from three above the break", SHARE("zone_AbovetheBreak3_FGA")),
    ("pace", "Pace", "Shot diet", "style", "Possessions per 48 minutes", P("adv_PACE")),
    ("cs_share", "Catch-and-shoot share", "Shot diet", "style", "Share of attempts taken off a pass without dribbling", SHARE("cs_CATCH_SHOOT_FGA")),
    ("pu_share", "Pull-up share", "Shot diet", "style", "Share of attempts taken off the dribble", SHARE("pu_PULL_UP_FGA")),
    ("drive_fga_share", "Drive attempt share", "Shot diet", "style", "Share of attempts that end a drive", SHARE("drv_DRIVE_FGA")),
    ("efg", "Effective FG%", "Shot making", "execution", "Field goals, with threes weighted 1.5", P("ff_EFG_PCT")),
    ("ts", "True shooting %", "Shot making", "execution", "Points per shooting possession, including free throws", P("adv_TS_PCT")),
    ("fg3_pct", "3-point %", "Shot making", "execution", "Three-point percentage", lambda d: d["_fg3m"] / d["_fg3a"]),
    ("rim_fg", "Rim FG%", "Shot making", "execution", "Field-goal % in the restricted area", P("zone_RestrictedArea_FG_PCT")),
    ("paint_fg", "Paint (non-rim) FG%", "Shot making", "execution", "Field-goal % in the paint outside the restricted area", P("zone_InThePaintNonRA_FG_PCT")),
    ("mid_fg", "Mid-range FG%", "Shot making", "execution", "Field-goal % from mid-range", P("zone_MidRange_FG_PCT")),
    ("corner3_fg", "Corner three %", "Shot making", "execution", "Three-point % from the corners", P("zone_Corner3_FG_PCT")),
    ("atb3_fg", "Above-the-break three %", "Shot making", "execution", "Three-point % above the break", P("zone_AbovetheBreak3_FG_PCT")),
    ("cs_efg", "Catch-and-shoot eFG%", "Shot making", "execution", "Effective FG% on catch-and-shoot attempts", P("cs_CATCH_SHOOT_EFG_PCT")),
    ("pu_efg", "Pull-up eFG%", "Shot making", "execution", "Effective FG% on pull-up attempts", P("pu_PULL_UP_EFG_PCT")),
    ("drive_fg", "Drive FG%", "Shot making", "execution", "Field-goal % on drives", P("drv_DRIVE_FG_PCT")),
    ("paint_touch_fg", "Paint-touch FG%", "Shot making", "execution", "Field-goal % after a touch in the paint", P("paint_PAINT_TOUCH_FG_PCT")),
    ("post_touch_fg", "Post-up FG%", "Shot making", "execution", "Field-goal % after a post touch", P("post_POST_TOUCH_FG_PCT")),
    ("elbow_touch_fg", "Elbow-touch FG%", "Shot making", "execution", "Field-goal % after an elbow touch", P("elbow_ELBOW_TOUCH_FG_PCT")),
    ("ast_pct", "Assist %", "Ball movement", "execution", "Share of made field goals that were assisted (needs a made shot)", P("adv_AST_PCT")),
    ("ast_ratio", "Assist ratio", "Ball movement", "execution", "Assists per 100 possessions", P("adv_AST_RATIO")),
    ("ast_3pm", "Assisted share of threes", "Ball movement", "execution", "Share of made threes that were assisted", P("score_PCT_AST_3PM")),
    ("ast_2pm", "Assisted share of twos", "Ball movement", "execution", "Share of made twos that were assisted", P("score_PCT_AST_2PM")),
    ("passes_100", "Passes per 100", "Ball movement", "style", "Passes made per 100 possessions", R100("pass_PASSES_MADE")),
    ("potential_ast_100", "Potential assists per 100", "Ball movement", "style", "Passes that led directly to a shot, per 100 possessions", R100("pass_POTENTIAL_AST")),
    ("ast_pts_100", "Points created by assists per 100", "Ball movement", "execution", "Points off assisted baskets, per 100 possessions", R100("pass_AST_POINTS_CREATED")),
    ("touches_100", "Touches per 100", "Ball movement", "style", "Times a player held the ball, per 100 possessions", R100("poss_TOUCHES")),
    ("sec_per_touch", "Seconds per touch", "Ball movement", "style", "Average time a player holds the ball", P("poss_AVG_SEC_PER_TOUCH")),
    ("drib_per_touch", "Dribbles per touch", "Ball movement", "style", "Average dribbles before passing or shooting", P("poss_AVG_DRIB_PER_TOUCH")),
    ("time_of_poss", "Time of possession", "Ball movement", "style", "Minutes per game the team's players hold the ball", P("poss_TIME_OF_POSS")),
    ("drives_100", "Drives per 100", "Attacking the paint", "style", "Drives to the basket per 100 possessions", R100("drv_DRIVES")),
    ("drive_pass_pct", "Drive pass %", "Attacking the paint", "style", "Share of drives that end in a pass", P("drv_DRIVE_PASSES_PCT")),
    ("drive_pts_per", "Points per drive", "Attacking the paint", "execution", "Points the driver scores per drive, shots and free throws", P("drv_DRIVE_PTS_PCT")),
    ("drive_pf_pct", "Drive foul %", "Attacking the paint", "style", "Share of drives that draw a foul", P("drv_DRIVE_PF_PCT")),
    ("paint_touches_100", "Paint touches per 100", "Attacking the paint", "style", "Touches inside the paint per 100 possessions", R100("poss_PAINT_TOUCHES")),
    ("post_touches_100", "Post touches per 100", "Attacking the paint", "style", "Post-up touches per 100 possessions", R100("poss_POST_TOUCHES")),
    ("elbow_touches_100", "Elbow touches per 100", "Attacking the paint", "style", "Touches at the elbow per 100 possessions", R100("poss_ELBOW_TOUCHES")),
    ("pts_per_paint_touch", "Points per paint touch", "Attacking the paint", "execution", "Points scored per touch inside the paint", P("poss_PTS_PER_PAINT_TOUCH")),
    ("tov_rate", "Turnover %", "Ball security", "execution", "Turnovers per 100 plays (lower is better)", P("ff_TM_TOV_PCT")),
    ("ast_to", "Assist-to-turnover", "Ball security", "execution", "Assists per turnover", P("adv_AST_TO")),
    ("drive_tov_pct", "Drive turnover %", "Ball security", "execution", "Share of drives that end in a turnover", P("drv_DRIVE_TOV_PCT")),
    ("paint_touch_tov", "Paint-touch turnover %", "Ball security", "execution", "Share of paint touches that end in a turnover", P("paint_PAINT_TOUCH_TOV_PCT")),
    ("oreb_pct", "Offensive rebound %", "Rebounding", "execution", "Share of own misses recovered", P("ff_OREB_PCT")),
    ("dreb_pct", "Defensive rebound %", "Rebounding", "execution", "Share of opponent misses recovered", P("adv_DREB_PCT")),
    ("reb_pct", "Total rebound %", "Rebounding", "execution", "Share of all available rebounds", P("adv_REB_PCT")),
    ("oreb_chance_pct", "Offensive rebound chance %", "Rebounding", "execution", "Share of offensive rebound chances converted", P("reb_OREB_CHANCE_PCT")),
    ("dreb_chance_pct", "Defensive rebound chance %", "Rebounding", "execution", "Share of defensive rebound chances converted", P("reb_DREB_CHANCE_PCT")),
    ("oreb_contest_pct", "Contested offensive rebound %", "Rebounding", "style", "Share of offensive rebounds that were contested", P("reb_OREB_CONTEST_PCT")),
    ("ft_rate", "Free-throw rate", "Free throws", "execution", "Free-throw attempts per field-goal attempt", P("ff_FTA_RATE")),
    ("opp_ft_rate", "Opponent free-throw rate", "Free throws", "execution", "Free-throw attempts the defence allows per field-goal attempt", P("ff_OPP_FTA_RATE")),
    ("opp_efg", "Opponent eFG%", "Defence", "execution", "Effective FG% the defence allows", P("ff_OPP_EFG_PCT")),
    ("opp_tov", "Opponent turnover %", "Defence", "execution", "Turnovers the defence forces per 100 plays", P("ff_OPP_TOV_PCT")),
    ("opp_oreb", "Opponent offensive rebound %", "Defence", "execution", "Share of the opponent's own misses that the opponent rebounds", P("ff_OPP_OREB_PCT")),
    ("opp_fg3a_rate", "Opponent 3-point attempt rate", "Defence", "style", "Share of opponent attempts that are threes", OPP("opp_OPP_FG3A")),
    ("opp_fg3_pct", "Opponent 3-point %", "Defence", "execution", "Three-point % the defence allows", P("opp_OPP_FG3_PCT")),
    ("opp_rim_faced", "Rim attempts faced per 100", "Defence", "style", "Opponent rim attempts per 100 possessions", R100("def_DEF_RIM_FGA")),
    ("opp_rim_fg", "Opponent rim FG%", "Defence", "execution", "Field-goal % allowed at the rim (rim protection)", P("def_DEF_RIM_FG_PCT")),
    ("stl_100", "Steals per 100", "Defence", "execution", "Steals per 100 possessions", R100("def_STL")),
    ("blk_100", "Blocks per 100", "Defence", "execution", "Blocks per 100 possessions", R100("def_BLK")),
    ("opp_paint_pts_100", "Opponent paint points per 100", "Defence", "execution", "Points in the paint allowed per 100 possessions", R100("misc_OPP_PTS_PAINT")),
    ("opp_fb_pts_100", "Opponent fast-break points per 100", "Defence", "execution", "Fast-break points allowed per 100 possessions", R100("misc_OPP_PTS_FB")),
    ("opp_tov_pts_100", "Opponent points off turnovers per 100", "Defence", "execution", "Points allowed off turnovers per 100 possessions", R100("misc_OPP_PTS_OFF_TOV")),
    ("opp_2nd_pts_100", "Opponent second-chance points per 100", "Defence", "execution", "Second-chance points allowed per 100 possessions", R100("misc_OPP_PTS_2ND_CHANCE")),
    ("pts_fb_pct", "Fast-break share of points", "Where points come from", "execution", "Share of points scored on the break", P("score_PCT_PTS_FB")),
    ("pts_tov_pct", "Turnover share of points", "Where points come from", "execution", "Share of points scored off turnovers", P("score_PCT_PTS_OFF_TOV")),
    ("pts_paint_pct", "Paint share of points", "Where points come from", "execution", "Share of points scored in the paint", P("score_PCT_PTS_PAINT")),
    ("pts_ft_pct", "Free-throw share of points", "Where points come from", "execution", "Share of points from the line", P("score_PCT_PTS_FT")),
    ("pts_3_pct", "Three-point share of points", "Where points come from", "execution", "Share of points from threes", P("score_PCT_PTS_3PT")),
    ("pts_mid_pct", "Mid-range share of points", "Where points come from", "execution", "Share of points from mid-range twos", P("score_PCT_PTS_2PT_MR")),
    ("pts_2nd_100", "Second-chance points per 100", "Where points come from", "execution", "Second-chance points per 100 possessions", R100("misc_PTS_2ND_CHANCE")),
    ("pts_fb_100", "Fast-break points per 100", "Where points come from", "execution", "Fast-break points per 100 possessions", R100("misc_PTS_FB")),
    ("speed_off", "Offensive speed", "Effort and movement", "effort", "Average speed on offence, mph", P("speed_AVG_SPEED_OFF")),
    ("speed_def", "Defensive speed", "Effort and movement", "effort", "Average speed on defence, mph", P("speed_AVG_SPEED_DEF")),
    ("miles_100", "Miles run per 100", "Effort and movement", "effort", "Distance covered per 100 possessions", R100("speed_DIST_MILES")),
    ("deflections_100", "Deflections per 100", "Effort and movement", "effort", "Passes and dribbles touched on defence", R100("hus_DEFLECTIONS")),
    ("contested_100", "Contested shots per 100", "Effort and movement", "effort", "Opponent shots with a defender in range", R100("hus_CONTESTED_SHOTS")),
    ("charges_100", "Charges drawn per 100", "Effort and movement", "effort", "Offensive fouls drawn", R100("hus_CHARGES_DRAWN")),
    ("screen_ast_100", "Screen assists per 100", "Effort and movement", "effort", "Screens that led to a made basket", R100("hus_SCREEN_ASSISTS")),
    ("loose_balls_100", "Loose balls recovered per 100", "Effort and movement", "effort", "Loose balls won", R100("hus_LOOSE_BALLS_RECOVERED")),
    ("box_outs_100", "Box-outs per 100", "Effort and movement", "effort", "Box-outs, offence and defence", R100("hus_BOX_OUTS")),
]
META = {k: dict(label=l, family=f, role=r, definition=d) for k, l, f, r, d, _ in SPECS}
assert len(META) == len(SPECS), "duplicate metric key"
TARGETS = {"win": "W_PCT", "net": "adv_NET_RATING", "off": "adv_OFF_RATING", "def": "adv_DEF_RATING"}
EDGE_KEYS = ["fg3a_rate", "rim_share", "mid_share", "pace", "ast_pct", "drives_100"]


def load() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_DIR / "teamseason_*.csv")))
    assert files, "run scripts/fetch_teamseason.py first"
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def build(raw: pd.DataFrame):
    """(meta, X): outcomes per team-season, and every metric as a raw value."""
    d = raw.copy()
    zone = lambda z, s: d[f"zone_{z}_{s}"]
    zs = ["RestrictedArea", "InThePaintNonRA", "MidRange", "LeftCorner3", "RightCorner3", "AbovetheBreak3", "Backcourt"]
    d["_fga"] = sum(zone(z, "FGA") for z in zs)
    d["_fg3a"], d["_fg3m"] = zone("Corner3", "FGA") + zone("AbovetheBreak3", "FGA"), zone("Corner3", "FGM") + zone("AbovetheBreak3", "FGM")
    X = pd.DataFrame({k: fn(d) for k, *_, fn in SPECS}).replace([np.inf, -np.inf], np.nan)
    meta = d[["SEASON", "TEAM_NAME"]].assign(**{k: d[c] for k, c in TARGETS.items()})
    meta["def"] = -meta["def"]  # so that higher is better for every target
    return meta, X


def zscore(df: pd.DataFrame, season: pd.Series) -> pd.DataFrame:
    g = df.groupby(season)
    return (df - g.transform("mean")) / g.transform("std", ddof=0).replace(0, np.nan)


def _season_sums(Z0, M, y, seasons):
    """Per-season sums of x*y, x^2 and y^2 (over rows where the metric exists): enough to rebuild any correlation."""
    idx = {s: np.flatnonzero(seasons == s) for s in np.unique(seasons)}
    sxy = np.array([Z0[i].T @ y[i] for i in idx.values()])
    sxx = np.array([(Z0[i] ** 2).sum(0) for i in idx.values()])
    syy = np.array([M[i].T @ (y[i] ** 2) for i in idx.values()])
    return sxy, sxx, syy, [len(i) for i in idx.values()]


def atlas(meta, Z, n_boot=1000, n_perm=1000, seed=0):
    """Correlation of every metric with win % (within-season), a season-resampled 95% CI, and a chance ceiling.

    The ceiling is the 95th percentile of the largest |t| any metric reaches when win % is shuffled inside each season,
    converted back to a correlation for each metric's own sample size: a metric under it is indistinguishable from the
    best of a hundred coin-flip metrics.
    """
    rng = np.random.default_rng(seed)
    seasons = meta["SEASON"].to_numpy()
    y = zscore(meta[["win"]], meta["SEASON"])["win"].to_numpy()
    M = Z.notna().to_numpy().astype(float)
    Z0 = np.nan_to_num(Z.to_numpy())
    sxy, sxx, syy, _ = _season_sums(Z0, M, y, seasons)
    r = sxy.sum(0) / np.sqrt(sxx.sum(0) * syy.sum(0))
    w = rng.multinomial(len(sxy), np.ones(len(sxy)) / len(sxy), size=n_boot)  # season draws with replacement
    rb = (w @ sxy) / np.sqrt((w @ sxx) * (w @ syy))
    lo, hi = np.nanquantile(rb, 0.025, axis=0), np.nanquantile(rb, 0.975, axis=0)
    n = M.sum(0)
    yp = np.empty((len(y), n_perm))
    for s in np.unique(seasons):
        i = np.flatnonzero(seasons == s)
        yp[i] = np.array([rng.permutation(y[i]) for _ in range(n_perm)]).T
    t = (Z0.T @ yp) / np.sqrt(sxx.sum(0) * syy.sum(0))[:, None] * np.sqrt(n)[:, None]  # r * sqrt(n) under the null
    t_crit = float(np.quantile(np.abs(t).max(0), 0.95))
    ceiling = t_crit / np.sqrt(n)
    rn = Z.corrwith(zscore(meta[["net"]], meta["SEASON"])["net"]).to_numpy()
    first = [meta.loc[Z[c].notna(), "SEASON"].min() for c in Z]
    rows = [{"key": c, **META[c], "n": int(n[i]), "first_season": first[i], "r_win": float(r[i]), "ci_low": float(lo[i]),
             "ci_high": float(hi[i]), "r_net": float(rn[i]), "chance_ceiling": float(ceiling[i]),
             "beats_chance": bool(abs(r[i]) > ceiling[i])} for i, c in enumerate(Z)]
    return sorted(rows, key=lambda x: -abs(x["r_win"])), t_crit


def _loso(Z, y, seasons, partial=None):
    """Leave-one-season-out ridge: per-season (SSE, SST) so R^2 and a season-resampled CI come from the same sums.

    With `partial`, the model explains what is left of y after the fold's own regression on that column.
    """
    sse, sst = [], []
    for s in np.unique(seasons):
        te = seasons == s
        yt, ye = y[~te], y[te]
        if partial is not None:
            b = (partial[~te] @ yt) / (partial[~te] @ partial[~te])
            yt, ye = yt - b * partial[~te], ye - b * partial[te]
        m = RidgeCV(alphas=ALPHAS).fit(Z[~te], yt)
        sse.append(((ye - m.predict(Z[te])) ** 2).sum())
        sst.append((ye**2).sum())
    return np.array(sse), np.array(sst)


def _r2(sse, sst, rng, n_boot=500):
    draws = rng.integers(0, len(sse), (n_boot, len(sse)))
    boot = 1 - sse[draws].sum(1) / sst[draws].sum(1)
    return {"r2": float(1 - sse.sum() / sst.sum()), "ci": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}


def blocks(meta, Z, keys, seed=0):
    """Which kind of factor explains winning? Cross-validated R^2 of win %, offence and defence from each block."""
    rng = np.random.default_rng(seed)
    seasons = meta["SEASON"].to_numpy()
    Y = zscore(meta[list(TARGETS)], meta["SEASON"])
    role = lambda *rs: [k for k in keys if META[k]["role"] in rs]
    sets = {"Style (choices)": role("style"), "Execution (results)": role("execution"), "Effort (hustle, speed)": role("effort"),
            "Style + effort": role("style", "effort") if role("effort") else [], "Everything": keys}
    out = {"n_rows": len(Z), "n_seasons": int(len(np.unique(seasons))), "sets": {}, "beyond_net_rating": {}, "families": []}
    for name, ks in sets.items():
        if not ks:
            continue
        out["sets"][name] = {"n_metrics": len(ks), **{t: _r2(*_loso(Z[ks].to_numpy(), Y[t].to_numpy(), seasons), rng) for t in ("win", "off", "def")}}
    net = Y["net"].to_numpy()
    out["net_rating_alone"] = _r2(*_loso(net[:, None], Y["win"].to_numpy(), seasons), rng)
    for name in ("Style + effort", "Everything"):
        if sets[name]:
            out["beyond_net_rating"][name] = _r2(*_loso(Z[sets[name]].to_numpy(), Y["win"].to_numpy(), seasons, partial=net), rng)
    full = _r2(*_loso(Z[keys].to_numpy(), Y["win"].to_numpy(), seasons), rng)
    for fam in dict.fromkeys(META[k]["family"] for k in keys):
        fk = [k for k in keys if META[k]["family"] == fam]
        alone = _r2(*_loso(Z[fk].to_numpy(), Y["win"].to_numpy(), seasons), rng)
        sse, sst = _loso(Z[[k for k in keys if k not in fk]].to_numpy(), Y["win"].to_numpy(), seasons)
        out["families"].append({"family": fam, "n_metrics": len(fk), "alone_r2": alone,
                                "loss_if_removed": full["r2"] - _r2(sse, sst, rng)["r2"]})
    out["families"].sort(key=lambda f: -f["alone_r2"]["r2"])
    return out


def effective_dimension(Z):
    """How many independent signals hide in the metrics: components to reach 90% of variance, and the entropy-based rank."""
    ev = np.clip(np.linalg.eigvalsh(np.corrcoef(Z.to_numpy().T))[::-1], 0, None)
    p = ev / ev.sum()
    return {"n_metrics": Z.shape[1], "components_for_90pct": int(np.searchsorted(np.cumsum(p), 0.9) + 1),
            "effective_rank": float(np.exp(-(p[p > 0] * np.log(p[p > 0])).sum()))}


def edge_over_time(meta, Z):
    """Does a style choice pay off, and has that changed? Per-season r with net rating plus a 5-season pooled r."""
    net = zscore(meta[["net"]], meta["SEASON"])["net"]
    seasons = sorted(meta["SEASON"].unique())
    out = {}
    for k in EDGE_KEYS:
        ok = Z[k].notna()
        per = [{"season": s, "r": float(np.corrcoef(Z.loc[m, k], net[m])[0, 1])}
               for s in seasons if (m := (meta["SEASON"] == s) & ok).sum() > 5]
        roll = []
        for i in range(4, len(per)):
            win = [p["season"] for p in per[i - 4:i + 1]]
            m = meta["SEASON"].isin(win) & ok
            r, n = float(np.corrcoef(Z.loc[m, k], net[m])[0, 1]), int(m.sum())
            half = 1.96 / np.sqrt(n - 3)
            roll.append({"season": per[i]["season"], "r": r, "lo": float(np.tanh(np.arctanh(r) - half)),
                         "hi": float(np.tanh(np.arctanh(r) + half))})
        out[k] = {"label": META[k]["label"], "per_season": per, "rolling5": roll}
    return out


def drive_points(meta, Z, X):
    m = Z["drives_100"].notna()
    d = meta[m].assign(drives_z=Z.loc[m, "drives_100"], drive_fg=X.loc[m, "drive_fg"], drives_100=X.loc[m, "drives_100"])
    return [{"season": r.SEASON, "team": r.TEAM_NAME, "drives_z": round(float(r.drives_z), 3), "drive_fg": round(float(r.drive_fg), 3),
             "net": round(float(r.net), 2), "win": round(float(r.win), 3)} for r in d.itertuples()]


def analyze(seed=0):
    raw = load()
    meta, X = build(raw)
    Z = zscore(X, meta["SEASON"])
    box_keys = [k for k in Z if Z[k].notna().all()]  # present in all 26 seasons
    era = (meta["SEASON"] >= TRACKING_ERA).to_numpy()
    era_keys = [k for k in Z if Z.loc[era, k].notna().all()]
    at, t_crit = atlas(meta, Z, seed=seed)
    return {
        "n_team_seasons": len(meta), "n_seasons": int(meta["SEASON"].nunique()), "n_metrics": len(at), "chance_t_ceiling": t_crit,
        "tracking_era_from": TRACKING_ERA, "atlas": at,
        "blocks_all_seasons": blocks(meta, Z, box_keys, seed),
        "blocks_tracking_era": blocks(meta[era].reset_index(drop=True), Z[era].reset_index(drop=True), era_keys, seed),
        "dimension": effective_dimension(Z.loc[era, era_keys]),
        "edge": edge_over_time(meta, Z), "drives": drive_points(meta, Z, X),
    }


def report_lines(st: dict) -> list[str]:
    pct = lambda d: f"{d['r2']:.2f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}]"
    lines = ["", "## What separates winning teams: style or execution?", "",
             f"{st['n_metrics']} metrics for {st['n_team_seasons']} team-seasons ({st['n_seasons']} seasons), each z-scored within its season. "
             f"Shot-zone and advanced tables cover every season; tracking (drives, touches, catch-and-shoot) starts 2013-14 and hustle 2016-17. "
             "'Chance ceiling' is the correlation the best of all these metrics would reach by luck alone (win % shuffled within each season).", "",
             "| Metric | Family | Role | r with win % [95% CI, seasons resampled] | Chance ceiling | Beats chance |", "|---|---|---|---|---|---|"]
    for r in st["atlas"][:25]:
        lines.append(f"| {r['label']} | {r['family']} | {r['role']} | {r['r_win']:+.2f} [{r['ci_low']:+.2f}, {r['ci_high']:+.2f}] | {r['chance_ceiling']:.2f} | {'yes' if r['beats_chance'] else 'no'} |")
    for key, title in (("blocks_all_seasons", "All 26 seasons"), ("blocks_tracking_era", f"Tracking era ({st['tracking_era_from']} on)")):
        b = st[key]
        lines += ["", f"### {title}: cross-validated R-squared by factor block ({b['n_rows']} team-seasons, leave one season out)", "",
                  "| Block | Metrics | Win % | Offence | Defence |", "|---|---|---|---|---|"]
        lines += [f"| {n} | {s['n_metrics']} | {pct(s['win'])} | {pct(s['off'])} | {pct(s['def'])} |" for n, s in b["sets"].items()]
        lines += ["", f"Net rating alone explains {pct(b['net_rating_alone'])} of win %. Beyond net rating, everything else explains "
                  f"{pct(b['beyond_net_rating']['Everything'])} of what is left.", "",
                  "| Family | Metrics | Alone | Loss in R-squared if removed |", "|---|---|---|---|"]
        lines += [f"| {f['family']} | {f['n_metrics']} | {pct(f['alone_r2'])} | {f['loss_if_removed']:+.3f} |" for f in b["families"]]
    d = st["dimension"]
    lines += ["", f"Redundancy: {d['n_metrics']} tracking-era metrics carry about {d['effective_rank']:.0f} independent signals "
              f"({d['components_for_90pct']} principal components reach 90% of the variance)."]
    return lines
