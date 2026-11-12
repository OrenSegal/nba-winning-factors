"""Scoring helpers: point metrics, calibration error, paired bootstrap."""

import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss


def expected_calibration_error(y, p, n_bins: int = 10) -> float:
    """Weighted mean |observed win rate - mean predicted p| over equal-width bins."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    ece = 0.0
    for b in np.unique(bins):
        m = bins == b
        ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


def score(y, p, y_hat=None) -> dict:
    """Accuracy always; log loss, Brier and ECE only when probabilities p are given."""
    if p is None:
        return {"accuracy": accuracy_score(y, y_hat)}
    y_hat = (np.asarray(p) >= 0.5).astype(int) if y_hat is None else y_hat
    return {
        "accuracy": accuracy_score(y, y_hat),
        "log_loss": log_loss(y, p, labels=[0, 1]),
        "brier": brier_score_loss(y, p),
        "ece": expected_calibration_error(y, p),
    }


def bootstrap_ci(y, fn, n: int = 1000, seed: int = 0, alpha: float = 0.05, groups=None) -> tuple[float, float]:
    """Percentile CI of fn(idx) over n resamples of row indices (paired across models).

    With `groups` (one label per row, e.g. the game date) whole groups are resampled, so rows that
    share a group are never treated as independent draws.
    """
    rng = np.random.default_rng(seed)
    if groups is None:
        draw = lambda: rng.integers(0, len(y), len(y))
    else:
        codes = np.unique(np.asarray(groups), return_inverse=True)[1]
        members = [np.flatnonzero(codes == g) for g in range(codes.max() + 1)]
        draw = lambda: np.concatenate([members[g] for g in rng.integers(0, len(members), len(members))])
    stats = [fn(draw()) for _ in range(n)]
    lo, hi = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)
