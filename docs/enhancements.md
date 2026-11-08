# Enhancement plan: what databallr does that this project should borrow

Reviewed 2026-11-08 against databallr.com (home, /teams, /stats, /calculator).

## What databallr is, and what it is not

databallr has 27 tools, most of them about players: RAPM-based impact metrics, WOWY lineups, live scores, contracts and draft games. This project has no player or play-by-play data and has deliberately left out a live layer, so copying their breadth is the wrong goal.

The thing worth borrowing is how a number is presented, not which numbers exist:

- **Every value carries its rank.** On /teams each cell shows the value with `#n` under it. A reader never has to ask whether +1.7 is good.
- **The model is a sandbox.** /calculator turns a published decomposition (Poropudas and Halme, *Dean Oliver's Four Factors Revisited*) into sliders, and cites the paper on the page.
- **Methodology sits next to the tool.** Each page has a glossary block, sign conventions ("positive is good everywhere") and a note on what is not yet done ("not ridge-regressed yet").
- **Luck is a toggle.** /teams has a "3P Luck" switch that re-ranks teams with shooting variance taken out.

This project has the opposite strength: held-out validation, chance ceilings, a clean split between pre-game and post-game information, and a thesis (style versus execution). The plan keeps that identity and adopts the presentation habits.

## Ranked enhancements

| # | Enhancement | Why it matters to a reader or reviewer | Data needed | Status |
|---|---|---|---|---|
| 1 | **Six-factor table for every season.** Net rating split into eight per-100 contributions (shooting, turnovers, rebounds, free throws, on each end), with each team's rank under each value. | Answers "why did this team win" in one row. Ours is regression-fitted on 776 team-seasons; databallr notes theirs is not regressed yet. | `ff_*` columns already in `data/raw` | Built |
| 2 | **3P-luck-adjusted standings.** Shrink each team's own and allowed 3P% toward the league by our measured reliability (0.60 and 0.35), convert the difference to points per 100, then re-rank. | Turns a finding (opponent 3P% is mostly noise) into a tool. Shows which records flattered or punished a team. | `opp_OPP_FG3A`, `opp_OPP_FG3_PCT`, zone 3PA/3PM, `metrics.json` reliabilities | Built |
| 3 | **Methods panel on the dashboard.** Data lineage, within-season z-scores, leave-one-season-out CV, season bootstrap, permutation ceiling, what was chosen after looking, how to reproduce. | Rigour the reader can see without opening the report. | none | Built |
| 4 | **Four-factor what-if sandbox.** Sliders for the eight factors, then predicted net rating, then expected wins, using the table's fitted weights. Show the closest historical team. | Turns the model into something to drive; the most shareable piece. | the weights from item 1 | Next |
| 5 | **Team-season twin.** Nearest neighbors by shot profile across all 26 seasons ("the 2025-26 Celtics shoot like the 2018-19 Rockets"). | Memorable, and it uses the atlas's within-season z-scores directly. | `dashboard.json` scatter keys | Next |
| 6 | **Team compare.** Two team-seasons side by side across the six factors and shot profile. | Common request; it reuses items 1 and 5. | same | Later |
| 7 | **Glossary page.** All 86 season metrics and 57 pre-game factors with definitions, sign convention and source table. | Already half there in the explorer; a standalone URL is linkable. | `factor_atlas.csv`, `DEFINITIONS` | Later |
| 8 | **Keyboard scrub.** Left and right arrows move the season; `F` focuses the franchise picker. | Cheap polish that databallr makes a point of. | none | Later |

## Deliberately not borrowed

- **Player metrics (RAPM, DPM, WOWY).** These need play-by-play and lineup data. A separate project.
- **Live and current-season windows (last 30 days and so on).** The user chose a modern design, not 2026-27 data. Date-sliced team stats would also need game-level aggregation of every table.
- **Games and gamification.** Off-thesis.
- **Card views and photo assets.** Licensing, and no analytical gain.

## Method notes for items 1 and 2

- **Six factors.** For each season the eight four-factor rates are centerd on that season's league mean. Net rating per 100 is regressed on the eight centerd rates, pooled over all team-seasons with no intercept. Each team's contribution is the coefficient times its deviation, signed so that positive helps. The residual (net minus the sum of contributions) is shown so the decomposition is honest about what it misses.
- **3P luck.** Expected 3P% equals the league rate plus reliability times (observed minus league). Luck in points per 100 equals (observed minus expected) times 3PA per 100 times 3. This is done for the offense (reliability 0.60) and the defense (0.35). Adjusted net equals net minus offensive luck plus defensive luck. Adjusted win % uses the pooled slope of win % on net rating. Reliabilities are split-half values with the Spearman-Brown correction from `nbawin/explore.py`. That treats each season's shooting variance as luck in proportion to how little of it repeats, which is a simplification: it ignores shot quality and who took the shot.
