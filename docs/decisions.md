# Decisions and rejected alternatives

Short records of the choices that shaped the project. Each lists what was chosen, what was not, and why.

**Static report site, no live service.** Chosen: a static page reading `metrics.json`. Rejected: FastAPI + MLflow + Streamlit (the first version; its only endpoint failed on every call and no model was ever served) and a hosted prediction API. Nothing consumes live predictions, and a static page cannot rot.

**CSV snapshot, no database or persisted feature store.** The data is 8.5 MB and the full run takes about two minutes. Rejected: DuckDB/Parquet layers and an orchestrator. A persisted intermediate table would add a stale-cache failure mode for no speed gain. Validation runs on every load instead.

**Time-ordered split plus walk-forward, never a random split.** The scaffold used a random split on same-game stats including the target. Chosen: train 2000-01 to 2022-23, hold out 2023-24 to 2025-26, assert train precedes test, and run an expanding-window backtest as an independent check. Hyperparameters are fixed, not tuned, so the test seasons never selected a model.

**Logistic regression as the primary model; boosting only as a check.** Boosting did not beat logistic on log loss, is harder to interpret, and was not given a tuning budget. Rejected: neural nets and stacking (no evidence the signal is nonlinear enough to pay for the complexity).

**Pre-game and same-game factors are separate code paths.** Same-game four factors explain a game (R2 about 0.95, close to an accounting identity) and never enter a predictive model. Rejected: reporting the high accuracy as a finding.

**Leakage tested by perturbation.** A test rewrites a game and every later game, then asserts a game's features do not move. Rejected: relying on code review of the shift/expanding logic. Same-day games are excluded from each other's league-level state because tipoff times differ.

**Elo with margin of victory and a quarter-season-to-mean carry-over, standard constants (K=20, carry 0.75, home 100), not tuned.** Chosen so the opening weeks have a rating and so results do not depend on a fitted hyperparameter. Rejected: tuning K and carry on the test seasons.

**Era control: a rolling league home-win rate, not season fixed effects.** Season dummies cannot be applied to a season the model has not seen and would absorb the very drift being studied. The rolling rate is known at tipoff. Raw pace is kept only as a diagnostic to show the confound.

**Factor screen: Bonferroni on in-sample Wald z, plus out-of-sample log-loss change with a paired bootstrap.** Chosen for simplicity and conservatism. Rejected: Holm or Benjamini-Hochberg (less conservative, defensible, not implemented), and p-value hacking via many specifications. Known gap: the screen uses one split.

**Bootstrap resamples games as independent.** Simple and paired across models. Rejected for now: resampling by date or week (clustered), which would widen intervals somewhat. Listed as a limitation.

**Home-court by franchise as fixed effects (OLS on margin with Elo).** Rejected: a hierarchical model with partial pooling (PyMC), which would shrink noisy extremes but adds a dependency for a descriptive table.

**Memory half-life by leave-one-season-out.** A single-signal two-parameter model trains stably on other seasons, but it uses future seasons, so it is not comparable to the walk-forward numbers and is labeled as such.

**Early-season games excluded from the main models (first 10 games per team).** Season-to-date averages are too noisy there. They are scored separately with Elo.

**Neutral-site games dropped.** No home team to define the target. Paris, Mexico City and NBA Cup semifinals are a handful of games.

**No betting lines.** The market is the real benchmark and would very likely win. Rejected for now: licensing and ingestion cost; listed as the next benchmark.

## Team-season layer (style or substance)

**Two layers, kept apart.** Pre-game factors predict a game and must be knowable at tipoff. Season-profile metrics (shot zones, tracking, hustle) only exist as season aggregates, so they can describe a finished season but cannot forecast a game. Mixing them would leak the outcome into the features. Rejected: pulling per-game tracking data (stats.nba.com does not expose it for teams in one call and it would multiply requests by 1,200 per season).

**Z-score every metric within its season.** The three-point rate, pace and nearly every volume stat trend over 26 years, so a pooled correlation measures the era. Within-season z-scores compare a team only with its contemporaries. Rejected: detrending with a regression on year, which assumes a smooth trend.

**Resample seasons, not teams.** The 30 teams in a season share one league, one rulebook and each other's schedules. A team-level bootstrap would give intervals that are too narrow. Seasons are the cluster, at the cost of fewer units (26, and 10 to 13 for tracking).

**A chance ceiling instead of 87 p-values.** Win % is shuffled inside each season 1,000 times and the largest |t| across all metrics is recorded. The 95th percentile, converted to a correlation for each metric's own sample size, is the bar a metric has to clear. It controls the family-wise error without assuming independence between metrics (they are heavily correlated). Rejected: Bonferroni across 87 metrics, which is too strict when metrics are about 26 independent ideas.

**Role labels (style, execution, effort) are judgment calls.** Style is a choice made before the shot (where, how fast, how often to drive or pass). Execution is the result (shooting %, turnovers, rebounds, what the defense allows, and anything that counts points). Assists need a made shot, so they are execution. Points-per-100 counts (fast break, second chance, assist points) are execution because they are outcomes. A first pass classified assists and point shares as style and made style look like it explained 83% of offense; the leak was found by dropping one family at a time. Points per drive was a second, smaller leak (style 50% before, 31% after). The split is a gradient, and the page says so.

**Ridge with leave-one-season-out, not a tuned model.** Metrics outnumber the usable rows in the tracking era (86 against 300), so unpenalised least squares overfits. The ridge penalty is picked by internal cross-validation inside each training fold; the held-out season never informs it.

**The "beyond net rating" test is the headline.** Execution explaining 91% of wins is nearly true by construction. The informative number is what remains after net rating: about 4% of the leftover (interval 0.7 to 7.1%), small but not zero.

**Rolling five-season windows for the edge chart.** One season has 30 teams, so a single-season correlation has a standard error near 0.18. Five pooled seasons bring it to about 0.08. The Fisher interval treats teams as independent and is labeled optimistic.

**Drives read as correlation only.** The negative link between drive volume and wins is not evidence that driving hurts; weaker offenses may drive more because they have fewer alternatives. Season data cannot separate those, and the page says so.
