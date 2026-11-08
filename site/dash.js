"use strict";
/* Dashboard: dashboard.json (team-seasons, per-season correlations) + metrics.json (model results). Plain SVG and DOM. */
const NS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);
const el = (tag, a = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (parent) parent.appendChild(e); return e; };
const txt = (p, x, y, s, a = {}) => { const t = el("text", { x, y, ...a }, p); t.textContent = s; return t; };
const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
const sgn = (v, d = 2) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
const lin = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
const lc = (l) => (/^[A-Z][a-z]/.test(l) ? l[0].toLowerCase() + l.slice(1) : l);  // keep acronyms like 3PA, eFG%
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

const FR = { SEA: "OKC", NJN: "BKN", NOH: "NOP", NOK: "NOP", CHH: "NOP", VAN: "MEM" };
const fr = (a) => FR[a] || a;
const TEAM_COLOR = { ATL: "#e03a3e", BOS: "#007a33", BKN: "#3a3a3a", CHA: "#1d1160", CHI: "#ce1141", CLE: "#860038", DAL: "#00538c", DEN: "#0e2240",
  DET: "#c8102e", GSW: "#1d428a", HOU: "#ce1141", IND: "#002d62", LAC: "#c8102e", LAL: "#552583", MEM: "#5d76a9", MIA: "#98002e", MIL: "#00471b",
  MIN: "#236192", NOP: "#0c2340", NYK: "#f58426", OKC: "#007ac1", ORL: "#0077c0", PHI: "#006bb6", PHX: "#e56020", POR: "#e03a3e", SAC: "#5a2d81",
  SAS: "#6b6f72", TOR: "#ce1141", UTA: "#002b5c", WAS: "#002b5c" };
const ERAS = [["2004-05", "Hand-check ban"], ["2011-12", "Lockout, 66 games"], ["2019-20", "Bubble"], ["2023-24", "In-Season Tournament"]];
const ROLE_C = { style: "var(--cool)", execution: "var(--hot)", effort: "var(--mint)" };
const SHORT = { fg3a_rate: "3PA share", fg3_pct: "3P%", corner3_share: "Corner 3s", rim_share: "Rim shots", mid_share: "Mid-range", pace: "Pace", efg: "eFG%",
  opp_efg: "Opp. eFG%", tov_rate: "Turnovers", oreb_pct: "Off. rebounds", ft_rate: "FT rate", ast_pct: "Assist %", drives_100: "Drives", drive_fg: "Drive FG%",
  cs_share: "Catch & shoot", opp_rim_fg: "Rim defense", deflections_100: "Deflections", speed_def: "Defensive speed" };
const PCT_KEYS = new Set(["fg3a_rate", "fg3_pct", "corner3_share", "rim_share", "mid_share", "efg", "opp_efg", "oreb_pct", "ft_rate", "ast_pct", "drive_fg", "cs_share", "opp_rim_fg", "tov_rate"]);
const logo = (a) => `<img src="logos/${fr(a)}.svg" alt="" loading="lazy" decoding="async">`;
const fmtF = (k, v) => v == null ? "n/a" : PCT_KEYS.has(k) ? pct(v > 1 ? v / 100 : v, 1) : v.toFixed(1);

const tip = $("#tip");
function showTip(html, e) {
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect(); let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.transform = `translate(${Math.max(8, x)}px,${Math.max(8, y)}px)`;
}
const hideTip = () => { tip.hidden = true; };
const hover = (node, fn) => { node.addEventListener("pointermove", (e) => showTip(fn(), e)); node.addEventListener("pointerdown", (e) => showTip(fn(), e)); node.addEventListener("pointerleave", hideTip); };

Promise.all([fetch("dashboard.json").then((r) => r.json()), fetch("metrics.json").then((r) => r.json())]).then(([D, M]) => start(D, M))
  .catch((e) => { $("#headline").textContent = "Could not load the data files."; console.error(e); });

function start(D, M) {
  const S = D.seasons, F = D.factors, by = D.by_season, last = S.length - 1;
  // current franchise names and abbreviations throughout: no Seattle, no New Jersey
  { const cur = {}; S.forEach((s) => by[s].teams.forEach((t) => { cur[fr(t.t)] = t.n; })); S.forEach((s) => by[s].teams.forEach((t) => { t.t = fr(t.t); t.n = cur[t.t]; })); }
  const st = { i: 0, x: "fg3a_rate", mode: "raw", team: "", role: "", timer: null };
  const pretty = (s) => s.replace("-", "–");

  /* ---------- static copy ---------- */
  $("#n-metrics").textContent = Object.keys(F).length;
  $("#intro").textContent = `${S.length} seasons, every team, one timeline. Press play or drag the timeline at the bottom.`;

  /* ---------- the short version: four findings, each with what to do about it ---------- */
  {
    const X = M.explore, ov = X.families.overall, byM = Object.fromEntries(M.results.map((r) => [r.model, r]));
    const rec = byM["Baseline: better season-to-date record wins"];
    const fams = X.families.families.filter((f) => f.family !== "Strength" && f.family !== "Era regime" && f.gain_over_strength[1] > 0).map((f) => f.family.toLowerCase());
    const pd3 = X.persistence.find((p) => p.stat === "def_fg3_pct"), BA = M.style.blocks_all_seasons, BT = M.style.blocks_tracking_era;
    const cards = [
      [pct(ov.full_logistic_accuracy, 1), "", `Best pre-game call on unseen seasons. "Better record wins" already gets ${pct(rec.accuracy, 1)}.`, "Do", `Start forecasts from team strength; the other ${ov.n_factors} factors add about ${((ov.full_logistic_accuracy - rec.accuracy) * 100).toFixed(1)} points.`, "#pregame"],
      [String(fams.length), `of ${X.families.families.length - 2} families`, `Pre-game factor groups that beat team strength on unseen seasons: ${fams.join(", ") || "none"}.`, "Do", "Adjust for rest and schedule; ignore altitude, travel and streaks.", "#pregame"],
      [pd3.split_half.toFixed(2), "reliability", "Opponent 3P% barely repeats within a season, so it is mostly luck.", "Do", "Judge a defense by the threes it concedes, not by how many go in.", "#why"],
      [`${(BA.sets["Style (choices)"].win.r2 * 100).toFixed(0)}%`, "vs " + (BT.sets["Execution (results)"].win.r2 * 100).toFixed(0) + "%", "Share of win % explained by shot diet, against execution (making shots, keeping the ball).", "Do", "Spend on shot-making and ball security before a shot-chart overhaul.", "#season-level"],
    ];
    $("#take").innerHTML = cards.map(([n, u, c, ak, a, href]) => `<div class="tk"><div class="n">${n}${u ? `<small>${u}</small>` : ""}</div><div class="c">${c}</div><div class="a"><b>${ak}</b>${a}</div><a href="${href}">Evidence ↓</a></div>`).join("");
  }

  /* ---------- KPI strip ---------- */
  const KPI = [["fg3a_rate", "Shots from three", (v) => pct(v, 1), 100, "pts"], ["pace", "Pace", (v) => v.toFixed(1), 1, ""], ["efg", "Effective FG%", (v) => pct(v, 1), 100, "pts"],
    ["home_win", "Home teams win", (v) => pct(v, 1), 100, "pts"], ["favorite_win", "Favorite wins", (v) => pct(v, 1), 100, "pts"], ["parity_sd", "Spread of win %", (v) => pct(v, 1), 100, "pts"]];
  $("#kpis").innerHTML = KPI.map(([k, l]) => `<div class="kpi"><div class="l">${l}</div><div class="v" id="kv-${k}"></div><div class="d" id="kd-${k}"></div><svg id="ks-${k}" aria-hidden="true"></svg></div>`).join("");
  const spark = (svg, vals, h, pad = 3) => {
    const w = svg.clientWidth || 160, lo = Math.min(...vals), hi = Math.max(...vals), sx = lin(0, vals.length - 1, 0, w), sy = lin(lo, hi, h - pad, pad);
    svg.innerHTML = ""; svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    el("path", { d: vals.map((v, i) => `${i ? "L" : "M"}${sx(i)} ${sy(v)}`).join(""), style: "fill:none;stroke:var(--ink2);stroke-width:1.5" }, svg);
    return { dot: el("circle", { r: 3.5, style: "fill:var(--hot);stroke:var(--panel);stroke-width:1.5" }, svg), sx, sy };
  };
  let kspark = {};
  const drawKpiSparks = () => { kspark = Object.fromEntries(KPI.map(([k]) => [k, spark($(`#ks-${k}`), S.map((s) => by[s].kpi[k]), 26)])); };

  /* ---------- the floor ---------- */
  const xchips = $("#xchips");
  xchips.innerHTML = D.scatter.map((k) => `<button class="chip" data-k="${k}" aria-pressed="${k === st.x}">${SHORT[k] || F[k].label}</button>`).join("");
  xchips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (!b) return; st.x = b.dataset.k; xchips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b)); buildFloor(); });
  const modeBtns = { raw: $("#m-raw"), z: $("#m-z") };
  Object.entries(modeBtns).forEach(([m, b]) => b.addEventListener("click", () => { st.mode = m; Object.entries(modeBtns).forEach(([k, n]) => n.setAttribute("aria-pressed", k === m)); buildFloor(); }));
  const latestName = {}; S.forEach((s) => by[s].teams.forEach((t) => { latestName[fr(t.t)] = t.n; }));
  const franchises = Object.keys(latestName).sort((a, b) => latestName[a].localeCompare(latestName[b]));
  $("#team").innerHTML += franchises.map((f) => `<option value="${f}">${latestName[f]}</option>`).join("");
  $("#team").addEventListener("change", (e) => { st.team = e.target.value; buildFloor(); });

  const zOf = (s, k) => { const v = by[s].teams.map((t) => t.f[k]).filter((v2) => v2 != null); if (v.length < 5) return null; const m = v.reduce((a, b) => a + b, 0) / v.length, sd = Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length); return (x) => (x == null ? null : (x - m) / sd); };
  const xval = (s, t) => { const v = t.f[st.x]; if (v == null) return null; if (st.mode === "raw") return v; const z = zOf(s, st.x); return z ? z(v) : null; };
  let floor = null;
  const niceTicks = (lo, hi, n = 5) => {
    const raw = (hi - lo) / n, p = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 2.5, 5, 10].map((k) => k * p).find((k) => k >= raw);
    const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10)); return { out, step };
  };
  function buildFloor() {
    const box = $("#floor"), w = Math.max(280, box.clientWidth), h = Math.max(300, Math.min(500, Math.round(w * 0.58))), small = w < 560;
    const m = { l: 44, r: 30, t: 26, b: 40 };
    box.innerHTML = ""; const svg = el("svg", { width: w, height: h, viewBox: `0 0 ${w} ${h}` }, box);
    let lo, hi;
    if (st.mode === "raw") {
      const all = S.flatMap((s) => by[s].teams.map((t) => t.f[st.x])).filter((v) => v != null).sort((a, b) => a - b);
      lo = all[Math.floor(all.length * 0.005)]; hi = all[Math.ceil(all.length * 0.995) - 1]; const pad = (hi - lo) * 0.05; lo -= pad; hi += pad;
    } else { lo = -3; hi = 3; }
    const sx = lin(lo, hi, m.l + 6, w - m.r), sy = lin(0.05, 0.95, h - m.b - 4, m.t);
    [0.2, 0.35, 0.5, 0.65, 0.8].forEach((v) => { el("line", { x1: m.l, x2: w - m.r, y1: sy(v), y2: sy(v), class: v === 0.5 ? "gl0" : "gl" }, svg); txt(svg, m.l - 8, sy(v) + 3.5, pct(v, 0), { class: "ax", "text-anchor": "end" }); });
    const { out: ticks, step } = st.mode === "raw" ? niceTicks(lo, hi, small ? 4 : 6) : { out: [-2, -1, 0, 1, 2], step: 1 };
    const tf = (v) => st.mode === "z" ? (v > 0 ? "+" : "") + v + " SD" : PCT_KEYS.has(st.x) && Math.abs(hi) <= 1.5 ? pct(v, step < 0.01 ? 1 : 0) : (+v.toFixed(2)).toString();
    ticks.forEach((v) => { el("line", { x1: sx(v), x2: sx(v), y1: m.t, y2: h - m.b, class: v === 0 && st.mode === "z" ? "gl0" : "gl" }, svg); txt(svg, sx(v), h - m.b + 16, tf(v), { class: "ax", "text-anchor": "middle" }); });
    txt(svg, (m.l + w - m.r) / 2, h - 4, F[st.x].label + (st.mode === "z" ? ", vs. that season's league" : ""), { class: "axt", "text-anchor": "middle" });
    txt(svg, 0, 0, "Win %", { class: "axt", "text-anchor": "middle", transform: `translate(10 ${(m.t + h - m.b) / 2}) rotate(-90)` });
    const fit = el("path", { class: "fit" }, svg), rlab = txt(svg, m.l + 6, 12, "", { class: "ax", style: "fill:var(--ink2);font-weight:600" });
    const trailG = el("g", {}, svg), toks = {};
    franchises.forEach((f) => {
      const g = el("g", { class: "tok", style: "opacity:0" }, svg);
      // logo on a light disc, so dark logos stay legible on the dark theme
      el("circle", { r: 13, class: "hit" }, g); el("circle", { r: small ? 9.5 : 11.5, class: "dot" }, g);
      const ls = small ? 15 : 19; el("image", { href: `logos/${f}.svg`, x: -ls / 2, y: -ls / 2, width: ls, height: ls }, g);
      el("title", {}, g).textContent = latestName[f];
      g.addEventListener("pointerenter", () => { if (st.team !== f) g.parentNode.insertBefore(g, toks[st.team] || null); });  // raise on hover, under the followed team
      hover(g, () => { const t = g._t; return t ? `${logo(t.t)}<b>${t.n}</b> ${pretty(S[st.i])}<br>Win % ${pct(t.w, 1)} · net rating ${sgn(t.net, 1)}<br>${F[st.x].label}: ${fmtF(st.x, t.f[st.x])}` : ""; });
      g.addEventListener("click", () => { st.team = st.team === f ? "" : f; $("#team").value = st.team; buildFloor(); });
      toks[f] = g;
    });
    const note = document.createElement("div"); note.className = "floor-note"; box.appendChild(note);
    floor = { svg, sx, sy, fit, rlab, toks, trailG, note, w, h, m, lo, hi };
    drawTrail(); updateFloor(true);
    if (sixT) updateSix();  // follow-a-team changes rebuild the floor; keep the table's highlight in step
  }
  function drawTrail() {
    const { trailG, sx, sy, lo, hi } = floor; trailG.innerHTML = "";
    if (!st.team) return;
    const pts = S.map((s) => { const t = by[s].teams.find((t2) => fr(t2.t) === st.team); const x = t && xval(s, t); return x == null ? null : [sx(Math.max(lo, Math.min(hi, x))), sy(t.w), s]; });
    const c = TEAM_COLOR[st.team] || "var(--ink)", n = pts.length;
    // older seasons fade, so the direction of travel reads without labels on every point
    pts.forEach((p, i) => { const q = pts[i - 1]; if (p && q) el("line", { x1: q[0], y1: q[1], x2: p[0], y2: p[1], style: `stroke:${c};stroke-width:1.75;stroke-linecap:round;opacity:${0.15 + 0.75 * (i / n)}` }, trailG); });
    const ends = [pts.find(Boolean), [...pts].reverse().find(Boolean)];
    ends.forEach((p, j) => { if (p && (j === 0 || p !== ends[0])) txt(trailG, p[0], p[1] + (j ? -9 : 15), "'" + p[2].slice(2, 4), { class: "ax", "text-anchor": "middle", style: `fill:${c};font-weight:600;opacity:${j ? 1 : 0.6}` }); });
    pts.forEach((p, i) => { if (!p) return; const dot = el("circle", { cx: p[0], cy: p[1], r: 2.5, style: `fill:${c};opacity:${0.25 + 0.75 * (i / n)}` }, trailG); hover(dot, () => `<b>${latestName[st.team]}</b> ${pretty(p[2])}`); });
  }
  function updateFloor(instant) {
    if (!floor) return;
    const s = S[st.i], { sx, sy, toks, fit, rlab, note, lo, hi } = floor, seen = new Set(), xs = [], ys = [];
    by[s].teams.forEach((t) => {
      const f = fr(t.t), g = toks[f], x = xval(s, t); if (!g) return; seen.add(f); g._t = t;
      if (x == null) { g.style.opacity = 0; g._p = null; return; }
      xs.push(x); ys.push(t.w); g._p = [sx(Math.max(lo, Math.min(hi, x))), sy(t.w)];
      if (instant) g.style.transition = "none";
      g.style.transform = `translate(${g._p[0]}px,${g._p[1]}px)`;
      g.style.opacity = ""; g.classList.toggle("dim", !!st.team && st.team !== f); g.classList.toggle("sel", st.team === f);
      g.querySelector(".dot").style.stroke = st.team === f ? TEAM_COLOR[f] || "var(--ink)" : "";
      if (instant) { g.getBoundingClientRect(); g.style.transition = ""; }
    });
    Object.entries(toks).forEach(([f, g]) => { if (!seen.has(f)) { g.style.opacity = 0; g._t = null; g._p = null; } });
    if (toks[st.team]) toks[st.team].parentNode.appendChild(toks[st.team]);
    const first = Object.keys(by).find((k) => by[k].teams.some((t) => t.f[st.x] != null));
    note.textContent = xs.length < 5 ? `${F[st.x].label} is not recorded before ${first}.` : "";
    let r = null;
    if (xs.length >= 5) {
      const mx = xs.reduce((a, b) => a + b, 0) / xs.length, my = ys.reduce((a, b) => a + b, 0) / ys.length;
      const sxy = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0), sxx = xs.reduce((a, x) => a + (x - mx) ** 2, 0), syy = ys.reduce((a, y) => a + (y - my) ** 2, 0);
      const b = sxy / sxx, x0 = Math.min(...xs), x1 = Math.max(...xs), y = (x) => Math.max(0.05, Math.min(0.95, my + b * (x - mx)));
      r = sxy / Math.sqrt(sxx * syy);
      const d = `M${sx(x0)} ${sy(y(x0))}L${sx(x1)} ${sy(y(x1))}`; fit.style.d = `path("${d}")`; fit.setAttribute("d", d); fit.style.opacity = 1;
      rlab.textContent = `${pretty(s)} fit, dashed: r ${sgn(r)}`;
    } else { fit.style.opacity = 0; rlab.textContent = ""; }
    floorCaption(s, r);
  }
  function floorCaption(s, r) {
    const pooled = F[st.x], ts = by[s].teams.filter((t) => t.f[st.x] != null), lab = F[st.x].label;
    if (!ts.length) { $("#floor-sub").textContent = `${lab} comes from tracking or hustle data, which starts after ${pretty(s)}. Move the timeline forward or pick another factor.`; return; }
    const best = ts.reduce((a, b) => (b.w > a.w ? b : a)), worst = ts.reduce((a, b) => (b.w < a.w ? b : a));
    const sorted = ts.map((t) => t.f[st.x]).sort((a, b) => a - b), rank = (v) => sorted.filter((u) => u > v).length + 1, ordinal = (k) => k + (k % 100 >= 11 && k % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][k % 10] || "th");
    const strength = r == null ? "" : Math.abs(r) < 0.15 ? "barely related to" : Math.abs(r) < 0.35 ? "loosely tied to" : "clearly tied to";
    const team = st.team && ts.find((t) => fr(t.t) === st.team);
    const f = (k, v) => `<span><span class="k">${k}</span>${v}</span>`;
    $("#floor-sub").innerHTML = f(pretty(s), `<b>r ${r == null ? "n/a" : sgn(r)}</b>, ${strength} winning`) +
      f("Best", `${logo(best.t)}${best.n} ${pct(best.w, 0)}, ${ordinal(rank(best.f[st.x]))} of ${ts.length}`) +
      f("Worst", `${logo(worst.t)}${worst.n} ${pct(worst.w, 0)}, ${ordinal(rank(worst.f[st.x]))}`) +
      f("All seasons", `<b>r ${sgn(pooled.r_win)}</b>${pooled.beats_chance ? "" : ", within chance"}`) +
      (team ? f("Following", `${logo(team.t)}${team.n} ${pct(team.w, 0)}, ${fmtF(st.x, team.f[st.x])}`) : "");
  }

  /* ---------- leaderboard ---------- */
  const board = $("#lboard"), rows = {};
  Object.entries(F).forEach(([k, f]) => {
    const d = document.createElement("div"); d.className = "lb"; d.style.opacity = 0; d.style.transform = "translateY(400px)";
    d.innerHTML = `<span class="rk"></span><span class="nm" title="${f.definition}"><i style="background:${ROLE_C[f.role]}"></i>${f.label}</span><span class="rv"></span><span class="bar"><s></s><b style="background:${ROLE_C[f.role]}"></b><u style="left:${50 + f.r_win * 50}%"></u></span>`;
    board.appendChild(d); rows[k] = d;
  });
  document.querySelectorAll("[data-role]").forEach((b) => b.addEventListener("click", () => { st.role = b.dataset.role; document.querySelectorAll("[data-role]").forEach((n) => n.setAttribute("aria-pressed", n === b)); updateBoard(); }));
  function updateBoard() {
    const r = by[S[st.i]].r, keys = Object.keys(r).filter((k) => F[k] && r[k] != null && (!st.role || (st.role === "style" ? F[k].role !== "execution" : F[k].role === "execution")));
    keys.sort((a, b) => Math.abs(r[b]) - Math.abs(r[a])); const top = new Set(keys.slice(0, 10));
    const all = Object.keys(r).filter((k) => F[k] && r[k] != null).sort((a, b) => Math.abs(r[b]) - Math.abs(r[a])), fs = all.findIndex((k) => F[k].role !== "execution");
    $("#board-sub").textContent = `Top ${Math.min(10, keys.length)} of ${all.length} by correlation with win %. ${fs < 0 ? "" : `Highest style factor: #${fs + 1}, ${lc(F[all[fs]].label)}.`}`;
    Object.entries(rows).forEach(([k, d]) => {
      const i = keys.indexOf(k);
      if (top.has(k)) {
        d.style.transform = `translateY(${i * 40}px)`; d.style.opacity = 1; d.removeAttribute("aria-hidden");
        d.querySelector(".rk").textContent = i + 1; d.querySelector(".rv").textContent = sgn(r[k]);
        const b = d.querySelector(".bar b"), v = r[k]; b.style.left = `${v < 0 ? 50 + v * 50 : 50}%`; b.style.width = `${Math.abs(v) * 50}%`;
      } else { d.style.opacity = 0; d.style.transform = "translateY(400px)"; d.setAttribute("aria-hidden", "true"); }
    });
  }

  /* ---------- why they won: six-factor table ---------- */
  const SK = D.six_keys, SF = D.six_fit, sv = (t, k) => t.six[SK.indexOf(k)];
  const SIXC = [["o_shoot", "Shooting"], ["o_tov", "Turnovers"], ["o_reb", "Rebounds"], ["o_ft", "Free throws"],
    ["d_shoot", "Shooting"], ["d_tov", "Turnovers"], ["d_reb", "Rebounds"], ["d_ft", "Free throws"], ["resid", "Other"], ["luck", "3P luck"]];
  const SIXL = { o_shoot: "shooting", o_tov: "ball security", o_reb: "offensive rebounding", o_ft: "getting to the line",
    d_shoot: "shooting defense", d_tov: "forcing turnovers", d_reb: "defensive rebounding", d_ft: "keeping opponents off the line" };
  st.sixSort = "net"; st.luck = false;
  const sixT = $("#six");
  const head = `<thead><tr><th colspan="4"></th><th class="grp sep" colspan="4">Offense</th><th class="grp sep" colspan="4">Defense</th><th class="sep" colspan="2"></th></tr><tr>` +
    `<th>#</th><th class="tm">Team</th>` + [["w", "Win %"], ["net", "Net"]].concat(SIXC).map(([k, l], j) => `<th data-k="${k}" class="${[0, 2, 6, 10].includes(j) ? "sep" : ""}"><button>${l}</button></th>`).join("") + `</tr></thead><tbody></tbody>`;
  sixT.innerHTML = head;
  sixT.querySelectorAll("th[data-k]").forEach((th) => th.querySelector("button").addEventListener("click", () => { st.sixSort = th.dataset.k; updateSix(); }));
  const lucky = { off: $("#l-off"), on: $("#l-on") };
  Object.entries(lucky).forEach(([m, b]) => b.addEventListener("click", () => { st.luck = m === "on"; Object.entries(lucky).forEach(([k, n]) => n.setAttribute("aria-pressed", k === m)); updateSix(); }));
  const followTeam = (f) => { st.team = st.team === f ? "" : f; $("#team").value = st.team; buildFloor(); };
  sixT.addEventListener("click", (e) => { const tr = e.target.closest("tbody tr"); if (tr) followTeam(tr.dataset.f); });
  sixT.addEventListener("keydown", (e) => { const tr = e.target.closest("tbody tr"); if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); followTeam(tr.dataset.f); } });
  const tint = (v, full) => { const a = Math.round(Math.min(1, Math.abs(v) / full) * 42); return a < 4 ? "" : `background:color-mix(in srgb, var(${v > 0 ? "--cool" : "--hot"}) ${a}%, transparent)`; };
  const ord = (k) => k + (k % 100 >= 11 && k % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][k % 10] || "th");
  function updateSix() {
    const s = S[st.i], L = st.luck;
    const rows = by[s].teams.map((t) => {
      const luck = sv(t, "luck"), r = { t, f: fr(t.t), v: { w: L ? t.w - luck * SF.win_per_point : t.w, net: L ? t.net - luck : t.net } };
      SK.forEach((k) => { r.v[k] = sv(t, k); }); return r;
    });
    const keys = ["w", "net", ...SK], rank = {};
    keys.forEach((k) => { const o = [...rows].sort((a, b) => b.v[k] - a.v[k]); rank[k] = new Map(o.map((r, i) => [r, i + 1])); });
    const played = new Map([...rows].sort((a, b) => b.t.net - a.t.net).map((r, i) => [r, i + 1]));
    rows.sort((a, b) => b.v[st.sixSort] - a.v[st.sixSort]);
    sixT.querySelectorAll("th[data-k]").forEach((th) => (th.dataset.k === st.sixSort ? th.setAttribute("aria-sort", "descending") : th.removeAttribute("aria-sort")));
    sixT.querySelector("thead th[data-k=w] button").textContent = L ? "Win %, neutral" : "Win %";
    sixT.querySelector("thead th[data-k=net] button").textContent = L ? "Net, neutral" : "Net";
    sixT.tBodies[0].innerHTML = rows.map((r, i) => {
      const mv = played.get(r) - rank.net.get(r), mvs = L && mv ? `<span class="mv ${mv > 0 ? "up" : "dn"}" title="${mv > 0 ? "Up" : "Down"} ${Math.abs(mv)} from as played">${mv > 0 ? "▲" : "▼"}${Math.abs(mv)}</span> ` : "";
      const cell = (k, j) => `<td class="${[0, 4, 8].includes(j) ? "sep" : ""}" style="${tint(r.v[k], k === "luck" || k === "resid" ? 2.5 : 4)}">${Math.abs(r.v[k]) < 0.05 ? "0.0" : sgn(r.v[k], 1)}<small>#${rank[k].get(r)}</small></td>`;
      return `<tr data-f="${r.f}" tabindex="0" class="${st.team === r.f ? "sel" : ""}"><td class="rk">${i + 1}</td><td class="tm">${logo(r.t.t)}<span class="nm">${r.t.n}</span><small>${r.t.t}</small></td>` +
        `<td class="sep">${pct(r.v.w, 1)}<small>#${rank.w.get(r)}</small></td><td class="big">${sgn(r.v.net, 1)}<small>${mvs}#${rank.net.get(r)}</small></td>` +
        SIXC.map(([k], j) => cell(k, j)).join("") + `</tr>`;
    }).join("");
    // caption: what drove the best team, who shot luckiest, and who moves most once luck is out
    const best = [...rows].sort((a, b) => b.t.net - a.t.net)[0], drv = Object.keys(SIXL).reduce((a, k) => (best.v[k] > best.v[a] ? k : a));
    const byLuck = [...rows].sort((a, b) => b.v.luck - a.v.luck), lk = byLuck[0], ul = byLuck[byLuck.length - 1];
    const neutral = new Map([...rows].sort((a, b) => (b.t.net - b.v.luck) - (a.t.net - a.v.luck)).map((r, j) => [r, j + 1]));
    const mover = rows.reduce((a, b) => (Math.abs(played.get(b) - neutral.get(b)) > Math.abs(played.get(a) - neutral.get(a)) ? b : a));
    const d = played.get(mover) - neutral.get(mover), fol = st.team && rows.find((r) => r.f === st.team);
    const f = (k, v) => `<span><span class="k">${k}</span>${v}</span>`;
    $("#six-sub").innerHTML = f("Best", `${logo(best.t.t)}<b>${best.t.n} ${sgn(best.t.net, 1)}</b>, mostly ${SIXL[drv]}`) +
      f("Luckiest from 3", `${logo(lk.t.t)}${lk.t.n} ${sgn(lk.v.luck, 1)}`) + f("Unluckiest", `${logo(ul.t.t)}${ul.t.n} ${sgn(ul.v.luck, 1)}`) +
      f("Luck out", d ? `${logo(mover.t.t)}${mover.t.n} ${ord(played.get(mover))} → ${ord(neutral.get(mover))}` : "no team moves") +
      (fol ? f("Following", `${logo(fol.t.t)}${fol.t.n}: best at ${SIXL[Object.keys(SIXL).reduce((a, k) => (fol.v[k] > fol.v[a] ? k : a))]}, worst at ${SIXL[Object.keys(SIXL).reduce((a, k) => (fol.v[k] < fol.v[a] ? k : a))]}`) : "");
  }
  $("#six-fn").textContent = `Weights fitted by least squares on all ${SF.n} team-seasons, each rate measured against its own season's league average. The eight factors explain ${pct(SF.r2, 1)} of net rating; "Other" is the remainder. ` +
    `3P luck pulls each team's own and allowed three-point % toward the league by how little of it repeats within a season (reliability ${SF.rel_off.toFixed(2)} for a team's own shooting, ${SF.rel_def.toFixed(2)} for what it allows), then counts the gap in points. ` +
    `That treats great shooting teams as partly lucky, which they partly are not. One point of net rating is worth about ${(SF.win_per_point * 82).toFixed(1)} wins over 82 games.`;

  /* ---------- pulse ---------- */
  const PULSE = [["fg3a_rate", "Shots from three", (v) => pct(v, 1)], ["rim_share", "Shots at the rim", (v) => pct(v, 1)], ["mid_share", "Mid-range shots", (v) => pct(v, 1)],
    ["pace", "Possessions per game", (v) => v.toFixed(1)], ["efg", "Effective FG%", (v) => pct(v, 1)], ["home_win", "Home win rate", (v) => pct(v, 1)]];
  $("#pulse").innerHTML = PULSE.map(([k, l]) => `<div class="pc"><div class="l">${l}<b class="mono" id="pv-${k}"></b></div><svg id="ps-${k}" aria-hidden="true"></svg></div>`).join("");
  let psp = {};
  const drawPulse = () => { psp = Object.fromEntries(PULSE.map(([k]) => [k, spark($(`#ps-${k}`), S.map((s) => by[s].kpi[k]), 64, 6)])); };

  /* ---------- timeline ---------- */
  const track = $("#track"), scrub = $("#scrub"); scrub.max = last;
  let tl = null;
  function drawTrack() {
    const w = track.clientWidth || 600, h = 44, small = w < 520, sx = lin(0, last, 8, w - 8);
    track.innerHTML = ""; track.setAttribute("viewBox", `0 0 ${w} ${h}`);
    const v = S.map((s) => by[s].kpi.fg3a_rate), hi = Math.max(...v), sy = lin(0, hi, h - 14, 12);
    el("path", { d: `M${sx(0)} ${h - 14}` + v.map((y, i) => `L${sx(i)} ${sy(y)}`).join("") + `L${sx(last)} ${h - 14}Z`, style: "fill:var(--hot);opacity:.12" }, track);
    el("line", { x1: sx(0), x2: sx(last), y1: h - 14, y2: h - 14, style: "stroke:var(--ink2);stroke-width:1" }, track);
    const prog = el("line", { x1: sx(0), y1: h - 14, y2: h - 14, style: "stroke:var(--hot);stroke-width:3;stroke-linecap:round" }, track);
    S.forEach((s, i) => { el("line", { x1: sx(i), x2: sx(i), y1: h - 17, y2: h - 11, style: "stroke:var(--ink2)" }, track); if (i % (small ? 5 : 5) === 0 || i === last) txt(track, sx(i), h - 1, "'" + s.slice(2, 4), { class: "ax", "text-anchor": "middle" }); });
    ERAS.forEach(([s, label]) => { const i = S.indexOf(s); if (i < 0) return; el("circle", { cx: sx(i), cy: 6, r: 2.5, style: "fill:var(--ink2)" }, track); el("line", { x1: sx(i), x2: sx(i), y1: 8, y2: h - 17, style: "stroke:var(--ink2);stroke-dasharray:1 2;opacity:.6" }, track);
      if (!small) txt(track, sx(i) + 5, 10, label, { class: "era" }); });
    const knob = el("circle", { cy: h - 14, r: 8, style: "fill:var(--hot);stroke:var(--bg);stroke-width:2.5" }, track);
    tl = { sx, prog, knob };
  }

  /* ---------- season update ---------- */
  function setSeason(i, instant = false) {
    st.i = i; const s = S[i], B = by[s], k = B.kpi;
    $("#season").innerHTML = `${s.slice(0, 4)}<span>-</span>${s.slice(5)}`; $("#cur").textContent = pretty(s);
    $("#hero-n").textContent = `${k.games.toLocaleString()} games · ${B.teams.length} teams`;
    const rr = Object.entries(B.r).filter(([key]) => F[key]), top = rr.reduce((a, b) => (Math.abs(b[1]) > Math.abs(a[1]) ? b : a));
    const topS = rr.filter(([key]) => F[key].role !== "execution").reduce((a, b) => (Math.abs(b[1]) > Math.abs(a[1]) ? b : a));
    $("#headline").innerHTML = `Threes were <b>${pct(k.fg3a_rate, 0)}</b> of all shots. Biggest gap between winners and losers: ${F[top[0]].label} (r ${sgn(top[1])}). Best style signal: ${F[topS[0]].label} (${sgn(topS[1])}).`;
    KPI.forEach(([key, , f, mult, unit]) => { const v = k[key], v0 = by[S[0]].kpi[key]; $(`#kv-${key}`).textContent = f(v);
      $(`#kd-${key}`).textContent = i ? `${sgn((v - v0) * mult, 1)}${unit ? " " + unit : ""} since '00` : "baseline"; const sp = kspark[key]; if (sp) { sp.dot.setAttribute("cx", sp.sx(i)); sp.dot.setAttribute("cy", sp.sy(v)); } });
    PULSE.forEach(([key, , f]) => { $(`#pv-${key}`).textContent = f(k[key]); const sp = psp[key]; if (sp) { sp.dot.setAttribute("cx", sp.sx(i)); sp.dot.setAttribute("cy", sp.sy(k[key])); } });
    if (tl) { tl.knob.setAttribute("cx", tl.sx(i)); tl.prog.setAttribute("x2", tl.sx(i)); }
    scrub.value = i; scrub.setAttribute("aria-valuetext", s);
    updateFloor(instant); updateBoard(); updateSix();
  }

  /* ---------- play ---------- */
  const ico = $("#play-ico"), playBtn = $("#play");
  const stop = () => { clearInterval(st.timer); st.timer = null; ico.setAttribute("d", "M4 2.5v11l9-5.5z"); playBtn.setAttribute("aria-label", "Play the seasons"); };
  const play = () => { if (st.i >= last) setSeason(0); ico.setAttribute("d", "M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"); playBtn.setAttribute("aria-label", "Pause");
    st.timer = setInterval(() => { if (st.i >= last) return stop(); setSeason(st.i + 1); }, 1100); };
  playBtn.addEventListener("click", () => { st.touched = true; st.timer ? stop() : play(); });
  scrub.addEventListener("input", () => { st.touched = true; stop(); setSeason(+scrub.value); });
  document.addEventListener("keydown", (e) => { if (e.key === " " && !e.target.closest("input,select,button,textarea")) { e.preventDefault(); st.touched = true; st.timer ? stop() : play(); } });

  const drawAll = () => { drawKpiSparks(); drawPulse(); drawTrack(); buildFloor(); setSeason(st.i, true); };
  drawAll();
  let rw = innerWidth; addEventListener("resize", () => { if (innerWidth !== rw) { rw = innerWidth; drawAll(); } });
  if (reduced) setSeason(last, true); else setTimeout(() => { if (!st.touched) play(); }, 700);  // autoplay once, unless the reader got there first
}
