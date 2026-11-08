"use strict";
(() => {
/* Every number on the page comes from metrics.json (written by nbawin.run). Charts are plain SVG. */
const NS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);
const el = (tag, a = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (parent) parent.appendChild(e); return e; };
const txt = (p, x, y, s, a = {}) => { const t = el("text", { x, y, ...a }, p); t.textContent = s; return t; };
const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
const sgn = (v, d = 2) => (v >= 0 ? "+" : "-") + Math.abs(v).toFixed(d);
const lin = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
const COLOR = { s1: "var(--s1)", s2: "var(--s2)", s3: "var(--s3)", gray: "var(--gray)" };

const tip = $("#tip");
function showTip(html, e) {
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.transform = `translate(${Math.max(8, x)}px,${Math.max(8, y)}px)`;
}
const hideTip = () => { tip.hidden = true; };
function hover(node, htmlFn) {
  node.addEventListener("pointermove", (e) => showTip(htmlFn(), e));
  node.addEventListener("pointerdown", (e) => showTip(htmlFn(), e));
  node.addEventListener("pointerleave", hideTip);
}

function mount(id, height, draw) {
  const box = document.getElementById(id);
  if (!box) return;
  const go = () => {
    box.querySelectorAll(":scope > svg").forEach((n) => n.remove());
    const w = Math.max(260, Math.floor(box.clientWidth)), h = typeof height === "function" ? height(w) : height;
    const svg = el("svg", { width: w, height: h, viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": box.dataset.label || "" });
    box.prepend(svg); box._w = w; draw(svg, w, h);
  };
  go();
  new ResizeObserver(() => { if (Math.floor(box.clientWidth) !== box._w) go(); }).observe(box);
}
const setHTML = (id, html) => { const n = document.getElementById(id); if (n) n.innerHTML = html; };
function legend(id, items) {
  setHTML(id, items.map(([c, label, kind]) => `<span><i class="${kind || ""}" style="background:${COLOR[c]};border-color:${COLOR[c]}"></i>${label}</span>`).join(""));
}
function dtable(id, headers, rows) {
  setHTML(id, `<details><summary>View as table</summary><table><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>` +
    rows.map((r) => `<tr>${r.map((c, i) => `<td class="${i ? "n" : ""}">${c}</td>`).join("")}</tr>`).join("") + "</table></details>");
}
const barPath = (x, y, w, h, r = 4) => { const rr = Math.min(r, w / 2, h / 2); return `M${x} ${y}H${x + w - rr}Q${x + w} ${y} ${x + w} ${y + rr}V${y + h - rr}Q${x + w} ${y + h} ${x + w - rr} ${y + h}H${x}Z`; };
const NAMES = {
  away_b2b: "Road team on a back-to-back", home_b2b: "Home team on a back-to-back", d_rest: "Rest-days edge", away_g4n3: "Road team: 3rd game in 4 nights",
  away_g6n5: "Road team: 4th game in 6 nights", home_g4n3: "Home team: 3rd game in 4 nights", home_g6n5: "Home team: 4th game in 6 nights",
  d_def_fg3_pct: "Opponents' 3P% allowed (luck)", home_alt_km: "Altitude of the home arena", d_alt: "Altitude gap", d_ewm5: "Hot streak (last ~5 games)",
  d_ewm8: "Recent form (~8 games)", d_ewm20: "Recent form (~20 games)", d_form10: "Last 10 vs season", d_luck: "Record vs point differential (luck)",
  d_close_net: "Close-game record", pace_sum_rel: "Combined pace", vol_sum: "Combined volatility", fav_x_vol: "Favorite x volatility", abs_d_pace: "Pace mismatch",
  season_day: "Point in season", is_weekend: "Weekend game", rematch_n: "Rematch number", league_home_rate: "League home-win rate lately",
  home_streak: "Home team: games into a home stand", away_streak: "Road team: games into a road trip", home_travel: "Home team travel", away_travel: "Road team travel",
  d_ast_rate: "Assist rate edge", d_blk_rate: "Block rate edge", d_def_orb_rate: "Defensive rebounding edge", d_fg3a_rate: "Three-point volume edge",
};
const nice = (f) => NAMES[f] || f.replace(/^d_/, "").replace(/_/g, " ");

fetch("metrics.json").then((r) => r.json()).then(main).catch((e) => console.error(e));

function main(M) {
  const X = M.explore, fam = X.families, ov = fam.overall, D = M.descriptive_same_game_factors, byModel = Object.fromEntries(M.results.map((r) => [r.model, r]));
  const seasons = X.trends.map((t) => t.SEASON);
  const first = (key) => X.trends[0][key], last = (key) => X.trends[X.trends.length - 1][key];

  /* hero */
  setHTML("hero-sub", `${seasons.length} seasons, ${M.games_total.toLocaleString()} games and ${ov.n_factors + M.style.n_metrics} factors, from Dean Oliver's four factors to altitude, travel, luck, three-point rates and drives. Act I tests what survives contact with games it has never seen. Act II asks whether style or execution wins seasons.`);
  setHTML("board", [[M.games_total.toLocaleString(), "games"], [ov.n_factors + M.style.n_metrics, "factors tested"], [pct(ov.full_logistic_accuracy, 1), "all-factor model, unseen seasons"], [pct(D.test_accuracy_win_from_same_game_factors, 1), "box score, after the fact"]]
    .map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join(""));
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) document.querySelectorAll("#ball animateMotion").forEach((n) => n.remove());

  /* 1: after the buzzer */
  const four = [["d_efg", "Shooting efficiency (eFG%)", 40], ["d_tov_rate", "Fewer turnovers", 25], ["d_orb_rate", "More offensive rebounds", 20], ["d_ft_rate", "More free-throw trips", 15]]
    .map(([k, label, oliver]) => ({ k, label, oliver, v: Math.abs(D.points_per_1sd[k].coef), sd: D.points_per_1sd[k]["1sd"] }));
  const tot = four.reduce((s, r) => s + r.v, 0); four.forEach((r) => { r.share = r.v / tot; });
  setHTML("t-after", `Once a game is over, four box-score numbers account for ${pct(D.test_r2_margin)} of the final margin and pick the winner ${pct(D.test_accuracy_win_from_same_game_factors)} of the time: shooting efficiency, turnovers, offensive rebounds and free throws. A one-standard-deviation edge in shooting is worth ${four[0].v.toFixed(1)} points. Most of that is bookkeeping, since the four numbers nearly determine the score, and none of them exist before tip-off.`);
  setHTML("n-after", `Dean Oliver's rule of thumb weights the four factors 40/25/20/15. Measured over ${seasons.length} seasons the split is ${four.map((r) => Math.round(r.share * 100)).join("/")}.`);
  mount("c-after", 4 * 62 + 8, (svg, w) => {
    const sx = lin(0, four[0].v * 1.12, 6, w - 78);
    four.forEach((r, i) => {
      const y = 8 + i * 62;
      txt(svg, 6, y + 12, r.label, { class: "t-lab" });
      txt(svg, w - 6, y + 12, `${Math.round(r.share * 100)}% of swing, Oliver ${r.oliver}%`, { class: "t-axis", "text-anchor": "end" });
      const bar = el("path", { d: barPath(6, y + 22, sx(r.v) - 6, 20), style: "fill:var(--s2)" }, svg);
      txt(svg, sx(r.v) + 8, y + 37, `${r.v.toFixed(1)} pts`, { class: "t-val" });
      hover(bar, () => `<b>${r.label}</b><br>${r.v.toFixed(2)} points of margin per 1 SD<br>1 SD = ${(r.sd * 100).toFixed(1)} percentage points`);
    });
  });
  dtable("d-after", ["Factor", "Points per 1 SD", "Share", "Oliver"], four.map((r) => [r.label, r.v.toFixed(2), pct(r.share, 0), r.oliver + "%"]));

  /* 2: the ceiling */
  const home = byModel["Baseline: home team wins"], rec = byModel["Baseline: better season-to-date record wins"], ff = byModel["Logistic regression (four factors + rest only)"];
  const ladder = [
    { label: "Always pick the home team", v: home.accuracy, ci: home.accuracy_ci, c: "gray", cap: "Knowable at tip-off" },
    { label: "Pick the team with the better record", v: rec.accuracy, ci: rec.accuracy_ci, c: "s1" },
    { label: "Four factors plus rest, logistic model", v: ff.accuracy, ci: ff.accuracy_ci, c: "s2" },
    { label: `Wide model, all ${ov.n_factors} factors`, v: ov.full_logistic_accuracy, c: "s2" },
    { label: "The box score of the game itself", v: D.test_accuracy_win_from_same_game_factors, c: "s3", cap: "Only knowable afterwards" },
  ];
  setHTML("t-ladder", `Using only what is known before the game, the best model here is right ${pct(ov.full_logistic_accuracy, 1)} of the time on ${M.test_games.toLocaleString()} games from three seasons it never trained on. Picking the team with the better record gets ${pct(rec.accuracy, 1)}. Everything layered on top is worth about ${((ov.full_logistic_accuracy - rec.accuracy) * 100).toFixed(1)} points, close to the noise floor for a sample this size.`);
  mount("c-ladder", 5 * 52 + 88, (svg, w) => {
    const L = 6, R = w - 62, sx = lin(0, 1, L, R); let y = 14;
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { el("line", { x1: sx(t), x2: sx(t), y1: 6, y2: 5 * 52 + 52, class: "grid-line" }, svg); txt(svg, sx(t), 5 * 52 + 66, pct(t, 0), { class: "t-axis", "text-anchor": "middle" }); });
    el("line", { x1: sx(0.5), x2: sx(0.5), y1: 6, y2: 5 * 52 + 52, style: "stroke:var(--ink2);stroke-dasharray:4 4;stroke-width:1.5" }, svg);
    txt(svg, sx(0.5), 5 * 52 + 80, "coin flip", { class: "t-axis", "text-anchor": "middle" });
    ladder.forEach((r, i) => {
      if (r.cap) { y += i ? 14 : 0; txt(svg, L, y + 2, r.cap, { class: "t-cap" }); }
      const by = y + 24, bar = el("path", { d: barPath(L, by, sx(r.v) - L, 18), style: `fill:${COLOR[r.c]}` }, svg);
      txt(svg, L, y + 16, r.label, { class: "t-lab" });
      txt(svg, sx(r.ci ? r.ci[1] : r.v) + 8, by + 14, pct(r.v), { class: "t-val" });
      if (r.ci) { [[r.ci[0], r.ci[1]]].forEach(([a, b]) => { el("path", { d: `M${sx(a)} ${by + 9}H${sx(b)}M${sx(a)} ${by + 4}V${by + 14}M${sx(b)} ${by + 4}V${by + 14}`, style: "stroke:var(--ink);stroke-width:1.5;fill:none" }, svg); }); }
      hover(bar, () => `<b>${r.label}</b><br>${pct(r.v)} correct${r.ci ? `<br>95% CI ${pct(r.ci[0])} to ${pct(r.ci[1])}` : ""}`);
      y += 52;
    });
  });
  setHTML("n-ladder", `The four-factor model was singled out after the results were in, so its margin is optimistic. The all-factor model has no interval. Betting lines are not included and would very likely beat every row.`);
  dtable("d-ladder", ["Predictor", "Accuracy"], ladder.map((r) => [r.label, pct(r.v)]));

  /* 3: the wide screen */
  const famRows = fam.families.filter((f) => f.family !== "Strength").map((f) => {
    const era = f.family === "Era regime", m = era ? f.loss_if_removed : f.gain_over_strength;
    return { name: f.family, n: f.n_factors, v: m[0] * 1000, lo: m[1] * 1000, hi: m[2] * 1000, era };
  }).sort((a, b) => b.v - a.v);
  const winners = famRows.filter((r) => r.lo > 0);
  setHTML("t-screen", `${X.n_factors_screened + X.base.length} candidate factors, each added to a baseline of team strength and the league's current home-court level, then scored on three seasons the model never saw. Families whose interval clears zero: ${winners.map((w) => w.name.toLowerCase()).join(" and ")}. The rest, including ${famRows.filter((r) => r.lo <= 0).slice(0, 5).map((r) => r.name.toLowerCase()).join(", ")}, cannot be told apart from no effect.`);
  mount("c-fam", famRows.length * 30 + 44, (svg, w) => {
    const lw = Math.min(210, w * 0.42), lo = Math.min(0, ...famRows.map((r) => r.lo)) - 0.3, hi = Math.max(...famRows.map((r) => r.hi)) + 0.3, sx = lin(lo, hi, lw, w - 16);
    const ticks = []; for (let t = Math.ceil(lo); t <= hi; t++) ticks.push(t);
    ticks.forEach((t) => { el("line", { x1: sx(t), x2: sx(t), y1: 4, y2: famRows.length * 30 + 6, class: t === 0 ? "zero" : "grid-line" }, svg); txt(svg, sx(t), famRows.length * 30 + 22, t, { class: "t-axis", "text-anchor": "middle" }); });
    txt(svg, w - 16, famRows.length * 30 + 38, "better forecasts, thousandths of log loss", { class: "t-axis", "text-anchor": "end" });
    famRows.forEach((r, i) => {
      const y = 20 + i * 30, real = r.lo > 0;
      txt(svg, 4, y + 4, r.name, { class: "t-lab" });
      el("path", { d: `M${sx(r.lo)} ${y}H${sx(r.hi)}`, style: `stroke:${real ? "var(--s2)" : "var(--gray)"};stroke-width:2` }, svg);
      const dot = el("circle", { cx: sx(r.v), cy: y, r: 6, style: `fill:${r.era ? "var(--surface)" : real ? "var(--s2)" : "var(--gray)"};stroke:${real ? "var(--s2)" : "var(--gray)"};stroke-width:2` }, svg);
      hover(dot, () => `<b>${r.name}</b> (${r.n} factors)<br>${r.v.toFixed(2)} [${r.lo.toFixed(2)}, ${r.hi.toFixed(2)}] thousandths${r.era ? "<br>measured as loss if removed" : ""}<br>${real ? "Clearly helps" : "Cannot be told from zero"}`);
    });
  });
  dtable("d-fam", ["Family", "Factors", "Gain (milli log loss)", "Low", "High"], famRows.map((r) => [r.name + (r.era ? " (if removed)" : ""), r.n, r.v.toFixed(2), r.lo.toFixed(2), r.hi.toFixed(2)]));

  const pts = X.screen.map((r) => ({ ...r, gain: -r.d_logloss * 1000, holds: r.significant_after_bonferroni && r.d_logloss_ci[1] < 0 }))
    .map((r) => ({ ...r, cat: r.holds ? "s3" : r.significant_after_bonferroni ? "s2" : "gray" }));
  legend("l-scatter", [["s3", "Holds up out of sample"], ["s2", "Significant in-sample only"], ["gray", "Not significant"]]);
  mount("c-scatter", (w) => (w < 520 ? 340 : 400), (svg, w, h) => {
    const m = { l: 56, r: 16, t: 14, b: 40 }, zmax = Math.ceil(Math.max(...pts.map((p) => Math.abs(p.z)))), gmin = Math.min(...pts.map((p) => p.gain)) - 0.2, gmax = Math.max(...pts.map((p) => p.gain)) + 0.3;
    const sx = lin(-zmax, zmax, m.l, w - m.r), sy = lin(gmin, gmax, h - m.b, m.t);
    for (let t = Math.ceil(gmin); t <= gmax; t++) { el("line", { x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), class: t === 0 ? "zero" : "grid-line" }, svg); txt(svg, m.l - 6, sy(t) + 4, t, { class: "t-axis", "text-anchor": "end" }); }
    for (let t = -zmax; t <= zmax; t += 2) txt(svg, sx(t), h - m.b + 16, t, { class: "t-axis", "text-anchor": "middle" });
    [-X.bonferroni_z, X.bonferroni_z].forEach((z) => el("line", { x1: sx(z), x2: sx(z), y1: m.t, y2: h - m.b, style: "stroke:var(--muted);stroke-dasharray:3 4" }, svg));
    txt(svg, sx(X.bonferroni_z) + 4, m.t + 10, "significant", { class: "t-axis" });
    txt(svg, (m.l + w - m.r) / 2, h - 6, w < 520 ? "in-sample z-score" : "in-sample z-score (effect relative to its noise)", { class: "t-axis", "text-anchor": "middle" });
    txt(svg, 0, 0, h < 380 ? "gain on unseen seasons" : "forecast gain on unseen seasons (milli log loss)", { class: "t-axis", "text-anchor": "middle", transform: `translate(11 ${(m.t + h - m.b) / 2}) rotate(-90)` });
    pts.slice().sort((a, b) => (a.cat === "gray") - (b.cat === "gray")).reverse().forEach((p) => {
      const c = el("circle", { cx: sx(p.z), cy: sy(p.gain), r: p.holds ? 6.5 : 5, style: `fill:${COLOR[p.cat]};stroke:var(--surface);stroke-width:2` }, svg);
      hover(c, () => `<b>${nice(p.feature)}</b><br>${p.family}<br>z ${sgn(p.z, 1)} in-sample<br>forecast gain ${sgn(p.gain)} thousandths [${sgn(-p.d_logloss_ci[1] * 1000)}, ${sgn(-p.d_logloss_ci[0] * 1000)}]`);
    });
    const labeled = pts.filter((p) => p.holds || ["home_alt_km", "d_def_fg3_pct", "away_b2b"].includes(p.feature));
    labeled.forEach((p) => { const right = sx(p.z) < w * 0.7; txt(svg, sx(p.z) + (right ? 10 : -10), sy(p.gain) + (p.feature === "d_def_fg3_pct" ? -9 : p.feature === "home_alt_km" ? 16 : 4), nice(p.feature), { class: "t-lab", "text-anchor": right ? "start" : "end", style: "font-size:11.5px" }); });
  });
  dtable("d-scatter", ["Factor", "Family", "z", "Gain (milli log loss)"], pts.slice(0, 20).map((p) => [nice(p.feature), p.family, p.z.toFixed(1), p.gain.toFixed(2)]));
  const e = X.era_confound;
  setHTML("n-era", `Raw combined pace looked predictive (z ${e.z_without_era_control.toFixed(1)}) until the league's recent home-win rate was added: faster eras were also eras with weaker home court. With that control it drops to z ${e.z_with_era_control.toFixed(1)} and adds nothing on new seasons, so the model uses pace relative to the league.`);

  /* 4: memory */
  const ew = X.memory.filter((m) => m.halflife_games), elo = X.memory.find((m) => m.signal === "elo_diff"), std = X.memory.find((m) => m.signal === "d_net_rtg"), best = ew.reduce((a, b) => (b.logloss < a.logloss ? b : a));
  setHTML("t-memory", `A rating that weights recent games with a half-life of ${best.halflife_games} games predicts best among season-only ratings (log loss ${best.logloss.toFixed(3)}). Two or three games of memory chase noise (${ew[0].logloss.toFixed(3)}); the full season reacts a little slowly (${std.logloss.toFixed(3)}). Elo, which carries last season forward, beats all of them (${elo.logloss.toFixed(3)}).`);
  legend("l-memory", [["s2", "Recency-weighted net rating", ""], ["s1", "Season-to-date net rating", ""], ["s3", "Elo, carries over across seasons", ""]]);
  mount("c-memory", 300, (svg, w, h) => {
    const m = { l: 52, r: 16, t: 14, b: 40 }, ys = [...ew.map((e2) => e2.logloss + e2.se * 0), elo.logloss, std.logloss], y0 = Math.min(...ys) - 0.004, y1 = Math.max(...ys) + 0.004;
    const sx = lin(Math.log(2), Math.log(80), m.l, w - m.r - 6), sy = lin(y0, y1, h - m.b, m.t);
    for (let t = Math.ceil(y0 * 100) / 100; t <= y1; t += 0.01) { el("line", { x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), class: "grid-line" }, svg); txt(svg, m.l - 6, sy(t) + 4, t.toFixed(2), { class: "t-axis", "text-anchor": "end" }); }
    ew.forEach((p) => txt(svg, sx(Math.log(p.halflife_games)), h - m.b + 16, p.halflife_games, { class: "t-axis", "text-anchor": "middle" }));
    txt(svg, (m.l + w - m.r) / 2, h - 6, "memory half-life, in games", { class: "t-axis", "text-anchor": "middle" });
    [[elo, "s3", "Elo"], [std, "s1", "season-to-date"]].forEach(([r, c, l]) => { el("line", { x1: m.l, x2: w - m.r, y1: sy(r.logloss), y2: sy(r.logloss), style: `stroke:${COLOR[c]};stroke-width:2;stroke-dasharray:6 4` }, svg); txt(svg, w - m.r - 4, sy(r.logloss) + (c === "s3" ? 14 : -6), l, { class: "t-lab", "text-anchor": "end" }); });
    el("path", { d: ew.map((p, i) => `${i ? "L" : "M"}${sx(Math.log(p.halflife_games))} ${sy(p.logloss)}`).join(""), style: "fill:none;stroke:var(--s2);stroke-width:2.5" }, svg);
    ew.forEach((p) => { const c = el("circle", { cx: sx(Math.log(p.halflife_games)), cy: sy(p.logloss), r: p === best ? 7 : 4.5, style: "fill:var(--s2);stroke:var(--surface);stroke-width:2" }, svg); hover(c, () => `<b>Half-life ${p.halflife_games} games</b><br>log loss ${p.logloss.toFixed(4)} (SE ${p.se.toFixed(4)})`); });
    txt(svg, sx(Math.log(best.halflife_games)), sy(best.logloss) - 14, "best", { class: "t-val", "text-anchor": "middle" });
  });
  dtable("d-memory", ["Signal", "Log loss", "SE"], X.memory.map((m) => [m.halflife_games ? `half-life ${m.halflife_games}` : m.signal, m.logloss.toFixed(4), m.se.toFixed(4)]));

  /* 5: skill or luck */
  const P = X.persistence, p3 = P.find((p) => p.stat === "fg3_pct"), pd3 = P.find((p) => p.stat === "def_fg3_pct"), pr3 = P.find((p) => p.stat === "fg3a_rate");
  setHTML("t-luck", `Split-half reliability compares a team's odd and even games within a season. Three-point attempt rate barely moves (${pr3.split_half.toFixed(2)}), because it is a choice. Three-point accuracy is less stable (${p3.split_half.toFixed(2)}). The three-point percentage a defense allows is mostly noise: ${pd3.split_half.toFixed(2)} within a season and ${pd3.year_over_year.toFixed(2)} from one year to the next.`);
  legend("l-luck", [["s2", "Split-half, same season"], ["s1", "Year over year", "ring"]]);
  mount("c-luck", P.length * 26 + 40, (svg, w) => {
    const narrow = w < 480, lw = narrow ? w * 0.56 : Math.min(230, w * 0.46), sx = lin(0, 1, lw, w - 18);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { el("line", { x1: sx(t), x2: sx(t), y1: 4, y2: P.length * 26 + 4, class: "grid-line" }, svg); txt(svg, sx(t), P.length * 26 + 20, t.toFixed(2).replace(/\.?0+$/, "") || "0", { class: "t-axis", "text-anchor": "middle" }); });
    P.forEach((p, i) => {
      const y = 16 + i * 26, luck = p.split_half < 0.7;
      txt(svg, 4, y + 4, narrow ? p.label.replace("Opponent", "Opp.") : p.label, { class: "t-lab", style: (luck ? "font-weight:600;fill:var(--ink);" : "") + (narrow ? "font-size:11.5px" : "") });
      el("path", { d: `M${sx(p.year_over_year)} ${y}H${sx(p.split_half)}`, style: "stroke:var(--line);stroke-width:3" }, svg);
      const a = el("circle", { cx: sx(p.split_half), cy: y, r: 5.5, style: "fill:var(--s2);stroke:var(--surface);stroke-width:2" }, svg);
      const b = el("circle", { cx: sx(p.year_over_year), cy: y, r: 5, style: "fill:var(--surface);stroke:var(--s1);stroke-width:2.5" }, svg);
      [a, b].forEach((n) => hover(n, () => `<b>${p.label}</b><br>split-half ${p.split_half.toFixed(2)}<br>year over year ${p.year_over_year.toFixed(2)}`));
    });
  });
  dtable("d-luck", ["Stat", "Split-half", "Year over year"], P.map((p) => [p.label, p.split_half.toFixed(2), p.year_over_year.toFixed(2)]));

  /* 6: opening week */
  const E = X.early_season, e1 = E[0], e3 = E.find((b) => b.bucket === "11-20");
  setHTML("t-early", `In each team's first five games, Elo picks ${pct(e1.acc_elo, 1)} correctly, against ${pct(e1.acc_record, 1)} for the current record and ${pct(e1.acc_home, 1)} for the home team (${e1.n_games} test games). By games 11 to 20 the record has caught up (${pct(e3.acc_record, 1)} against ${pct(e3.acc_elo, 1)}).`);
  legend("l-early", [["s3", "Elo (remembers last season)"], ["s1", "This season's record"], ["gray", "Always the home team"]]);
  mount("c-early", 280, (svg, w, h) => lineChart(svg, w, h, { xs: E.map((b) => b.bucket), y: [0.45, 0.75], ticks: [0.5, 0.6, 0.7], fmt: (v) => pct(v, 0), every: 1,
    series: [{ name: "Elo", c: "s3", vals: E.map((b) => b.acc_elo) }, { name: "Record", c: "s1", vals: E.map((b) => b.acc_record) }, { name: "Home team", c: "gray", vals: E.map((b) => b.acc_home) }], markers: true, vfmt: (v) => pct(v, 1), caption: "games played this season by the less-experienced team" }));
  dtable("d-early", ["Games played", "n", "Home", "Elo", "Record"], E.map((b) => [b.bucket, b.n_games, pct(b.acc_home), pct(b.acc_elo), pct(b.acc_record)]));

  /* 7: home court */
  const H = X.home_court, T = H.teams, top = T.slice(0, 3), bot = T[T.length - 1];
  const pre = X.trends.filter((t) => t.SEASON < "2019-20"), post = X.trends.filter((t) => t.SEASON >= "2019-20"), avg = (a, k) => a.reduce((s, t) => s + t[k], 0) / a.length;
  setHTML("t-home", `After adjusting for team strength, playing at home is worth ${H.league_avg_points.toFixed(1)} points a game. ${top.map((t) => t.team).join(", ")} lead the table and ${bot.team} trails it (${sgn(bot.hca, 1)}). Each estimate carries about 0.4 points of standard error, so only the ends of the table are clearly different. Home teams won ${pct(avg(pre, "home_win_rate"), 0)} of games through 2018-19 and ${pct(avg(post, "home_win_rate"), 0)} since.`);
  const ALT = { DEN: "5,280 ft", UTA: "4,226 ft" };
  mount("c-hca", T.length * 21 + 40, (svg, w) => {
    const lw = 44, hi = Math.max(...T.map((t) => t.hca + 1.96 * t.se)) + 0.2, lo = Math.min(...T.map((t) => t.hca - 1.96 * t.se)) - 0.2, sx = lin(lo, hi, lw, w - 60);
    for (let t = Math.ceil(lo); t <= hi; t++) { el("line", { x1: sx(t), x2: sx(t), y1: 4, y2: T.length * 21 + 6, class: "grid-line" }, svg); txt(svg, sx(t), T.length * 21 + 22, t, { class: "t-axis", "text-anchor": "middle" }); }
    el("line", { x1: sx(H.league_avg_points), x2: sx(H.league_avg_points), y1: 4, y2: T.length * 21 + 6, style: "stroke:var(--ink2);stroke-dasharray:4 4;stroke-width:1.5" }, svg);
    txt(svg, sx(H.league_avg_points) + 4, T.length * 21 + 38, `league average ${H.league_avg_points.toFixed(1)}`, { class: "t-axis" });
    T.forEach((t, i) => {
      const y = 14 + i * 21;
      el("circle", { cx: 17, cy: y, r: 9.5, style: "fill:#f4f3ef" }, svg); el("image", { href: `logos/${t.team}.svg`, x: 10, y: y - 7, width: 14, height: 14 }, svg); el("title", {}, svg.lastChild).textContent = t.team;
      el("path", { d: `M${sx(t.hca - 1.96 * t.se)} ${y}H${sx(t.hca + 1.96 * t.se)}`, style: "stroke:var(--s2);stroke-width:2;opacity:.55" }, svg);
      const c = el("circle", { cx: sx(t.hca), cy: y, r: 5.5, style: "fill:var(--s2);stroke:var(--surface);stroke-width:2" }, svg);
      if (ALT[t.team]) txt(svg, sx(t.hca + 1.96 * t.se) + 8, y + 4, ALT[t.team], { class: "t-axis" });
      hover(c, () => `<b>${t.team}</b><br>${t.hca.toFixed(2)} points (SE ${t.se.toFixed(2)})<br>${t.n_games.toLocaleString()} home games`);
    });
  });
  dtable("d-hca", ["Franchise", "Points", "SE", "Games"], T.map((t) => [t.team, t.hca.toFixed(2), t.se.toFixed(2), t.n_games]));
  mount("c-homerate", 260, (svg, w, h) => lineChart(svg, w, h, { xs: seasons, y: [0.5, 0.66], ticks: [0.5, 0.55, 0.6, 0.65], fmt: (v) => pct(v, 0), every: 5, rot: true,
    series: [{ name: "Home win rate", c: "s2", vals: X.trends.map((t) => t.home_win_rate) }], markers: true, vfmt: (v) => pct(v, 1), shade: [seasons.indexOf("2019-20"), seasons.indexOf("2020-21"), "bubble, empty arenas"] }));
  dtable("d-homerate", ["Season", "Home win rate"], X.trends.map((t) => [t.SEASON, pct(t.home_win_rate)]));

  /* 8: the game changed */
  const trendDefs = [["fg3a_per_game", "Threes attempted per team", (v) => v.toFixed(1)], ["pace", "Possessions per game", (v) => v.toFixed(1)], ["orb_rate", "Offensive rebound rate", (v) => pct(v, 1)], ["favorite_win_rate", "Favorite wins (by Elo)", (v) => pct(v, 1)]];
  setHTML("t-trends", `Twenty-five years ago a team took <b>${first("fg3a_per_game").toFixed(0)}</b> threes a night; now it takes <b>${last("fg3a_per_game").toFixed(0)}</b>. Pace is up ${((last("pace") / first("pace") - 1) * 100).toFixed(0)}%, offensive rebounding is down from ${pct(first("orb_rate"), 0)} to ${pct(last("orb_rate"), 0)}, and the better team now wins a bit more often (${pct(first("favorite_win_rate"), 0)} then, ${pct(last("favorite_win_rate"), 0)} now). Any model fit across eras has to respect that the sport it is describing keeps moving.`);
  setHTML("trends", trendDefs.map(([k, title, f]) => `<div class="card"><h3>${title}</h3><p class="sub">${f(first(k))} to <b style="color:var(--ink)">${f(last(k))}</b></p><div id="m-${k}" data-label="${title} by season"></div></div>`).join(""));
  trendDefs.forEach(([k, title, f]) => mount(`m-${k}`, 96, (svg, w, h) => lineChart(svg, w, h, { xs: seasons, mini: true, y: [Math.min(...X.trends.map((t) => t[k])) * 0.98, Math.max(...X.trends.map((t) => t[k])) * 1.02], series: [{ name: title, c: "s2", vals: X.trends.map((t) => t[k]) }], vfmt: f })));

  /* 9: walk-forward */
  const wfNames = { "Baseline: home team wins": ["Home team", "gray"], "Baseline: better season-to-date record wins": ["Better record", "s1"], "Logistic regression (four factors + rest only)": ["Four-factor model", "s2"] };
  const wfSeasons = [...new Set(M.walk_forward.map((r) => r.season))].sort();
  const wfSeries = Object.entries(wfNames).map(([m, [name, c]]) => ({ name, c, vals: wfSeasons.map((s) => M.walk_forward.find((r) => r.season === s && r.model === m).accuracy) }));
  const diffs = wfSeasons.map((s, i) => wfSeries[2].vals[i] - wfSeries[1].vals[i]), nS = diffs.length, wins = diffs.filter((d) => d > 0).length, gap = diffs.reduce((a, b) => a + b, 0) / nS;
  const sdD = Math.sqrt(diffs.reduce((a, d) => a + (d - gap) ** 2, 0) / (nS - 1)), tcrit = { 20: 2.086 }[nS - 1] || 1.96, half = tcrit * sdD / Math.sqrt(nS);
  const choose = (n, k) => { let r = 1; for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i; return r; };
  const signP = Math.min(1, 2 * Array.from({ length: nS - wins + 1 }, (_, k) => choose(nS, k)).reduce((a, b) => a + b, 0) / 2 ** nS);
  setHTML("t-wf", `Each season is predicted by models trained only on the seasons before it. The four-factor model beats "better record wins" in ${wins} of ${wfSeasons.length} seasons, by ${(gap * 100).toFixed(1)} points on average (95% interval ${((gap - half) * 100).toFixed(1)} to ${((gap + half) * 100).toFixed(1)}; sign test p = ${signP < 0.01 ? signP.toFixed(3) : signP.toFixed(2)}). Seasons are treated as independent and this comparison was picked after looking. No season is predicted much better than 70%.`);
  legend("l-wf", [["gray", "Home team"], ["s1", "Better record"], ["s2", "Four-factor model"]]);
  mount("c-wf", 300, (svg, w, h) => lineChart(svg, w, h, { xs: wfSeasons, y: [0.52, 0.74], ticks: [0.55, 0.6, 0.65, 0.7], fmt: (v) => pct(v, 0), every: 4, rot: true, series: wfSeries, markers: true, vfmt: (v) => pct(v, 1), direct: true }));
  dtable("d-wf", ["Season", ...wfSeries.map((s) => s.name)], wfSeasons.map((s, i) => [s, ...wfSeries.map((r) => pct(r.vals[i]))]));

  /* ---------- Act II: style or substance ---------- */
  const S = M.style, AT = S.atlas, A = Object.fromEntries(AT.map((r) => [r.key, r])), BA = S.blocks_all_seasons, BT = S.blocks_tracking_era;
  const R2 = (d) => `${(d.r2 * 100).toFixed(0)}%`;
  setHTML("t-act2", `A different question, asked of whole seasons: do the ways teams choose to play (shot locations, pace, drives, passing) explain winning, or only how well they execute? ${S.n_metrics} metrics for ${S.n_team_seasons} team-seasons, each compared only with its own season so league-wide trends cannot pose as advantages. Shot zones and advanced stats cover 2000-01 on, player tracking 2013-14 on, hustle stats 2016-17 on.`);

  const sty = BT.sets["Style (choices)"], eff = BT.sets["Effort (hustle, speed)"], exe = BT.sets["Execution (results)"], all = BT.sets.Everything, dive = BA.sets["Style (choices)"];
  const blk = [
    { label: "Shot diet: zones, three-point rate, pace", sub: `${dive.n_metrics} metrics, all ${BA.n_seasons} seasons`, d: dive.win, c: "s1" },
    { label: "All measurable style: plus drives, touches, passing", sub: `${sty.n_metrics} metrics, tracking era`, d: sty.win, c: "s1" },
    { label: "Hustle and speed", sub: `${eff.n_metrics} metrics, tracking era`, d: eff.win, c: "s3" },
    { label: "Execution: shooting, turnovers, rebounds, what defenses allow", sub: `${exe.n_metrics} metrics, tracking era`, d: exe.win, c: "s2" },
    { label: "Everything together", sub: `${all.n_metrics} metrics`, d: all.win, c: "gray" },
    { label: "Net rating alone", sub: "one number", d: BT.net_rating_alone, c: "gray" },
  ];
  const bn = BT.beyond_net_rating.Everything, dm = S.dimension;
  setHTML("t-blocks", `Shot diet alone (zones, three-point rate, pace) explains ${R2(dive.win)} of the differences in win % within a season. Every style signal in the tracking data together explains ${R2(sty.win)}; hustle and speed, ${R2(eff.win)}. Results (shooting %, turnovers, rebounds, what the defense allows) explain ${R2(exe.win)}, largely by construction, since they are what net rating is made of.`);
  setHTML("n-blocks", `Net rating alone explains ${R2(BT.net_rating_alone)} of win %. Adding all ${all.n_metrics} other metrics explains ${(bn.r2 * 100).toFixed(1)}% of what remains (95% interval ${(bn.ci[0] * 100).toFixed(1)} to ${(bn.ci[1] * 100).toFixed(1)}%). The ${dm.n_metrics} metrics behave like about ${Math.round(dm.effective_rank)} independent measurements; most restate each other.`);
  legend("l-blocks", [["s1", "Style: choices", "sq"], ["s3", "Effort", "sq"], ["s2", "Execution: results", "sq"], ["gray", "Reference", "sq"]]);
  mount("c-blocks", blk.length * 58 + 44, (svg, w) => {
    const L = 6, R = w - 52, sx = lin(0, 1, L, R), H = blk.length * 58;
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => { el("line", { x1: sx(t), x2: sx(t), y1: 4, y2: H + 2, class: "grid-line" }, svg); txt(svg, sx(t), H + 18, pct(t, 0), { class: "t-axis", "text-anchor": "middle" }); });
    txt(svg, R, H + 36, "share of win % explained on seasons the model never saw", { class: "t-axis", "text-anchor": "end" });
    blk.forEach((r, i) => {
      const y = 8 + i * 58, bar = el("path", { d: barPath(L, y + 24, Math.max(2, sx(r.d.r2) - L), 18), style: `fill:${COLOR[r.c]}` }, svg);
      txt(svg, L, y + 14, r.label, { class: "t-lab", style: w < 480 ? "font-size:11.5px" : "" });
      const [a, b] = r.d.ci; el("path", { d: `M${sx(a)} ${y + 33}H${sx(b)}M${sx(a)} ${y + 28}V${y + 38}M${sx(b)} ${y + 28}V${y + 38}`, style: "stroke:var(--ink);stroke-width:1.5;fill:none" }, svg);
      txt(svg, sx(b) + 8, y + 38, R2(r.d), { class: "t-val" });
      hover(bar, () => `<b>${r.label}</b><br>${r.sub}<br>${(r.d.r2 * 100).toFixed(1)}% explained [${(a * 100).toFixed(0)}%, ${(b * 100).toFixed(0)}%]`);
    });
  });
  dtable("d-blocks", ["Block", "Metrics", "R-squared", "Low", "High"], blk.map((r) => [r.label, r.sub, pct(r.d.r2, 0), pct(r.d.ci[0], 0), pct(r.d.ci[1], 0)]));
  const real = AT.filter((r) => r.beats_chance && r.role !== "execution"), li = (r) => `<li><span>${r.label}</span><b>${sgn(r.r_win)}</b></li>`;
  setHTML("up", real.filter((r) => r.r_win > 0).slice(0, 6).map(li).join("")); setHTML("down", real.filter((r) => r.r_win < 0).slice(0, 6).map(li).join(""));

  /* 11: the explorer (plain HTML so it can be searched, sorted and read by a screen reader) */
  const ROLE = { style: ["Style: a choice", "var(--s1)"], execution: ["Execution: a result", "var(--s2)"], effort: ["Effort", "var(--s3)"], "pre-game": ["Known before tip-off", "var(--s1)"] };
  const seasonRows = AT.map((r) => ({ id: r.key, name: r.label, family: r.family, role: r.role, def: r.definition, v: r.r_win, lo: r.ci_low, hi: r.ci_high, band: r.chance_ceiling, real: r.beats_chance,
    stat: `r ${sgn(r.r_win)} [${sgn(r.ci_low)}, ${sgn(r.ci_high)}], chance ceiling ${r.chance_ceiling.toFixed(2)}, ${r.n} team-seasons from ${r.first_season}` }));
  const gameRows = pts.map((r) => ({ id: r.feature, name: nice(r.feature), family: r.family, role: "pre-game", def: r.definition, v: r.gain, lo: -r.d_logloss_ci[1] * 1000, hi: -r.d_logloss_ci[0] * 1000, real: r.holds,
    stat: `forecast gain ${sgn(r.gain)} thousandths of log loss [${sgn(-r.d_logloss_ci[1] * 1000)}, ${sgn(-r.d_logloss_ci[0] * 1000)}], in-sample z ${sgn(r.z, 1)}` }));
  const tabs = { season: { rows: seasonRows, scale: 0.8, fmt: (v) => sgn(v), help: "Bars show correlation with win % within the season. The gray band is what chance alone produces; the thin line is the 95% interval (whole seasons resampled).", roles: true },
                 game: { rows: gameRows, scale: Math.max(...gameRows.map((r) => Math.max(Math.abs(r.lo), Math.abs(r.hi)))) * 1.05, fmt: (v) => sgn(v, 1), help: "Bars show the forecast gain on three unseen seasons, in thousandths of log loss (right of the line helps). Team strength, Elo and the era are already in the baseline, so these are extras.", roles: false } };
  const st = { tab: "season" }, $q = $("#ex-q"), $f = $("#ex-family"), $r = $("#ex-role"), $s = $("#ex-sort"), $c = $("#ex-real");
  setHTML("t-explorer", `All ${seasonRows.length} season metrics and ${gameRows.length} pre-game factors, with definitions. Filter by family or by choice versus result, search by name, or keep only what clears the chance threshold.`);
  const opts = (a, all) => `<option value="">${all}</option>` + a.map((x) => `<option value="${x[0]}">${x[1]}</option>`).join("");
  $s.innerHTML = opts([], "Strongest effect first").replace('value=""', 'value="effect"') + '<option value="name">A to Z</option><option value="family">By family</option>'; $s.value = "effect";
  function setupTab(t) {
    st.tab = t; const T = tabs[t];
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b.id === "tab-" + t));
    $f.innerHTML = opts([...new Set(T.rows.map((r) => r.family))].map((f) => [f, f]), "All families");
    $r.innerHTML = opts(Object.entries(ROLE).filter(([k]) => k !== "pre-game").map(([k, v]) => [k, v[0]]), "Style, execution and effort"); $r.hidden = !T.roles; $r.value = "";
    render();
  }
  function render() {
    const T = tabs[st.tab], q = $q.value.trim().toLowerCase();
    let rows = T.rows.filter((r) => (!$f.value || r.family === $f.value) && (!$r.value || r.role === $r.value) && (!$c.checked || r.real) && (!q || `${r.name} ${r.family} ${r.def} ${r.id}`.toLowerCase().includes(q)));
    rows.sort($s.value === "name" ? (a, b) => a.name.localeCompare(b.name) : $s.value === "family" ? (a, b) => a.family.localeCompare(b.family) || Math.abs(b.v) - Math.abs(a.v) : (a, b) => Math.abs(b.v) - Math.abs(a.v));
    const pos = (x) => 50 + (x / T.scale) * 50;
    setHTML("ex-count", `Showing ${rows.length} of ${T.rows.length}. ${T.help}`);
    setHTML("ex-rows", rows.length ? rows.map((r) => {
      const [rl, rc] = ROLE[r.role], col = st.tab === "game" ? (r.real ? "var(--s3)" : "var(--gray)") : rc, a = Math.min(pos(0), pos(r.v)), wd = Math.abs(pos(r.v) - pos(0));
      return `<div class="xr${r.real ? "" : " dim"}" role="listitem"><div><div class="nm">${r.name}</div><div class="df">${r.def}</div><div class="meta"><i class="role" style="background:${rc}"></i>${rl} &middot; ${r.family}${r.real ? " &middot; <b>clears the chance bar</b>" : ""}<br>${r.stat}</div></div>` +
        `<div class="bar" aria-hidden="true">${r.band ? `<i class="band" style="left:${pos(-r.band)}%;width:${pos(r.band) - pos(-r.band)}%"></i>` : ""}<i class="zero"></i><i class="fill" style="left:${a}%;width:${wd}%;background:${col}"></i><i class="ci" style="left:${pos(r.lo)}%;width:${pos(r.hi) - pos(r.lo)}%"></i><span class="v">${T.fmt(r.v)}</span></div></div>`;
    }).join("") : `<p class="sub">Nothing matches. Clear the search or uncheck the filter.</p>`);
  }
  [$q, $f, $r, $s, $c].forEach((n) => n.addEventListener("input", render));
  $("#tab-season").addEventListener("click", () => setupTab("season")); $("#tab-game").addEventListener("click", () => setupTab("game"));
  setupTab("season");

  /* 12: the three-point edge over time */
  const EG = S.edge, edgeKeys = [["fg3a_rate", "s2", "3PA rate"], ["mid_share", "s1", "Mid-range"], ["rim_share", "s3", "Rim"], ["pace", "gray", "Pace"]], g3 = EG.fg3a_rate.rolling5, gm = EG.mid_share.rolling5;
  const peak = g3.reduce((a, b) => (b.r > a.r ? b : a)), lastE = g3[g3.length - 1], midLo = gm.reduce((a, b) => (b.r < a.r ? b : a)), midNow = gm[gm.length - 1];
  setHTML("t-edge", `Over five-season windows, the correlation between a team's three-point rate and its net rating rose to ${sgn(peak.r)} (window ending ${peak.season}) and has fallen to ${sgn(lastE.r)} (${lastE.season}).${lastE.lo <= 0 ? " The latest interval includes zero." : ""} Once most teams shoot threes, shooting more of them separates teams less. Mid-range share moved the other way, from ${sgn(midLo.r)} (${midLo.season}) to ${sgn(midNow.r)}. Single windows are noisy and the bands are optimistic.`);
  legend("l-edge", edgeKeys.map(([, c, l]) => [c, l]));
  const exs = g3.map((r) => r.season);
  mount("c-edge", 300, (svg, w, h) => lineChart(svg, w, h, { xs: exs, y: [-0.4, 0.5], ticks: [-0.3, -0.15, 0, 0.15, 0.3, 0.45], fmt: (v) => sgn(v, 2), every: 3, rot: true, direct: true, vfmt: (v) => sgn(v, 2), band: { lo: g3.map((r) => r.lo), hi: g3.map((r) => r.hi), c: "s2" },
    series: edgeKeys.map(([k, c, name]) => ({ name, c, vals: EG[k].rolling5.map((r) => r.r) })) }));
  dtable("d-edge", ["Window ending", ...edgeKeys.map((k) => k[2])], exs.map((s2, i) => [s2, ...edgeKeys.map(([k]) => sgn(EG[k].rolling5[i].r))]));

  /* 13: drives */
  const DR = S.drives, mean = (a) => a.reduce((x, y) => x + y, 0) / a.length, mx = mean(DR.map((p) => p.drives_z)), my = mean(DR.map((p) => p.win));
  const sxy = DR.reduce((a, p) => a + (p.drives_z - mx) * (p.win - my), 0), sxx = DR.reduce((a, p) => a + (p.drives_z - mx) ** 2, 0), syy = DR.reduce((a, p) => a + (p.win - my) ** 2, 0), slope = sxy / sxx, rD = sxy / Math.sqrt(sxx * syy);
  setHTML("t-drives", `Across ${DR.length} team-seasons since 2013-14, drive volume and win % correlate at ${sgn(rD)}: teams that drive more than their rivals win slightly less. Finishing is what tracks winning, with drive FG% at ${sgn(A.drive_fg.r_win)} and points per drive at ${sgn(A.drive_pts_per.r_win)}.`);
  mount("c-drives", (w) => (w < 520 ? 320 : 380), (svg, w, h) => {
    const m = { l: 48, r: 14, t: 12, b: 40 }, sx = lin(-3, 3, m.l, w - m.r), sy = lin(0.1, 0.9, h - m.b, m.t);
    [0.2, 0.35, 0.5, 0.65, 0.8].forEach((t) => { el("line", { x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), class: t === 0.5 ? "zero" : "grid-line" }, svg); txt(svg, m.l - 6, sy(t) + 4, pct(t, 0), { class: "t-axis", "text-anchor": "end" }); });
    [-2, -1, 0, 1, 2].forEach((t) => txt(svg, sx(t), h - m.b + 16, t > 0 ? "+" + t : t, { class: "t-axis", "text-anchor": "middle" }));
    txt(svg, (m.l + w - m.r) / 2, h - 6, w < 520 ? "drives per 100, SD vs. league that season" : "drives per 100 possessions, standard deviations from that season's league average", { class: "t-axis", "text-anchor": "middle" });
    txt(svg, 0, 0, "win %", { class: "t-axis", "text-anchor": "middle", transform: `translate(11 ${(m.t + h - m.b) / 2}) rotate(-90)` });
    DR.forEach((p) => { const c = el("circle", { cx: sx(Math.max(-3, Math.min(3, p.drives_z))), cy: sy(p.win), r: 4.5, style: "fill:var(--s1);opacity:.5" }, svg);
      hover(c, () => `<b>${p.team === "Charlotte Bobcats" ? "Charlotte Hornets" : p.team}, ${p.season}</b><br>drives ${sgn(p.drives_z, 1)} SD vs league<br>win % ${pct(p.win, 0)}<br>drive FG% ${pct(p.drive_fg, 0)}`); });
    el("path", { d: `M${sx(-2.6)} ${sy(my + slope * (-2.6 - mx))}L${sx(2.6)} ${sy(my + slope * (2.6 - mx))}`, style: "stroke:var(--s2);stroke-width:3;fill:none" }, svg);
    txt(svg, sx(2.6) - 6, sy(my + slope * (2.6 - mx)) - 12, `r ${sgn(rD)}`, { class: "t-val", "text-anchor": "end" });
  });
  dtable("d-drives", ["Metric", "r with win %", "95% interval", "Beats chance"], ["drives_100", "drive_fg", "drive_pts_per", "drive_pass_pct", "drive_tov_pct", "drive_pf_pct"].map((k) => [A[k].label, sgn(A[k].r_win), `${sgn(A[k].ci_low)} to ${sgn(A[k].ci_high)}`, A[k].beats_chance ? "yes" : "no"]));
  setHTML("n-drives", `Season data cannot say why. One plausible reading is that offenses with fewer good options drive more, in which case telling a team to drive less would not make it better.`);

  /* 14: materials */
  setHTML("t-materials", `The atlas has ${S.n_metrics} metrics with definitions, ready for a spreadsheet or a notebook. Everything on this page, including the pipeline that fetches the data, is reproducible from the repository: <code>uv run python -m nbawin.run</code> rebuilds every number in about four minutes.`);
  setHTML("n-materials", `<b>What this cannot tell you.</b> These are season-level correlations explaining a finished season, not causes and not forecasts. The ${S.n_metrics} rows are about ${Math.round(dm.effective_rank)} independent ideas, not ${S.n_metrics} separate findings, and the chance bar already accounts for testing them all at once. Tracking starts in 2013-14, hustle in 2016-17, so those rows rest on fewer seasons. Style metrics are not free of results (a drive that ends in a pass still needs a shot to follow), which is why the style/execution split is a gradient, not a wall.`);
}

/* shared line chart: crosshair tooltip, optional direct labels, shaded band, mini mode */
function lineChart(svg, w, h, o) {
  const mini = !!o.mini, n = o.xs.length;
  const direct = o.direct && w > 520;
  const m = mini ? { l: 4, r: 6, t: 8, b: 6 } : { l: 46, r: direct ? 118 : 16, t: 14, b: o.rot ? 46 : o.caption ? 44 : 28 };
  const X = (i) => m.l + (n === 1 ? 0 : (i / (n - 1))) * (w - m.l - m.r), [y0, y1] = o.y, Y = (v) => h - m.b - ((v - y0) / (y1 - y0)) * (h - m.t - m.b);
  if (!mini) {
    (o.ticks || []).forEach((t) => { el("line", { x1: m.l, x2: w - m.r, y1: Y(t), y2: Y(t), class: t === 0 ? "zero" : "grid-line" }, svg); txt(svg, m.l - 6, Y(t) + 4, o.fmt(t), { class: "t-axis", "text-anchor": "end" }); });
    o.xs.forEach((x, i) => { if (i % (o.every || 1) === 0 || i === n - 1 && n < 8) { const t = txt(svg, X(i), h - m.b + 16, o.rot ? x : x, { class: "t-axis", "text-anchor": o.rot ? "end" : "middle" }); if (o.rot) t.setAttribute("transform", `rotate(-40 ${X(i)} ${h - m.b + 16})`); } });
    if (o.caption) txt(svg, (m.l + w - m.r) / 2, h - 4, o.caption, { class: "t-axis", "text-anchor": "middle" });
  }
  if (o.shade) { const [a, b, label] = o.shade; el("rect", { x: X(a) - 6, y: m.t, width: X(b) - X(a) + 12, height: h - m.t - m.b, style: "fill:var(--wood);opacity:.18" }, svg); txt(svg, X(a) - 10, m.t + 12, label, { class: "t-axis", "text-anchor": "end" }); }
  if (o.band) el("path", { d: o.band.hi.map((v, i) => `${i ? "L" : "M"}${X(i)} ${Y(v)}`).join("") + o.band.lo.map((v, i) => `L${X(n - 1 - i)} ${Y(o.band.lo[n - 1 - i])}`).join("") + "Z", style: `fill:${COLOR[o.band.c]};opacity:.14` }, svg);
  o.series.forEach((s) => {
    el("path", { d: s.vals.map((v, i) => `${i ? "L" : "M"}${X(i)} ${Y(v)}`).join(""), style: `fill:none;stroke:${COLOR[s.c]};stroke-width:${mini ? 2.2 : 2.5};stroke-linejoin:round` }, svg);
    if (o.markers) s.vals.forEach((v, i) => el("circle", { cx: X(i), cy: Y(v), r: n > 12 ? 2.8 : 4.5, style: `fill:${COLOR[s.c]};stroke:var(--surface);stroke-width:1.5` }, svg));
  });
  if (mini) { const a = o.series[0].vals; [[0, "start"], [n - 1, "end"]].forEach(([i, anchor]) => el("circle", { cx: X(i), cy: Y(a[i]), r: 4, style: "fill:var(--s2);stroke:var(--surface);stroke-width:2" }, svg)); }
  if (direct) {
    const ends = o.series.map((s) => ({ s, y: Y(s.vals[n - 1]) })).sort((a, b) => a.y - b.y);
    ends.forEach((e, i) => { if (i && e.y - ends[i - 1].y < 14) e.y = ends[i - 1].y + 14; txt(svg, w - m.r + 8, e.y + 4, `${e.s.name} ${o.vfmt(e.s.vals[n - 1])}`, { class: "t-lab", style: "font-size:11.5px" }); });
  }
  const cross = el("line", { y1: m.t, y2: h - m.b, style: "stroke:var(--ink2);stroke-width:1;opacity:0" }, svg), dots = o.series.map((s) => el("circle", { r: 5, style: `fill:${COLOR[s.c]};stroke:var(--surface);stroke-width:2;opacity:0` }, svg));
  const hit = el("rect", { x: m.l, y: 0, width: w - m.l - m.r, height: h, style: "fill:transparent;cursor:crosshair;touch-action:pan-y" }, svg);
  const at = (e) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left - m.l) / (w - m.l - m.r)) * (n - 1)))); };
  const draw = (e) => {
    const i = at(e); cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.style.opacity = 1;
    dots.forEach((d, k) => { d.setAttribute("cx", X(i)); d.setAttribute("cy", Y(o.series[k].vals[i])); d.style.opacity = 1; });
    showTip(`<b>${o.xs[i]}</b>` + o.series.map((s) => `<br>${s.name}: ${o.vfmt(s.vals[i])}`).join(""), e);
  };
  hit.addEventListener("pointermove", draw); hit.addEventListener("pointerdown", draw);
  hit.addEventListener("pointerleave", () => { cross.style.opacity = 0; dots.forEach((d) => (d.style.opacity = 0)); hideTip(); });
}
})();
