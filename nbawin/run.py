"""End-to-end analysis: uv run python -m nbawin.run

Writes results/metrics.json, results/report.md and figures in results/.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nbawin.data import load_team_logs, to_games
from nbawin.features import FEATURES, pregame_features, same_game_factor_diffs
from nbawin.metrics import bootstrap_ci, score

OUT = Path(__file__).resolve().parent.parent / "results"
TEST_SEASONS = ["2023-24", "2024-25"]
FACTOR_FEATURES = [f for f in FEATURES if f not in ("d_win", "d_net_rtg")]
SEED = 0
N_BOOT = 1000


def split(df: pd.DataFrame):
    test = df["SEASON"].isin(TEST_SEASONS)
    return df[~test], df[test]


def lr():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))


def fit_models(train: pd.DataFrame) -> dict:
    y = train["home_win"]
    models = {
        "Logistic regression (all features)": (lr(), FEATURES),
        "Logistic regression (four factors + rest only)": (lr(), FACTOR_FEATURES),
        "Gradient boosting (all features)": (
            HistGradientBoostingClassifier(
                learning_rate=0.05, max_iter=300, max_depth=3, min_samples_leaf=50, random_state=SEED
            ),
            FEATURES,
        ),
        "Simple model: logistic on win% difference only": (lr(), ["d_win"]),
    }
    for model, cols in models.values():
        model.fit(train[cols], y)
    return models


def predictions(train: pd.DataFrame, test: pd.DataFrame, models: dict) -> dict:
    """name -> (probabilities or None, hard predictions) on test."""
    home_rate = train["home_win"].mean()
    preds = {
        "Baseline: home team wins": (np.full(len(test), home_rate), np.ones(len(test), int)),
        # ties (equal season-to-date win%) go to the home team
        "Baseline: better season-to-date record wins": (None, (test["d_win"] >= 0).astype(int).to_numpy()),
    }
    for name, (model, cols) in models.items():
        p = model.predict_proba(test[cols])[:, 1]
        preds[name] = (p, (p >= 0.5).astype(int))
    return preds


def results_table(test: pd.DataFrame, preds: dict) -> pd.DataFrame:
    y = test["home_win"].to_numpy()
    rows = []
    for name, (p, y_hat) in preds.items():
        row = {"model": name, **score(y, p, y_hat)}
        lo, hi = bootstrap_ci(y, lambda i: (y_hat[i] == y[i]).mean(), N_BOOT, SEED)
        row["accuracy_ci"] = [lo, hi]
        if p is not None:
            row["log_loss_ci"] = list(bootstrap_ci(y, lambda i: score(y[i], p[i])["log_loss"], N_BOOT, SEED))
        for season in TEST_SEASONS:
            m = (test["SEASON"] == season).to_numpy()
            row[f"accuracy_{season}"] = float((y_hat[m] == y[m]).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def paired_deltas(test: pd.DataFrame, preds: dict, model: str) -> dict:
    """Model minus each baseline, with paired bootstrap CIs over the same resampled games."""
    y = test["home_win"].to_numpy()
    p, y_hat = preds[model]
    out = {}
    for base in ["Baseline: home team wins", "Baseline: better season-to-date record wins",
                 "Simple model: logistic on win% difference only"]:
        bp, by = preds[base]
        d_acc = lambda i: (y_hat[i] == y[i]).mean() - (by[i] == y[i]).mean()
        entry = {"accuracy_delta": float(d_acc(np.arange(len(y)))), "accuracy_delta_ci": bootstrap_ci(y, d_acc, N_BOOT, SEED)}
        if bp is not None:
            d_ll = lambda i: score(y[i], p[i])["log_loss"] - score(y[i], bp[i])["log_loss"]
            entry["log_loss_delta"] = float(d_ll(np.arange(len(y))))
            entry["log_loss_delta_ci"] = bootstrap_ci(y, d_ll, N_BOOT, SEED)
        out[base] = entry
    return out


def coefficient_cis(train: pd.DataFrame, cols: list[str], n: int = 200) -> pd.DataFrame:
    """Standardized logistic coefficients, refit on bootstrap resamples of training games."""
    rng = np.random.default_rng(SEED)
    X, y = train[cols].to_numpy(), train["home_win"].to_numpy()
    point = lr().fit(X, y)[-1].coef_[0]
    boots = np.array([lr().fit(X[i], y[i])[-1].coef_[0] for i in (rng.integers(0, len(y), len(y)) for _ in range(n))])
    lo, hi = np.quantile(boots, [0.025, 0.975], axis=0)
    return pd.DataFrame({"feature": cols, "coef": point, "ci_low": lo, "ci_high": hi}).sort_values("coef", key=abs, ascending=False)


def perm_importance(test: pd.DataFrame, model, cols: list[str]) -> pd.DataFrame:
    r = permutation_importance(model, test[cols], test["home_win"], scoring="neg_log_loss", n_repeats=30, random_state=SEED)
    return pd.DataFrame({"feature": cols, "mean": r.importances_mean, "std": r.importances_std}).sort_values("mean", ascending=False)


def descriptive_factors(games: pd.DataFrame) -> dict:
    """Same-game four-factor differences vs margin. Explains outcomes; cannot forecast them."""
    d = same_game_factor_diffs(games)
    cols = ["d_efg", "d_tov_rate", "d_orb_rate", "d_ft_rate"]
    train, test = split(d)
    sd = train[cols].std()
    reg = LinearRegression().fit(train[cols] / sd, train["margin"])
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(train), len(train))
        boots.append(LinearRegression().fit(train[cols].iloc[i] / sd, train["margin"].iloc[i]).coef_)
    lo, hi = np.quantile(boots, [0.025, 0.975], axis=0)
    clf = lr().fit(train[cols], train["home_win"])
    return {
        "n_train_games": len(train),
        "n_test_games": len(test),
        "test_r2_margin": float(reg.score(test[cols] / sd, test["margin"])),
        "test_accuracy_win_from_same_game_factors": float(clf.score(test[cols], test["home_win"])),
        "points_per_1sd": {c: {"coef": float(b), "ci": [float(l), float(h)], "1sd": float(sd[c])}
                           for c, b, l, h in zip(cols, reg.coef_, lo, hi)},
    }


def plot_calibration(test: pd.DataFrame, preds: dict, path: Path) -> None:
    y = test["home_win"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], ls="--", c="grey", lw=1, label="perfect calibration")
    for name in ["Logistic regression (all features)", "Gradient boosting (all features)",
                 "Simple model: logistic on win% difference only"]:
        frac, mean_p = calibration_curve(y, preds[name][0], n_bins=10, strategy="quantile")
        ax.plot(mean_p, frac, marker="o", ms=4, label=name)
    ax.axhline(preds["Baseline: home team wins"][0][0], c="black", lw=1, ls=":", label="home-win base rate (train)")
    ax.set(xlabel="predicted P(home win)", ylabel="observed home win rate",
           title=f"Calibration on held-out seasons {' & '.join(TEST_SEASONS)}\n(n={len(test)} games, deciles of prediction)")
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_coefficients(coefs: pd.DataFrame, path: Path) -> None:
    c = coefs.sort_values("coef")
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.errorbar(c["coef"], c["feature"], xerr=[c["coef"] - c["ci_low"], c["ci_high"] - c["coef"]], fmt="o", capsize=3)
    ax.axvline(0, c="grey", lw=1)
    ax.set(xlabel="log-odds of home win per 1 SD (95% bootstrap CI)",
           title="Pre-game factors: logistic coefficients\n(home minus away, season-to-date, train 2015-16 to 2022-23)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fmt_ci(ci) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def write_report(summary: dict, table: pd.DataFrame, path: Path) -> None:
    lines = [f"Train: {summary['train_games']} games ({summary['train_seasons']}). "
             f"Test: {summary['test_games']} games ({', '.join(TEST_SEASONS)}).", "",
             "| Model | Accuracy [95% CI] | Log loss [95% CI] | Brier | ECE | Acc 2023-24 | Acc 2024-25 |",
             "|---|---|---|---|---|---|---|"]
    for r in table.to_dict("records"):
        ll = f"{r['log_loss']:.4f} {fmt_ci(r['log_loss_ci'])}" if isinstance(r.get("log_loss_ci"), list) else "n/a"
        brier = f"{r['brier']:.4f}" if pd.notna(r.get("brier")) else "n/a"
        ece = f"{r['ece']:.3f}" if pd.notna(r.get("ece")) else "n/a"
        lines.append(f"| {r['model']} | {r['accuracy']:.3f} {fmt_ci(r['accuracy_ci'])} | {ll} | {brier} | {ece} | "
                     f"{r['accuracy_2023-24']:.3f} | {r['accuracy_2024-25']:.3f} |")
    lines += ["", "Paired bootstrap over test games, model minus baseline (positive accuracy delta and negative log-loss delta = model better):", ""]
    for model, deltas in summary["deltas"].items():
        for base, d in deltas.items():
            s = f"- {model} vs {base}: accuracy {d['accuracy_delta']:+.3f} {fmt_ci(d['accuracy_delta_ci'])}"
            if "log_loss_delta" in d:
                s += f", log loss {d['log_loss_delta']:+.4f} {fmt_ci(d['log_loss_delta_ci'])}"
            lines.append(s)
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    games = to_games(load_team_logs())
    df = pregame_features(games)
    train, test = split(df)
    assert train["GAME_DATE"].max() < test["GAME_DATE"].min(), "time split violated"

    models = fit_models(train)
    preds = predictions(train, test, models)
    table = results_table(test, preds)
    deltas = {m: paired_deltas(test, preds, m) for m in
              ["Logistic regression (all features)", "Gradient boosting (all features)"]}
    coefs = coefficient_cis(train, FACTOR_FEATURES)
    perm = {name: perm_importance(test, models[name][0], models[name][1]).to_dict("records")
            for name in ["Logistic regression (all features)", "Gradient boosting (all features)"]}

    plot_calibration(test, preds, OUT / "calibration.png")
    plot_coefficients(coefs, OUT / "coefficients.png")

    summary = {
        "games_total": len(games),
        "games_after_min_prior_filter": len(df),
        "train_games": len(train),
        "test_games": len(test),
        "train_seasons": f"{train['SEASON'].min()} to {train['SEASON'].max()}",
        "train_home_win_rate": float(train["home_win"].mean()),
        "test_home_win_rate": float(test["home_win"].mean()),
        "results": table.to_dict("records"),
        "deltas": deltas,
        "factor_coefficients": coefs.to_dict("records"),
        "permutation_importance_test_neg_log_loss": perm,
        "descriptive_same_game_factors": descriptive_factors(games),
    }
    (OUT / "metrics.json").write_text(json.dumps(summary, indent=2, default=float))
    write_report(summary, table, OUT / "report.md")
    print((OUT / "report.md").read_text())
    print(json.dumps({k: summary[k] for k in ["factor_coefficients", "permutation_importance_test_neg_log_loss",
                                              "descriptive_same_game_factors"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
