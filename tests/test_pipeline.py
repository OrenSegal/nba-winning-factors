import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import log_loss

from nbawin.data import STATS, load_team_logs, to_games
from nbawin.features import FEATURES, four_factors, possessions, pregame_features, same_game_factor_diffs
from nbawin.metrics import bootstrap_ci, expected_calibration_error, score
from nbawin.run import TEST_SEASONS, split


@pytest.fixture(scope="module")
def games():
    return to_games(load_team_logs())


# ---- data -------------------------------------------------------------------

def test_one_row_per_game_with_correct_home_team(games):
    assert games["GAME_ID"].is_unique
    # 2024-25 opener: LAL vs. MIN at Crypto.com Arena, LAL won 110-103
    g = games.set_index("GAME_ID").loc["0022400062"]
    assert (g["home_team"], g["away_team"], g["home_PTS"], g["away_PTS"], g["home_win"]) == ("LAL", "MIN", 110, 103, 1)


def test_neutral_site_games_dropped(games):
    # Paris game, MIA vs WAS in Mexico City and NBA Cup semifinals: both rows use '@'
    for gid in ["0022400147", "0022401229", "0022401230", "0022400621", "0022400633"]:
        assert gid not in set(games["GAME_ID"])


# ---- feature arithmetic -----------------------------------------------------

def test_four_factors_hand_computed():
    own = pd.DataFrame({"FGM": [40], "FG3M": [10], "FGA": [90], "FTM": [18], "FTA": [25], "OREB": [10], "TOV": [12]})
    opp = pd.DataFrame({"DREB": [30]})
    ff = four_factors(own, opp).iloc[0]
    assert ff["efg"] == pytest.approx(45 / 90)
    assert ff["tov_rate"] == pytest.approx(12 / possessions(90, 25, 10, 12))
    assert possessions(90, 25, 10, 12) == pytest.approx(103.0)
    assert ff["orb_rate"] == pytest.approx(10 / 40)
    assert ff["ft_rate"] == pytest.approx(18 / 90)


def test_pregame_win_pct_counts_only_earlier_games(games):
    feats = pregame_features(games).set_index("GAME_ID")
    season = games[games["SEASON"] == "2022-23"]
    gid = feats[feats["SEASON"] == "2022-23"].index[100]
    row = season[season["GAME_ID"] == gid].iloc[0]

    def record_before(team):
        prior = season[(season["GAME_DATE"] < row["GAME_DATE"])
                       & ((season["home_team"] == team) | (season["away_team"] == team))]
        won = np.where(prior["home_team"] == team, prior["home_win"], 1 - prior["home_win"])
        return won.mean()

    assert feats.loc[gid, "d_win"] == pytest.approx(record_before(row["home_team"]) - record_before(row["away_team"]))


# ---- leakage ----------------------------------------------------------------

def test_features_ignore_own_and_future_games(games):
    """Perturbing a game's own box score and every later game must not change its features."""
    base = pregame_features(games).set_index("GAME_ID")
    target = base.index[len(base) // 2]
    cutoff = games.loc[games["GAME_ID"] == target, "GAME_DATE"].iloc[0]
    tampered = games.copy()
    later = tampered["GAME_DATE"] >= cutoff
    stat_cols = [c for c in games if c.startswith(("home_", "away_")) and c not in ("home_team", "away_team", "home_win")]
    rng = np.random.default_rng(1)
    tampered.loc[later, stat_cols] = rng.integers(1, 150, size=(later.sum(), len(stat_cols)))
    tampered.loc[later, "home_win"] = 1 - tampered.loc[later, "home_win"]
    after = pregame_features(tampered).set_index("GAME_ID")
    pd.testing.assert_series_equal(base.loc[target, FEATURES], after.loc[target, FEATURES])


def test_no_outcome_columns_in_features():
    banned = ("PTS", "margin", "home_win", "PLUS_MINUS", "WL")
    assert not any(b.lower() in f.lower() for f in FEATURES for b in banned)


def test_time_split_train_strictly_before_test(games):
    train, test = split(pregame_features(games))
    assert set(test["SEASON"]) == set(TEST_SEASONS)
    assert train["GAME_DATE"].max() < test["GAME_DATE"].min()


def test_same_game_diffs_are_antisymmetric(games):
    d = same_game_factor_diffs(games.head(50))
    swap = {f"home_{c}": f"away_{c}" for c in STATS + ["team"]}
    swapped = games.head(50).rename(columns=swap | {v: k for k, v in swap.items()})
    d2 = same_game_factor_diffs(swapped)
    np.testing.assert_allclose(d["d_efg"], -d2["d_efg"])


# ---- metrics ----------------------------------------------------------------

def test_ece_hand_computed():
    y = [1, 0, 1, 1]
    p = [0.9, 0.1, 0.8, 0.4]
    # bins: 0.1 -> bin1 (y=0); 0.4 -> bin4 (y=1); 0.8 -> bin8 (y=1); 0.9 -> bin9 (y=1)
    expected = 0.25 * (0.1 + 0.6 + 0.2 + 0.1)
    assert expected_calibration_error(y, p) == pytest.approx(expected)
    assert expected_calibration_error([0, 1], [0.0, 1.0]) == pytest.approx(0.0)


def test_score_matches_definitions():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.8, 0.3, 0.4, 0.6])
    s = score(y, p)
    assert s["accuracy"] == pytest.approx(0.5)
    assert s["brier"] == pytest.approx(np.mean((p - y) ** 2))
    assert s["log_loss"] == pytest.approx(log_loss(y, p))
    assert score(y, None, np.array([1, 1, 1, 1])) == {"accuracy": 0.5}


def test_bootstrap_ci_brackets_point_estimate():
    y = np.r_[np.ones(600), np.zeros(400)]
    lo, hi = bootstrap_ci(y, lambda i: y[i].mean(), n=500)
    assert lo < 0.6 < hi and hi - lo < 0.08


def test_validate_logs_rejects_orphan_and_duplicate_rows():
    from nbawin.data import validate_logs

    logs = load_team_logs()
    good = logs[logs["GAME_ID"].isin(logs["GAME_ID"].unique()[:100])]
    validate_logs(good)
    with pytest.raises(ValueError, match="exactly two"):
        validate_logs(good.iloc[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        validate_logs(pd.concat([good, good.iloc[[0]]]))


def test_run_writes_outputs(tmp_path, monkeypatch):
    from nbawin import run

    monkeypatch.setattr(run, "OUT", tmp_path)
    monkeypatch.setattr(run, "N_BOOT", 20)
    monkeypatch.setattr(run, "WF_MIN_TRAIN", 23)  # walk-forward over the last 3 seasons only, keeps this fast
    run.main()
    report = (tmp_path / "report.md").read_text()
    assert "## What predicts a win before tipoff" in report and "## Walk-forward across all seasons" in report
    assert (tmp_path / "metrics.json").exists() and (tmp_path / "walk_forward.png").exists()
