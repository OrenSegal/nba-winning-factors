"""Wide factor screen plus targeted data catches. Everything here is pre-game or a descriptive audit.

analyze() returns one JSON-able dict that run.py merges into metrics.json under "explore".
"""

from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nbawin.factors import (ALL_FEATURES, DEFINITIONS, EWM_HALFLIVES, FAMILIES, FAMILY_OF, candidate_features, model_rows,
                            team_games)
from nbawin.teams import franchise

ERA = ["league_home_rate"]
BASE = ["elo_diff", "d_net_rtg"] + ERA  # the screen asks: what does a factor add beyond team strength and the era?
PERSISTENCE_STATS = {
    "net_rtg": "Net rating", "win": "Win %", "off_efg": "Offensive eFG%", "def_efg": "Opponent eFG% allowed",
    "off_tov_rate": "Turnover rate", "def_tov_rate": "Opponent turnovers forced", "off_orb_rate": "Offensive rebound rate",
    "def_orb_rate": "Opponent offensive rebounds allowed", "off_ft_rate": "Free-throw rate", "def_ft_rate": "Opponent free-throw rate allowed",
    "fg3a_rate": "Three-point attempt rate", "fg3_pct": "Three-point %", "def_fg3_pct": "Opponent three-point % allowed",
    "def_fg3a_rate": "Opponent three-point attempt rate", "ft_pct": "Free-throw %", "pace": "Pace",
    "ast_rate": "Assist rate", "stl_rate": "Steal rate", "blk_rate": "Block rate", "pf_rate": "Foul rate",
}
BUCKETS = [(0, 5, "games 1-5"), (5, 10, "6-10"), (10, 20, "11-20"), (20, 40, "21-40"), (40, 60, "41-60"), (60, 100, "61+")]


def _logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def _fit(train, test, cols, C=1.0):
    """Standardized logistic fit on train; returns (test probabilities, model)."""
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000)).fit(train[cols], train["home_win"])
    return m.predict_proba(test[cols])[:, 1], m


def _ci(delta, idx):
    boots = delta[idx].mean(axis=1)
    return float(delta.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def _clustered_p(delta, groups):
    """Two-sided normal p-value for mean(delta) with a standard error clustered on `groups` (game dates)."""
    sums = pd.Series(delta).groupby(np.asarray(groups)).sum().to_numpy()
    g = len(sums)
    se = np.sqrt(g / (g - 1) * ((sums - sums.mean()) ** 2).sum()) / len(delta)
    return float(2 * (1 - NormalDist().cdf(abs(delta.mean() / se))))


def _holm(ps):
    """Holm step-down adjusted p-values, in the input order."""
    adj, running = [0.0] * len(ps), 0.0
    for rank, j in enumerate(np.argsort(ps)):
        running = max(running, min(1.0, (len(ps) - rank) * ps[j]))
        adj[j] = running
    return adj


def _wald_last(train, cols):
    """Coefficient, 95% CI and z for the last column of an (almost) unpenalized standardized logistic fit."""
    p, m = _fit(train, train, cols, C=1e6)
    X = m[0].transform(train[cols])
    Xd = np.c_[np.ones(len(X)), X]
    cov = np.linalg.inv((Xd * (p * (1 - p))[:, None]).T @ Xd)
    b, se = m[-1].coef_[0][-1], float(np.sqrt(cov[-1, -1]))
    return float(b), float(b - 1.96 * se), float(b + 1.96 * se), float(b / se)


def screen(train, test, idx):
    """Each factor added to team strength alone: in-sample Wald effect and out-of-sample log-loss change."""
    p0, _ = _fit(train, test, BASE)
    l0 = _logloss(test["home_win"].to_numpy(), p0)
    cands = [c for c in ALL_FEATURES if c not in BASE]
    assert "pace_sum" not in cands
    z_crit = NormalDist().inv_cdf(1 - 0.025 / len(cands))  # Bonferroni across every factor screened
    rows = []
    for c in cands:
        coef, lo, hi, z = _wald_last(train, BASE + [c])
        p, _ = _fit(train, test, BASE + [c])
        d, dlo, dhi = _ci(_logloss(test["home_win"].to_numpy(), p) - l0, idx)
        rows.append({"feature": c, "family": FAMILY_OF[c], "definition": DEFINITIONS[c], "coef": coef, "ci_low": lo, "ci_high": hi, "z": z,
                     "significant_after_bonferroni": bool(abs(z) > z_crit),
                     "d_logloss": d, "d_logloss_ci": [dlo, dhi]})
    return sorted(rows, key=lambda r: -abs(r["z"])), z_crit


def era_confound(train):
    """A factor can look real only because it tracks the era: pace_sum before and after controlling the home-court regime."""
    raw = _wald_last(train, ["elo_diff", "d_net_rtg", "pace_sum"])
    adj = _wald_last(train, ["elo_diff", "d_net_rtg", "league_home_rate", "pace_sum"])
    return {"factor": "pace_sum", "z_without_era_control": raw[3], "z_with_era_control": adj[3],
            "coef_without": raw[0], "coef_with": adj[0]}


def families(train, test, idx):
    """Family value two ways: gain over strength alone, and loss from removing it from the full model."""
    y = test["home_win"].to_numpy()
    full = [c for c in ALL_FEATURES]
    p_full, _ = _fit(train, test, full)
    l_full = _logloss(y, p_full)
    strength = FAMILIES["Strength"] + ERA
    p_str, _ = _fit(train, test, strength)
    l_str = _logloss(y, p_str)
    gb = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_depth=3, min_samples_leaf=50, random_state=0)
    gb.fit(train[full], train["home_win"])
    out = {"overall": {
        "strength_only_logloss": float(l_str.mean()), "full_logistic_logloss": float(l_full.mean()),
        "full_boosting_logloss": float(_logloss(y, gb.predict_proba(test[full])[:, 1]).mean()),
        "full_logistic_accuracy": float(((p_full >= 0.5) == y).mean()), "strength_only_accuracy": float(((p_str >= 0.5) == y).mean()),
        "n_factors": len(full)}, "families": []}
    for fam, cols in FAMILIES.items():
        row = {"family": fam, "n_factors": len(cols)}
        p_wo, _ = _fit(train, test, [c for c in full if c not in cols])
        row["loss_if_removed"] = _ci(_logloss(y, p_wo) - l_full, idx)  # > 0 means the family was helping
        if fam not in ("Strength", "Era regime"):
            p_add, _ = _fit(train, test, strength + cols)
            row["gain_over_strength"] = _ci(l_str - _logloss(y, p_add), idx)  # > 0 means it helps
            row["gain_p"] = _clustered_p(l_str - _logloss(y, p_add), test["GAME_DATE"])
        out["families"].append(row)
    tested = [r for r in out["families"] if "gain_p" in r]
    for r, p in zip(tested, _holm([r["gain_p"] for r in tested])):
        r["gain_p_holm"] = p  # corrected across the families tested against strength
    return out


def memory(rows):
    """Leave-one-season-out log loss of single-signal models: how many games of history should a team rating use?"""
    seasons = sorted(rows["SEASON"].unique())
    variants = [(f"d_ewm{h}", h) for h in EWM_HALFLIVES] + [("d_net_rtg", None), ("elo_diff", None)]
    out = []
    for col, h in variants:
        per_season = []
        for s in seasons:
            test = rows[rows["SEASON"] == s]
            p, _ = _fit(rows[rows["SEASON"] != s], test, [col])
            per_season.append(_logloss(test["home_win"].to_numpy(), p).mean())
        out.append({"signal": col, "halflife_games": h, "logloss": float(np.mean(per_season)),
                    "se": float(np.std(per_season, ddof=1) / np.sqrt(len(per_season)))})
    return out


def persistence(tg):
    """How much of a team stat in one season is skill? Split-half (odd vs even games) and year-over-year correlation."""
    tg = tg.sort_values(["SEASON", "team", "GAME_DATE", "GAME_ID"])
    tg["half"] = tg.groupby(["SEASON", "team"]).cumcount() % 2
    out = []
    for c, label in PERSISTENCE_STATS.items():
        halves = tg.groupby(["SEASON", "team", "half"])[c].mean().unstack()
        r = halves.corr().iloc[0, 1]
        means = tg.groupby(["fr", "SEASON"])[c].mean().unstack()
        cols = list(means.columns)
        pairs = pd.concat([pd.DataFrame({"a": means[a], "b": means[b]}) for a, b in zip(cols[:-1], cols[1:])]).dropna()
        out.append({"stat": c, "label": label, "split_half": float(2 * r / (1 + r)), "year_over_year": float(pairs.corr().iloc[0, 1])})
    return sorted(out, key=lambda r: -r["split_half"])


def early_season(cand, train_seasons_mask):
    """Accuracy by how many games the teams have played: Elo (remembers last season) vs this season's record."""
    c = cand.assign(d_net_rtg=cand["d_net_rtg"].fillna(0), min_prior=np.minimum(cand["home_prior"], cand["away_prior"]))
    train, test = c[train_seasons_mask(c)], c[~train_seasons_mask(c)]
    y = test["home_win"].to_numpy()
    p_elo, _ = _fit(train, test, ["elo_diff"])
    p_rec, _ = _fit(train, test, ["d_net_rtg"])
    p_home = np.full(len(test), train["home_win"].mean())
    out = []
    for lo, hi, label in BUCKETS:
        m = ((test["min_prior"] >= lo) & (test["min_prior"] < hi)).to_numpy()
        if m.sum() == 0:
            continue
        out.append({"bucket": label, "n_games": int(m.sum()),
                    "acc_home": float(((p_home[m] >= 0.5) == y[m]).mean()),
                    "acc_elo": float(((p_elo[m] >= 0.5) == y[m]).mean()), "acc_record": float(((p_rec[m] >= 0.5) == y[m]).mean()),
                    "ll_elo": float(_logloss(y[m], p_elo[m]).mean()), "ll_record": float(_logloss(y[m], p_rec[m]).mean())})
    return out


def team_home_court(cand):
    """Home-court value in points per franchise after controlling for Elo gap (OLS, margin ~ elo_diff + home team)."""
    d = cand[cand["SEASON"] >= "2001-02"].copy()
    d["fr"] = d["home_team"].map(franchise)
    X = pd.get_dummies(d["fr"]).astype(float)
    X.insert(0, "elo_diff", d["elo_diff"])
    A, y = X.to_numpy(), d["margin"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    cov = np.linalg.inv(A.T @ A) * (resid @ resid) / (len(y) - A.shape[1])
    n = d["fr"].value_counts()
    rows = [{"team": t, "hca": float(beta[i + 1]), "se": float(np.sqrt(cov[i + 1, i + 1])), "n_games": int(n[t])}
            for i, t in enumerate(X.columns[1:])]
    league = float(np.average([r["hca"] for r in rows], weights=[r["n_games"] for r in rows]))
    return {"league_avg_points": league, "teams": sorted(rows, key=lambda r: -r["hca"])}


def league_trends(tg, cand, rows):
    """How the game itself changed: pace, threes, rebounding, parity and how often the favorite wins."""
    by = tg.groupby("SEASON")
    t = pd.DataFrame({"pace": by["pace"].mean(), "fg3a_per_game": by["fg3a"].mean(), "fg3a_rate": by["fg3a_rate"].mean(),
                      "ppg": by["pts"].mean(), "efg": by["off_efg"].mean(), "tov_rate": by["off_tov_rate"].mean(),
                      "orb_rate": by["off_orb_rate"].mean(), "ft_rate": by["off_ft_rate"].mean()})
    t["parity_sd_win_pct"] = tg.groupby(["SEASON", "team"])["win"].mean().groupby("SEASON").std()
    t["home_win_rate"] = cand.groupby("SEASON")["home_win"].mean()
    t["favorite_win_rate"] = rows.assign(fav=(rows["elo_diff"] > 0) == (rows["home_win"] == 1)).groupby("SEASON")["fav"].mean()
    t["avg_abs_margin"] = cand.assign(a=cand["margin"].abs()).groupby("SEASON")["a"].mean()
    return t.reset_index().to_dict("records")


def calendar(rows, train_mask):
    """Home results vs what Elo expects, by weekday and month: a null-hunting audit."""
    p, _ = _fit(rows[train_mask], rows, ["elo_diff"])
    r = rows.assign(resid=rows["home_win"] - p)
    out = {}
    for key, name in (("weekday", r["GAME_DATE"].dt.day_name()), ("month", r["GAME_DATE"].dt.month_name())):
        g = r.groupby(name)["resid"].agg(["mean", "std", "count"])
        out[key] = [{"label": k, "mean_resid": float(v["mean"]), "se": float(v["std"] / np.sqrt(v["count"])), "n": int(v["count"])}
                    for k, v in g.iterrows()]
    return out


def analyze(games, test_seasons, seed=0, n_boot=500):
    cand = candidate_features(games)
    rows = model_rows(cand)
    test_mask = lambda df: df["SEASON"].isin(test_seasons)
    train, test = rows[~test_mask(rows)], rows[test_mask(rows)]
    idx = np.random.default_rng(seed).integers(0, len(test), (n_boot, len(test)))
    tg = team_games(games)
    scr, z_crit = screen(train, test, idx)
    return {
        "n_games": len(rows), "n_train": len(train), "n_test": len(test), "n_factors_screened": len(scr), "bonferroni_z": z_crit,
        "base": BASE, "screen": scr, "era_confound": era_confound(train), "families": families(train, test, idx), "memory": memory(rows),
        "persistence": persistence(tg), "early_season": early_season(cand, lambda df: ~test_mask(df)),
        "home_court": team_home_court(cand), "trends": league_trends(tg, cand, rows),
        "calendar": calendar(rows, ~test_mask(rows)),
    }


def report_lines(ex: dict) -> list[str]:
    """Markdown for the wide factor screen and the data catches."""
    f = lambda x, n=4: f"{x:+.{n}f}"
    ci = lambda t: f"{f(t[0])} [{f(t[1])}, {f(t[2])}]"
    lines = ["", "## Beyond the four factors: a wide factor screen", "",
             f"{ex['n_factors_screened']} candidate factors, each added to team strength (Elo, season-to-date net rating) and the "
             f"current home-court regime. Train {ex['n_train']} games, test {ex['n_test']}. 'z' is the in-sample Wald statistic "
             f"(Bonferroni threshold {ex['bonferroni_z']:.2f}); 'test log-loss change' is out of sample (negative = better), with a paired bootstrap CI.", "",
             "| Factor | Family | Effect per 1 SD (log-odds) | z | Test log-loss change [95% CI] |", "|---|---|---|---|---|"]
    for r in ex["screen"][:14]:
        lines.append(f"| {r['feature']} | {r['family']} | {r['coef']:+.3f} | {r['z']:+.1f}{'*' if r['significant_after_bonferroni'] else ''} | {ci([r['d_logloss'], *r['d_logloss_ci']])} |")
    e = ex["era_confound"]
    lines += ["", f"Era confound: raw league pace looks predictive (z {e['z_without_era_control']:+.1f}) but shrinks to z {e['z_with_era_control']:+.1f} once the "
              "home-court regime is controlled, because pace rose while home advantage fell. The model uses era-relative pace instead.", "",
              "### Factor families", "", "Gain over strength-only (log loss, positive = family helps) and loss when removed from the full model. The adjusted p-value "
              "uses a standard error clustered by game date and Holm's correction across the families tested:", "",
              "| Family | Factors | Gain over strength [95% CI] | Holm-adjusted p for the gain | Loss if removed [95% CI] |", "|---|---|---|---|---|"]
    for r in ex["families"]["families"]:
        gain = ci(r["gain_over_strength"]) if "gain_over_strength" in r else "baseline"
        holm = f"{r['gain_p_holm']:.3f}" if "gain_p_holm" in r else ""
        lines.append(f"| {r['family']} | {r['n_factors']} | {gain} | {holm} | {ci(r['loss_if_removed'])} |")
    o = ex["families"]["overall"]
    lines += ["", f"All {o['n_factors']} factors in a logistic model: log loss {o['full_logistic_logloss']:.4f}, accuracy {o['full_logistic_accuracy']:.3f} "
              f"(strength only {o['strength_only_logloss']:.4f}, {o['strength_only_accuracy']:.3f}; gradient boosting {o['full_boosting_logloss']:.4f}).",
              "", "### How long is a team's memory?", "", "Leave-one-season-out log loss of one rating signal (lower is better):", "",
              "| Signal | Log loss | SE |", "|---|---|---|"]
    for m in ex["memory"]:
        name = f"EWMA half-life {m['halflife_games']} games" if m["halflife_games"] else {"d_net_rtg": "Season-to-date net rating", "elo_diff": "Elo (carries over across seasons)"}[m["signal"]]
        lines.append(f"| {name} | {m['logloss']:.4f} | {m['se']:.4f} |")
    lines += ["", "### Skill or luck? Persistence of team stats", "", "Split-half reliability (odd vs even games, Spearman-Brown) and year-over-year correlation:", "",
              "| Stat | Split-half | Year over year |", "|---|---|---|"]
    lines += [f"| {p['label']} | {p['split_half']:.2f} | {p['year_over_year']:.2f} |" for p in ex["persistence"]]
    lines += ["", "### Opening weeks: Elo vs this season's record", "", "| Games played | Test games | Home | Elo | Record |", "|---|---|---|---|---|"]
    lines += [f"| {r['bucket']} | {r['n_games']} | {r['acc_home']:.3f} | {r['acc_elo']:.3f} | {r['acc_record']:.3f} |" for r in ex["early_season"]]
    hc = ex["home_court"]
    lines += ["", f"### Home-court value by franchise (league average {hc['league_avg_points']:.1f} points, controlling for Elo)", "",
              "| Franchise | Points | SE |", "|---|---|---|"]
    lines += [f"| {t['team']} | {t['hca']:.2f} | {t['se']:.2f} |" for t in hc["teams"]]
    return lines
