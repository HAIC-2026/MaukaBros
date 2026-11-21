// DOM builders for district figures, shared by the map page and the report page.
// Every value is inserted with textContent (via el()), never as HTML.
import { fmtMetric, fmtMoe, fmtCount, diffText, shortCounty, shortGeo, compareEstimates } from "./format.js";

export const $ = id => document.getElementById(id);

export const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  kids.forEach(k => k != null && n.append(k));
  return n;
};

export function tableLinks(src, into) {
  (src.tables || []).forEach((t, i) => into.append(i ? ", " : "",
    el("a", { href: t.url, target: "_blank", rel: "noopener", textContent: "Table " + t.table_id })));
}

// Short source line: source, year, table and geography on every figure.
export function srcLine(src) {
  const p = el("p", { className: "src" }, `Census ACS 5-year ${src.year} · `);
  tableLinks(src, p);
  p.append(` · ${shortGeo(src.geography)}`);
  return p;
}

// Notes a reader needs once, kept out of the way: a closed "About these figures".
export const aboutBox = (...notes) => {
  const ps = notes.filter(Boolean);
  return ps.length ? el("details", { className: "about-notes" }, el("summary", { textContent: "About these figures" }),
    el("div", { className: "inner" }, ...ps.map(n => el("p", { textContent: n })))) : null;
};

// ---------- headline cards: three views ----------
// The same figures, drawn three ways. Each view answers a different question:
//   text   "What does it say?" plain sentences (default)
//   range  "Is the gap real?"  district estimate with its margin-of-error band, county and state marked
//   bars   "How big is it?"    bars from zero, so sizes compare at a glance
// Range and bars are drawn for sighted readers; their full sentence is in screen-reader text.
export const CARD_STYLES = [
  ["text", "Text", "Each comparison as a plain sentence."],
  ["range", "Range", "Is each gap real? The shaded band is the margin of error."],
  ["bars", "Bars", "How big is each figure? Bars start at zero."],
];
const CS_KEY = "di-card-style";
export function cardStyle() {
  let s = new URL(location.href).searchParams.get("card");
  try { s = s || localStorage.getItem(CS_KEY); } catch { /* storage blocked */ }
  return CARD_STYLES.some(([k]) => k === s) ? s : CARD_STYLES[0][0];
}
export function cardStyleSwitch(onChange) {
  const cur = cardStyle();
  const wrap = el("div", { className: "cs-switch", role: "group" });
  wrap.setAttribute("aria-label", "Card view");
  CARD_STYLES.forEach(([k, label]) => {
    const b = el("button", { type: "button", textContent: label, onclick: () => {
      try { localStorage.setItem(CS_KEY, k); } catch { /* storage blocked */ }
      const u = new URL(location.href); u.searchParams.delete("card"); history.replaceState(null, "", u);
      onChange(k);
    } });
    b.setAttribute("aria-pressed", k === cur);
    wrap.append(b);
  });
  return wrap;
}

const GLYPH = { 1: "▲", "-1": "▼", 0: "=" };
const VERDICT = { real: "Clear difference", within: "Within margin of error", unknown: "No margin of error published" };
const verdictOf = d => d.dir === 0 || d.text === "not available" ? "" : VERDICT[d.sure];
const capital = t => t.charAt(0).toUpperCase() + t.slice(1);

// The comparisons on one card: name, value, and the difference in compact and sentence form.
function refsOf(c) {
  const refs = [];
  if (c.county) refs.push({ key: "co", name: shortCounty(c.county.name), ref: c.county });
  refs.push({ key: "st", name: "State", ref: c.state });
  return refs.map(r => {
    const d = diffText(r.ref && r.ref.difference, c.format);
    const value = r.ref ? r.ref.value : null;
    const whom = r.key === "st" ? "the state" : r.name;
    const v = fmtMetric(value, c.format);
    const say = d.text === "not available" ? `${r.name}: ${v}`
      : d.dir === 0 ? `About the same as ${whom} (${v})`
      : `${capital(d.text)} than ${whom} (${v}). ${verdictOf(d)}`;
    return { ...r, value, d, whom, say };
  });
}
// Delta chip: ▲ 2.1 pts. Solid for a clear difference; dashed outline inside the margin of error.
function chip(d) {
  if (d.text === "not available") return el("span", { className: "cs-chip na", textContent: "n/a" });
  return el("span", { className: `cs-chip ${d.dir === 0 ? "within" : d.sure}`, title: verdictOf(d) || d.text },
    el("b", { textContent: GLYPH[d.dir] }), d.dir === 0 ? "same" : d.size);
}
// Scale for a number line around the given points, padded, kept inside 0-100% for rates.
function scale(pts, c) {
  let lo = Math.min(...pts), hi = Math.max(...pts);
  const pad = (hi - lo) * 0.12 || Math.abs(pts[0]) * 0.1 || 0.01;
  lo -= pad; hi += pad;
  if (c.format !== "dollars") { lo = Math.max(0, lo); hi = Math.min(1, hi); }
  return x => `${(100 * (x - lo) / (hi - lo)).toFixed(2)}%`;
}
const band = (at, v, m, cls = "") => el("span", { className: `cs-band ${cls}`, style: `left:${at(v - m)};width:calc(${at(v + m)} - ${at(v - m)})` });
const dot = (at, v, cls = "") => el("span", { className: `cs-dot ${cls}`, style: `left:${at(v)}` });
const whiskerAt = (w, v, m) => el("span", { className: "cs-whisker", style: `left:${w(v - m)};width:calc(${w(v + m)} - ${w(v - m)})` });

// Range: the estimate, its margin of error, and where the county and state fall.
function styleRange(c, refs) {
  const v = c.district.value, m = c.district.moe || 0;
  const at = scale([v, v - m, v + m, ...refs.map(r => r.value).filter(x => x != null)], c);
  const track = el("div", { className: "cs-track" }, band(at, v, m),
    ...refs.filter(r => r.value != null).map(r => el("span", { className: `cs-tick ${r.key}`, style: `left:${at(r.value)}` })),
    dot(at, v));
  const rows = el("div", { className: "cs-rows" }, ...refs.map(r => el("div", { className: "cs-row" },
    el("span", { className: `cs-key ${r.key}` }), el("span", { className: "cs-name", textContent: r.name }),
    el("span", { className: "cs-val", textContent: fmtMetric(r.value, c.format) }), chip(r.d))));
  return [el("div", { className: "cs-range" }, track), rows];
}
// Bars: sizes from zero. The district bar carries a whisker for its margin of error.
function barRow(cls, label, value, c, w, extra, tail) {
  return el("div", { className: `cs-bar ${cls}` }, el("span", { className: "cs-name", textContent: label }),
    el("span", { className: "cs-barwrap" }, el("span", { className: "cs-fill", style: `width:${w(value || 0)}` }), extra),
    el("span", { className: "cs-val" }, fmtMetric(value, c.format), tail));
}
function styleBars(c, refs) {
  const v = c.district.value, m = c.district.moe || 0;
  const max = Math.max(v + m, ...refs.map(r => r.value || 0)) * 1.04 || 1;
  const w = x => `${(100 * Math.max(0, x) / max).toFixed(2)}%`;
  return [el("div", { className: "cs-bars" }, barRow("me", "District", v, c, w, whiskerAt(w, v, m), null),
    ...refs.map(r => barRow(r.key, r.name.replace(/ County$/, ""), r.value, c, w, null,
      r.d.sure === "real" || r.d.dir === 0 ? null : el("b", { className: "cs-approx", textContent: " ≈", title: verdictOf(r.d) }))))];
}
// Text: one sentence per comparison.
function styleText(c, refs) {
  return [el("ul", { className: "cs-text" }, ...refs.map(r => {
    if (r.d.text === "not available") return el("li", { textContent: r.say + "." });
    if (r.d.dir === 0) return el("li", {}, el("b", { textContent: "About the same" }), ` as ${r.whom} (${fmtMetric(r.value, c.format)}).`);
    return el("li", {}, el("b", { textContent: capital(r.d.text) }), ` than ${r.whom} (${fmtMetric(r.value, c.format)}). `,
      el("span", { className: `cs-verdict ${r.d.sure}`, textContent: verdictOf(r.d) + "." }));
  }))];
}

// How a figure was made: a percentage from two published counts, or a median published as is.
function howCalculated(c) {
  const calc = calcDetails(c.district.calculation);
  if (calc || c.district.value == null || c.format !== "dollars") return calc;
  const tables = (c.source.tables || []).map(t => "Table " + t.table_id).join(", ");
  return el("details", { className: "calc" }, el("summary", { textContent: "How it's calculated" }),
    el("p", { textContent: `Published as is by the Census Bureau (${tables}). Medians can't be rebuilt from counts.` }));
}

// One headline figure: value with its margin of error, comparison with county and state, source.
export function renderKeyFact(c, { style = cardStyle() } = {}) {
  const card = el("article", { className: `fact card-${style}` }, el("h3", { textContent: c.label }));
  const has = c.district.value != null;
  card.append(el("p", { className: "big" }, fmtMetric(c.district.value, c.format),
    has ? el("span", { className: "pm", textContent: ` ${fmtMoe(c.district.moe, c.format)}` }) : null));
  if (!has) card.append(el("p", { className: "moe", textContent: "Not published for this district" }));
  if (c.district.low_reliability) card.append(el("p", { className: "flag", textContent: "Low reliability: large margin of error" }));
  const refs = refsOf(c);
  const vs = el("div", { className: "vs" });
  if (has && style === "text") vs.append(...styleText(c, refs));
  else {
    vs.append(el("p", { className: "sr-only", textContent: refs.map(r => r.say).join(". ") + "." }));
    if (has) (style === "bars" ? styleBars : styleRange)(c, refs).forEach(n => { n.setAttribute("aria-hidden", "true"); vs.append(n); });
  }
  card.append(vs, srcLine(c.source));
  const how = howCalculated(c);
  if (how) card.append(how);
  return card;
}

// Two districts on one card: both values with margins of error, the difference tested against
// both margins (same rule as pairTable), and the state for reference.
// `a` and `b` are { id, name }; `ca` and `cb` are each district's comparison for this measure.
export function renderPairFact(ca, cb, a, b, style = cardStyle()) {
  const c = ca || cb;
  const card = el("article", { className: `fact pair card-${style}` }, el("h3", { textContent: c.label }));
  const A = ca && ca.district, B = cb && cb.district, S = c.state && c.state.value;
  const val = (e, who, cls) => el("div", { className: `pv ${cls}` }, el("span", { className: "pv-id", textContent: who.id }),
    el("span", { className: "pv-big", textContent: fmtMetric(e && e.value, c.format) }),
    e && e.value != null ? el("span", { className: "pm", textContent: fmtMoe(e.moe, c.format) }) : el("span", { className: "pm", textContent: "Not published" }));
  card.append(el("div", { className: "pv-row" }, val(A, a, "a"), val(B, b, "b")));
  [[A, a], [B, b]].forEach(([e, who]) => { if (e && e.low_reliability) card.append(el("p", { className: "flag", textContent: `${who.id}: low reliability, large margin of error` })); });
  const both = A && B && A.value != null && B.value != null;
  const d = diffText(both ? compareEstimates(A, B) : null, c.format);
  const sentence = !both ? "Not available for both districts"
    : d.dir === 0 ? `About the same in ${a.id} and ${b.id}`
    : `${capital(d.text)} in ${a.id} than ${b.id}. ${verdictOf(d)}`;
  const stateLine = `State: ${fmtMetric(S, c.format)}`;
  const vs = el("div", { className: "vs" });
  if (style === "text") {
    vs.append(el("ul", { className: "cs-text" },
      el("li", {}, both && d.dir !== 0 ? el("b", { textContent: capital(d.text) }) : el("b", { textContent: both ? "About the same" : "Not available" }),
        both && d.dir !== 0 ? ` in ${a.id} than ${b.id}. ` : both ? ` in ${a.id} and ${b.id}.` : " for both districts.",
        both && d.dir !== 0 ? el("span", { className: `cs-verdict ${d.sure}`, textContent: verdictOf(d) + "." }) : null),
      el("li", { textContent: stateLine + "." })));
  } else {
    vs.append(el("p", { className: "sr-only", textContent: `${a.name}: ${fmtMetric(A && A.value, c.format)}${A && A.value != null ? `, ${fmtMoe(A.moe, c.format)}` : ""}. ${b.name}: ${fmtMetric(B && B.value, c.format)}${B && B.value != null ? `, ${fmtMoe(B.moe, c.format)}` : ""}. ${sentence}. ${stateLine}.` }));
    if (both) {
      let pic;
      if (style === "bars") {
        const max = Math.max(A.value + (A.moe || 0), B.value + (B.moe || 0), S || 0) * 1.04 || 1;
        const w = x => `${(100 * Math.max(0, x) / max).toFixed(2)}%`;
        pic = el("div", { className: "cs-bars" }, barRow("me", a.id, A.value, c, w, whiskerAt(w, A.value, A.moe || 0), null),
          barRow("b", b.id, B.value, c, w, whiskerAt(w, B.value, B.moe || 0), null), barRow("st", "State", S, c, w, null, null));
      } else {
        const at = scale([A.value, A.value - (A.moe || 0), A.value + (A.moe || 0), B.value - (B.moe || 0), B.value + (B.moe || 0), ...(S != null ? [S] : [])], c);
        pic = el("div", { className: "cs-range" }, el("div", { className: "cs-track" },
          band(at, A.value, A.moe || 0), band(at, B.value, B.moe || 0, "b"),
          S != null ? el("span", { className: "cs-tick st", style: `left:${at(S)}` }) : null, dot(at, B.value, "b"), dot(at, A.value)));
      }
      pic.setAttribute("aria-hidden", "true");
      const verdict = el("div", { className: "cs-pair-verdict" }, chip(d),
        el("span", { className: "cs-name", textContent: `${a.id} vs ${b.id}${d.dir === 0 ? "" : ": " + verdictOf(d).toLowerCase()}` }));
      verdict.setAttribute("aria-hidden", "true");
      vs.append(pic, verdict);
      if (style !== "bars") vs.append(el("p", { className: "cs-state", textContent: stateLine, ariaHidden: "true" }));

    }
  }
  const geos = [...new Set([ca, cb].filter(Boolean).map(x => shortGeo(x.source.geography)))];
  card.append(vs, srcLine({ ...c.source, geography: geos.join(" and ") }));
  return card;
}

// One-line key under a grid of headline cards, matching the view. `pair` = { a, b } ids when comparing.
export function factKey(style = cardStyle(), pair = null) {
  if (style === "text") return null;
  const k = el("p", { className: "cs-legend" });
  k.setAttribute("aria-hidden", "true"); // each card carries its own screen-reader sentence
  if (style === "range" && pair) k.append(el("span", { className: "cs-dot sw" }), pair.a, el("span", { className: "cs-dot b sw" }), pair.b,
    el("span", { className: "cs-band sw" }), "Margin of error", el("span", { className: "cs-key st" }), "State");
  else if (style === "range") k.append(el("span", { className: "cs-dot sw" }), "District", el("span", { className: "cs-band sw" }), "Margin of error",
    el("span", { className: "cs-key co" }), "County", el("span", { className: "cs-key st" }), "State");
  else k.append(el("span", { className: "cs-whisker sw" }), "Margin of error");
  if (style === "bars" && !pair) {
    k.append(el("b", { className: "cs-approx", textContent: "≈" }), "Within margin of error");
    return k;
  }
  k.append(el("span", { className: "cs-chip real" }, el("b", { textContent: "▲" }), "Clear difference"),
    el("span", { className: "cs-chip within" }, el("b", { textContent: "▲" }), "Within margin of error"));
  return k;
}

// The two published counts behind a percentage, so the reader can find them in the Census table.
export function calcDetails(calc) {
  if (!calc || calc.numerator.value == null || calc.denominator.value == null) return null;
  const { numerator: n, denominator: d } = calc;
  const item = p => el("li", {}, el("strong", { textContent: fmtCount(p.value) }),
    ` ${p.label.charAt(0).toLowerCase() + p.label.slice(1)}`,
    p.rows > 1 ? `, ${p.rows} table rows added together` : "",
    p.moe != null ? el("span", { className: "moe", textContent: ` ±${fmtCount(p.moe)}` }) : "");
  return el("details", { className: "calc" },
    el("summary", { textContent: "How it's calculated" }),
    el("p", { textContent: `${fmtCount(n.value)} ÷ ${fmtCount(d.value)} = ${(100 * n.value / d.value).toFixed(1)}%` }),
    el("ul", {}, item(n), item(d)),
    el("p", { textContent: "Both counts are in the linked Census table." }));
}

// Card shown when a view asks for a figure the data store does not have.
export function missingFact(label) {
  return el("article", { className: "fact missing" }, el("h3", { textContent: label }),
    el("p", { className: "big", textContent: "Not available" }),
    el("p", { className: "moe", textContent: "Not in this tool's data yet" }));
}

// Plain-language comparison for table cells: "2.1 pts higher" or "14% lower".
const cellDiff = text => text.replace(" points ", " pts ");

// Table of comparisons (district with margin of error, county, state, differences), grouped.
export function comparisonTable(comps, countyName, { groupRows = true } = {}) {
  const t = el("table");
  const cn = countyName || "County";
  const head = t.createTHead().insertRow();
  ["Measure", "This district", cn, "State", "Vs " + cn, "Vs state"].forEach(h => head.append(el("th", { scope: "col", textContent: h })));
  const body = t.createTBody();
  let group = null;
  comps.forEach(c => {
    if (groupRows && c.group !== group) {
      group = c.group;
      if (group !== "District profile") {
        const th = el("th", { scope: "colgroup", colSpan: 6, textContent: group, className: "grouprow" });
        if (c.group_note) th.append(el("span", { className: "moe", textContent: c.group_note }));
        body.insertRow().append(th);
      }
    }
    const tr = body.insertRow();
    const src = el("span", { className: "moe" });
    tableLinks(c.source, src);
    src.append(` · ACS 5-year ${c.source.year}`);
    tr.append(el("th", { scope: "row" }, c.label, src));
    const v = (e, withMoe) => {
      const td = el("td", {}, fmtMetric(e && e.value, c.format));
      if (withMoe && e && e.value != null) td.append(el("span", { className: "moe", textContent: fmtMoe(e.moe, c.format) }));
      if (withMoe && e && e.low_reliability) td.append(el("span", { className: "flag", textContent: "Low reliability: large margin of error" }));
      return td;
    };
    const d = ref => {
      const x = diffText(ref && ref.difference, c.format);
      const td = el("td", {}, cellDiff(x.text));
      if (x.flag) td.append(el("span", { className: "flag", textContent: x.flag }));
      return td;
    };
    tr.append(v(c.district, true), c.county ? v(c.county, false) : el("td"), v(c.state, false), d(c.county), d(c.state));
  });
  return el("div", { className: "table-wrap" }, t);
}

// Two districts side by side: one row per measure with both values and margins of error, the
// difference tested against both margins of error, the state for reference, and the source.
// `a` and `b` are { id, name, comparisons } from /api/districts/{id}. Explicit ARIA roles keep
// the table semantics when narrow screens restyle rows as stacked cards.
export function pairTable(metricIds, a, b) {
  const byId = (d, id) => d.comparisons.find(c => c.metric_id === id);
  const t = el("table", { className: "pair" });
  t.setAttribute("role", "table");
  const cols = ["Measure", a.name, b.name, `Difference (${a.id} vs ${b.id})`, "State"];
  const head = t.createTHead().insertRow();
  head.setAttribute("role", "row");
  // District codes never break at their hyphen.
  const nb = id => el("span", { style: "white-space:nowrap", textContent: id });
  const heads = [cols[0], cols[1], cols[2], el("span", {}, "Difference (", nb(a.id), " vs ", nb(b.id), ")"), cols[4]];
  heads.forEach(h => { const th = el("th", { scope: "col" }, h); th.setAttribute("role", "columnheader"); head.append(th); });
  const body = t.createTBody();
  const cell = (label, ...kids) => {
    const td = el("td", {}, ...kids);
    td.setAttribute("role", "cell");
    td.dataset.label = label;
    return td;
  };
  const value = (e, c) => {
    if (!e || e.value == null) return [el("span", { className: "val", textContent: "Not available" }),
      el("span", { className: "flag", textContent: "Not published for this district" })];
    const out = [el("span", { className: "val", textContent: fmtMetric(e.value, c.format) }),
      el("span", { className: "moe", textContent: fmtMoe(e.moe, c.format) })];
    if (e.low_reliability) out.push(el("span", { className: "flag", textContent: "Low reliability: large margin of error" }));
    return out;
  };
  metricIds.forEach(id => {
    const ca = byId(a, id), cb = byId(b, id);
    const c = ca || cb;
    const tr = body.insertRow();
    tr.setAttribute("role", "row");
    const th = el("th", { scope: "row" }, el("span", { className: "measure", textContent: c ? c.label : id }));
    th.setAttribute("role", "rowheader");
    tr.append(th);
    if (!c) {
      tr.append(cell(a.id, "Not available"), cell(b.id, "Not available"), cell("Difference", "not available"), cell("State", ""));
      th.append(el("span", { className: "flag", textContent: "Not in this tool's data yet" }));
      return;
    }
    // Both districts come from the same ACS release; name both geographies when the chambers differ.
    const geos = [...new Set([ca, cb].filter(Boolean).map(x => shortGeo(x.source.geography)))];
    const src = srcLine({ ...c.source, geography: geos.join(" and ") });
    th.append(src);
    const diff = ca && cb ? compareEstimates(ca.district, cb.district) : null;
    const d = diffText(diff, c.format);
    const same = d.text === "about the same" || d.text === "not available";
    const text = same ? d.text : `${diff.within_margin_of_error ? "about " : ""}${cellDiff(d.text)} in ${a.id}`;
    const diffCell = cell("Difference", el("span", { className: diff && diff.within_margin_of_error === false ? "diff real" : "diff", textContent: text }));
    if (d.flag) diffCell.append(el("span", { className: "flag", textContent: d.flag }));
    tr.append(cell(a.id, ...value(ca && ca.district, c)), cell(b.id, ...value(cb && cb.district, c)), diffCell,
      cell("State", fmtMetric(c.state && c.state.value, c.format)));
  });
  return el("div", { className: "table-wrap" }, t);
}

// Short county name, or "" when the district's county is not known.
export const countyOf = data => {
  const c = data.comparisons[0] && data.comparisons[0].county;
  return c && c.name ? shortCounty(c.name) : "";
};

// The API's broad "District profile" group, split by topic for reading. Display only: any
// measure not listed here falls into "Other measures", so nothing is ever dropped.
const PROFILE_TOPICS = [
  ["People and households", ["share_65_plus", "under_18_share", "kupuna_alone_share", "households_with_children_share",
    "single_parent_share", "disability_rate", "limited_english_share"]],
  ["Income and work", ["median_household_income", "poverty_rate", "kupuna_poverty_rate", "income_under_50k_share",
    "income_200k_plus_share", "social_security_share", "unemployment_rate"]],
  ["Housing", ["median_gross_rent", "rent_burden_rate", "owner_cost_burden_rate"]],
];

// Source data appendix: every measure (by topic, each section closed) and every published count,
// so a reader can check any figure against its Census table. Reference material, not a narrative.
export function renderDetails(data) {
  const county = countyOf(data);
  const wrap = el("div", { className: "source-data" });
  wrap.append(el("p", { className: "muted small", textContent:
    "Every measure, and the Census counts behind each percentage." }));

  const sections = [];
  const placed = new Set();
  PROFILE_TOPICS.forEach(([title, ids]) => {
    const comps = ids.map(id => data.comparisons.find(c => c.metric_id === id)).filter(Boolean);
    comps.forEach(c => placed.add(c.metric_id));
    sections.push([title, comps]);
  });
  const rest = data.comparisons.filter(c => !placed.has(c.metric_id));
  [...new Set(rest.map(c => c.group))].forEach(g =>
    sections.push([g === "District profile" ? "Other measures" : g, rest.filter(c => c.group === g)]));
  sections.filter(([, comps]) => comps.length).forEach(([title, comps]) => {
    const note = comps[0].group !== "District profile" && comps[0].group_note;
    const strip = comps.map(c => ({ ...c, label: c.label.replace(/^Employed residents working in:\s*/, "") }));
    wrap.append(el("details", { className: "sub-details" },
      el("summary", {}, title, el("span", { className: "count", textContent: ` ${comps.length} measures` })),
      el("div", { className: "inner" }, note ? el("p", { className: "muted small", textContent: note }) : null,
        comparisonTable(strip, county, { groupRows: false }))));
  });

  const t2 = el("table");
  const h2 = t2.createTHead().insertRow();
  ["Figure", "Value", "Source table"].forEach(h => h2.append(el("th", { scope: "col", textContent: h })));
  const b2 = t2.createTBody();
  data.facts.forEach(f => {
    const tr = b2.insertRow();
    tr.append(el("th", { scope: "row", textContent: f.label }));
    const unitFmt = v => f.unit === "dollars" ? "$" + Math.round(v).toLocaleString("en-US") : Math.round(v).toLocaleString("en-US");
    const vt = el("td");
    if (f.value_status === "ok") {
      vt.append(unitFmt(f.value));
      vt.append(el("span", { className: "moe", textContent: f.moe == null ? "margin of error not available"
        : `${f.moe_status === "derived" ? "about " : ""}±${unitFmt(f.moe)}` }));
    } else {
      vt.append("Not available", el("span", { className: "flag", textContent: "Too few cases to publish" }));
    }
    const st = el("td");
    tableLinks({ tables: f.source.tables }, st);
    st.append(` (${f.source.year})`);
    tr.append(vt, st);
  });
  if (data.facts.length) {
    wrap.append(el("details", { className: "sub-details" },
      el("summary", {}, "Published counts behind the percentages",
        el("span", { className: "count", textContent: ` ${data.facts.length} figures, for checking` })),
      el("div", { className: "inner" },
        el("p", { className: "muted small", textContent:
          "All figures: " + data.facts[0].source.publisher + ", " + data.facts[0].source.dataset + ". Geography: " + data.facts[0].source.geography +
          ". Reported directly for this geography; not estimated or apportioned by us." }),
        el("div", { className: "table-wrap" }, t2))));
  }
  return wrap;
}

// Figures published only for counties and the state (BEA, BLS, DHS, DOTAX). Never district figures.
// `ids` limits the rows to those indicator ids; omit for all.
export function contextBody(data, countyName, ids) {
  const ctx = (data.county_context || []).filter(c => !ids || ids.includes(c.indicator_id));
  if (!ctx.length) return null;
  const t = el("table");
  const h = t.createTHead().insertRow();
  ["Measure", countyName || "County", "State", "Source"].forEach(x => h.append(el("th", { scope: "col", textContent: x })));
  const b = t.createTBody();
  const fmt = (v, unit) => v == null ? "Not available" : unit === "dollars" ? "$" + Math.round(v).toLocaleString("en-US")
    : unit === "percent" ? v.toFixed(1) + "%" : Math.round(v).toLocaleString("en-US");
  ctx.forEach(c => {
    const tr = b.insertRow();
    const th = el("th", { scope: "row" }, c.label, el("span", { className: "moe", textContent: c.period }));
    if (c.caveat) th.append(el("span", { className: "flag", textContent: c.caveat }));
    tr.append(th);
    [c.county, c.state].forEach(e => {
      const td = el("td", {}, e ? fmt(e.value, c.unit) : "Not available");
      if (e && e.note) td.append(el("span", { className: "flag", textContent: e.note }));
      tr.append(td);
    });
    const st = el("td", {}, `${c.source.publisher}, ${c.source.dataset}, `);
    c.source.tables.forEach(x => st.append(el("a", { href: x.url, target: "_blank", rel: "noopener", textContent: x.table_id })));
    if (c.source.original_source) st.append(el("span", { className: "moe", textContent: "Original data: " + c.source.original_source.replace(/^Source:\s*/, "") }));
    st.append(el("span", { className: "moe", textContent: `${c.source.vintage ? c.source.vintage + ". " : ""}Downloaded ${c.source.retrieved_at}.` }));
    tr.append(st);
  });
  const records = ctx.some(c => /^(snap_|medquest_|dotax_.*_claims$)/.test(c.indicator_id));
  return el("div", {}, el("p", { className: "muted small", textContent: "County and state figures, not district figures." }),
    el("div", { className: "table-wrap" }, t),
    aboutBox("They describe the district's county (or island), cover different years, and have no published margin of error.",
      records && "SNAP and Med-QUEST counts are Hawaiʻi DHS program records; tax-credit claims are DOTAX records. Both show actual program use."));
}

export function renderContext(data, countyName) {
  const body = contextBody(data, countyName);
  return body && el("details", {}, el("summary", { textContent: "County and state context (not district figures)" }),
    el("div", { className: "inner" }, body));
}

// DOTAX tax areas that overlap the district. Whole-area figures, never district figures.
export function taxAreasBody(data, countyName) {
  const ta = data.tax_areas;
  if (!ta || !ta.areas.length) return null;
  const money = v => v == null ? "Not available" : "$" + Math.round(v).toLocaleString("en-US");
  const pct = v => v < 0.001 ? "under 0.1%" : (100 * v).toFixed(v < 0.1 ? 1 : 0) + "%";
  const ctx = (data.county_context || []).find(c => c.indicator_id === "dotax_median_agi");
  const t = el("table");
  const h = t.createTHead().insertRow();
  ["Tax area", ta.label, "Resident returns", "Returns claiming Hawaiʻi EITC", "District's residents in area", "Area's residents in district"]
    .forEach(x => h.append(el("th", { scope: "col", textContent: x })));
  const b = t.createTBody();
  ta.areas.forEach(a => {
    const tr = b.insertRow();
    const th = el("th", { scope: "row", textContent: a.name });
    if (a.relation !== "overlaps") th.append(el("span", { className: "flag", textContent: "Edge only (under 1% of district residents)" }));
    tr.append(th, el("td", { textContent: money(a.median_agi) }),
      el("td", { textContent: a.returns == null ? "Not available" : Math.round(a.returns).toLocaleString("en-US") }),
      el("td", { textContent: a.eitc_share == null ? "Not available" : (100 * a.eitc_share).toFixed(1) + "%" }),
      el("td", { textContent: a.share_of_district_residents ? pct(a.share_of_district_residents) : "none" }),
      el("td", { textContent: a.share_of_area_residents_in_district ? pct(a.share_of_area_residents_in_district) : "none" }));
  });
  if (ctx) {
    [[ctx.county, countyName || "County"], [ctx.state, "State"]].forEach(([e, name]) => {
      if (!e) return;
      const eitc = name === "State" && ta.credits && ta.credits.state_eitc_share != null ? (100 * ta.credits.state_eitc_share).toFixed(1) + "%" : "";
      b.insertRow().append(el("th", { scope: "row", textContent: `For comparison: ${name}` }), el("td", { textContent: money(e.value) }),
        el("td"), el("td", { textContent: eitc }), el("td"), el("td"));
    });
  }
  const src = el("p", { className: "muted small" }, `Source: ${ta.source.publisher}, ${ta.source.dataset}, `);
  ta.source.tables.forEach((x, i) => { if (i) src.append(", "); src.append(el("a", { href: x.url, target: "_blank", rel: "noopener", textContent: x.table_id })); });
  src.append(`. ${ta.source.vintage ? ta.source.vintage + ". " : ""}Downloaded ${ta.source.retrieved_at}. Matched to districts with: ${ta.overlap_source}`);
  if (ta.credits) {
    src.append(el("br"), `EITC claims: ${ta.credits.source.publisher}, ${ta.credits.source.dataset}, `,
      el("a", { href: ta.credits.source.url, target: "_blank", rel: "noopener", textContent: "Table A-7" }),
      `. Downloaded ${ta.credits.source.retrieved_at}. ${ta.credits.note}`);
  }
  return el("div", {}, el("p", { className: "muted small", textContent: "Whole tax areas that overlap the district, not district figures." }),
    el("div", { className: "table-wrap" }, t), src,
    aboutBox(ta.applies_to, "Resident shares use 2020 Census counts, only to match areas to the district.", ta.caveat,
      ta.district_residents_in_no_tax_area >= 0.01 && `${pct(ta.district_residents_in_no_tax_area)} of the district's 2020 residents live in ZIP codes DOTAX does not list.`));
}

export function renderTaxAreas(data, countyName) {
  const body = taxAreasBody(data, countyName);
  return body && el("details", {}, el("summary", { textContent: "Income by tax area" }),
    el("div", { className: "inner" }, body));
}

// "Residents likely eligible" estimates (programs.yaml `likely_eligible`, docs/ELIGIBILITY_METHOD.md).
// Counts of people, so no "higher/lower than" comparison: districts, counties and the state differ in size.
const STATUS_TEXT = {
  suppressed: "Not published: too few survey responses",
  not_applicable: "Not applicable for this area",
};
const leCount = e => e && e.value != null ? fmtCount(e.value) : "Not available";
const leMoe = e => !e ? "Not in this tool's data"
  : e.value == null ? (STATUS_TEXT[e.value_status] || "Not published for this area")
  : e.moe == null ? "margin of error not available"
  : `${e.moe_status === "derived" ? "about " : ""}±${fmtCount(e.moe)}`;
const leTitle = (le, p) => le.label ? le.label.split(":")[0] : `${p.name}: residents likely eligible`;
const LE_DIRECTION = { low: "Likely counts too few.", high: "Likely counts too many.", uncertain: "Could count too many or too few." };
const leProgs = data => (data.programs || []).filter(p => p.likely_eligible);

function leCard(p, countyName) {
  const le = p.likely_eligible;
  if (!le.estimated) {
    return el("article", { className: "fact missing" }, el("h3", { textContent: `${p.name}: residents likely eligible` }),
      el("p", { className: "big", textContent: "No estimate" }),
      el("p", { className: "moe", textContent: "No survey measure fits this program" }),
      el("details", { className: "calc" }, el("summary", { textContent: "Why" }), el("p", { textContent: le.reason })));
  }
  const d = le.district;
  const card = el("article", { className: "fact" }, el("h3", { textContent: leTitle(le, p) }),
    el("p", { className: "big", textContent: leCount(d) }),
    el("p", { className: "moe", textContent: `${d && d.value != null ? "residents, " : ""}${leMoe(d)}` }));
  if (d && d.low_reliability) card.append(el("p", { className: "flag", textContent: "Low reliability: large margin of error" }));
  card.append(el("p", { className: "muted small", style: "margin:0 0 1rem", textContent: `${le.caveat} ${LE_DIRECTION[le.direction] || ""}` }));
  const vs = el("div", { className: "vs" });
  [[le.county, countyName || "the county"], [le.state, "the state"]].forEach(([e, name]) => {
    if (e) vs.append(el("div", { className: "row" }, `In ${name}: `, el("span", { className: "hl", textContent: leCount(e) }), ` (${leMoe(e)})`));
  });
  card.append(vs);
  if (le.source) card.append(srcLine(le.source));
  card.append(leMethod(le));
  return card;
}

// How an estimate was made: the survey cut, the rule it stands in for, and which way it errs.
function leMethod(le) {
  const box = el("details", { className: "calc" }, el("summary", { textContent: "How it's estimated" }));
  [`Cut used: ${le.acs_cut}.`, `Program rule it approximates: ${le.rule}`,
    le.universe_label && `Counted among: ${le.universe_label} ${le.unit_note || ""}`, le.direction_text]
    .filter(Boolean).forEach(t => box.append(el("p", { textContent: t })));
  [["Why it may count too few", le.runs_low], ["Why it may count too many", le.runs_high], ["Could go either way", le.either_way]]
    .filter(([, xs]) => xs && xs.length).forEach(([title, xs]) => {
      box.append(el("p", { textContent: title + ":" }), el("ul", {}, ...xs.map(x => el("li", { textContent: x }))));
    });
  if (le.final_eligibility) box.append(el("p", { textContent: le.final_eligibility }));
  return box;
}

export function likelyEligibleBody(data) {
  const progs = leProgs(data);
  if (!progs.length) return null;
  const county = countyOf(data);
  return el("div", {},
    el("p", { className: "muted small", textContent:
      "Income test only, so these are estimates, not eligibility counts." }),
    el("div", { className: "facts" }, ...progs.map(p => leCard(p, county))));
}

// Comparison mode: both districts' estimates side by side (counts; no difference test).
export function likelyEligiblePair(a, b) {
  const progs = leProgs(a).filter(p => p.likely_eligible.estimated);
  if (!progs.length) return null;
  const other = id => (b.programs || []).find(x => x.id === id);
  const t = el("table");
  const head = t.createTHead().insertRow();
  ["Estimate", a.name, b.name, "State"].forEach(h => head.append(el("th", { scope: "col", textContent: h })));
  const body = t.createTBody();
  const cell = e => el("td", {}, leCount(e), el("span", { className: "moe", textContent: leMoe(e) }));
  progs.forEach(p => {
    const le = p.likely_eligible, lb = other(p.id) && other(p.id).likely_eligible;
    const th = el("th", { scope: "row" }, leTitle(le, p), el("span", { className: "moe", textContent: `${le.acs_cut}. ${le.caveat}` }));
    if (le.source) {
      const geos = [...new Set([le, lb].filter(x => x && x.source).map(x => shortGeo(x.source.geography)))];
      const src = srcLine({ ...le.source, geography: geos.join(" and ") });
      src.style.fontWeight = "normal";
      th.append(src);
    }
    body.insertRow().append(th, cell(le.district), cell(lb && lb.district), cell(le.state));
  });
  return el("div", {},
    el("p", { className: "muted small", textContent: "Counts of residents, so larger districts have larger counts. Income test only." }),
    el("div", { className: "table-wrap" }, t));
}

// ---------- where to apply: each program's official page, up front ----------
// Phone numbers and web addresses in program facts become links (tap to call, or open the page).
const LINKABLE = /https?:\/\/[^\s,;)]+[^\s,;).]|(?:1-)?(?:\(\d{3}\)\s?|\d{3}-)\d{3}-\d{4}/g;
function withLinks(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(LINKABLE)) {
    const web = m[0].startsWith("http");
    out.push(text.slice(last, m.index), web
      ? el("a", { href: m[0], target: "_blank", rel: "noopener", textContent: m[0].replace(/^https?:\/\//, "") })
      : el("a", { href: "tel:" + m[0].replace(/\D/g, ""), textContent: m[0] }));
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}
const agencyShort = a => a.split(/[,(]/)[0].trim();
const hostOf = url => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };

// The official-page button for one program. Opens the agency's own page in a new tab.
export function applyButton(p, cls = "") {
  return el("a", { className: `btn i-launch prog-go ${cls}`, href: p.url, target: "_blank", rel: "noopener" },
    "Who qualifies & how to apply",
    el("span", { className: "sr-only", textContent: `: ${p.name}, official ${agencyShort(p.agency)} page (opens in a new tab)` }));
}

// One tile per program: who it serves, how to apply, phone numbers, and the official link.
// `progs` are programs from /api/districts/{id} or /api/programs; `heading` is the tile title tag.
export function programLinks(progs, { heading = "h3", checkedOn = "" } = {}) {
  if (!progs || !progs.length) return null;
  const tiles = progs.map(p => {
    const how = (p.facts || []).filter(f => f.topic === "apply" || f.topic === "contact");
    const host = hostOf(p.url);
    return el("article", { className: "prog-tile" },
      el(heading, { textContent: p.name }),
      el("p", { className: "prog-serves", textContent: p.serves }),
      how.length ? el("ul", { className: "prog-how" }, ...how.map(f => el("li", {}, ...withLinks(f.text)))) : null,
      applyButton(p),
      el("p", { className: "print-url", textContent: p.url }), // printed copies keep the address
      el("p", { className: "src", textContent: `Official source: ${agencyShort(p.agency)}${host ? ` · ${host}` : ""}. Checked ${p.checked_on || checkedOn}.` }));
  });
  return el("div", {},
    el("p", { className: "muted small", textContent:
      "Each agency decides who qualifies." }),
    el("div", { className: "prog-links" }, ...tiles));
}

// Programs (pipeline/programs.yaml). Every fact is quoted from a saved official document. The
// same for every district: the district's own figures and estimates are elsewhere in the view.
export function programsBody(data) {
  const progs = data.programs || [];
  if (!progs.length) return null;
  const money = v => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: Number.isInteger(v) ? 0 : 2, maximumFractionDigits: 2 });
  const rowsTitle = { by_household_size: "Household size", by_children: "Children claimed", by_federal_agi: "Federal AGI", by_living_arrangement: "Living arrangement" };
  const rows = progs.map(p => {
    const body = el("div", { className: "inner" });
    const section = (title, topics) => {
      const fs = p.facts.filter(f => topics.includes(f.topic));
      if (fs.length) body.append(el("h4", { textContent: title }), el("ul", {}, ...fs.map(f => el("li", {}, ...withLinks(f.text)))));
    };
    section("Who may qualify", ["eligibility"]);
    const lim = p.income_limits;
    if (lim) {
      const rowsKey = Object.keys(lim).find(k => k.startsWith("by_"));
      const t = el("table");
      const h = t.createTHead().insertRow();
      [rowsTitle[rowsKey] || "", ...lim.columns].forEach(x => h.append(el("th", { scope: "col", textContent: x })));
      const tb = t.createTBody();
      Object.entries(lim[rowsKey]).slice(0, rowsKey === "by_household_size" ? 4 : 99).forEach(([k, vals]) => {
        const tr = tb.insertRow();
        tr.append(el("th", { scope: "row", textContent: k }));
        vals.forEach(v => tr.append(el("td", { textContent: money(v) })));
      });
      body.append(el("h4", { textContent: "Income limits" }),
        el("p", { className: "muted small", textContent: `${lim.description} ${lim.valid_for}.${rowsKey === "by_household_size" ? " Larger households: see the official page." : ""}` }),
        el("div", { className: "table-wrap" }, t));
    }
    section("How to apply", ["apply", "contact"]);
    section("What to bring", ["documents"]);
    section("Coming changes", ["change"]);
    if (p.uptake_note) body.append(el("h4", { textContent: "Program use" }), el("p", { className: "small", textContent: p.uptake_note }));
    body.append(el("p", { className: "src", textContent: `${p.agency}. Saved ${p.checked_on}.` }));
    return el("article", { className: "prog-row" },
      el("div", { className: "prog-row-head" },
        el("div", {}, el("h3", { textContent: p.name }), el("p", { className: "prog-serves", textContent: p.serves })),
        applyButton(p, "secondary small")),
      el("p", { className: "print-url", textContent: p.url }),
      el("details", { className: "prog-details" }, el("summary", { textContent: "Details: who qualifies, income limits, how to apply" }), body));
  });
  return el("div", {}, el("p", { className: "muted small", textContent: "Each agency decides who qualifies." }), ...rows);
}

// Map page: "Programs residents can apply for", always open, with a link to the report's
// Programs view (likely-eligible estimates, income limits, what to bring).
// `collapsed`: a closed dropdown, for district views (the programs are the same for every district).
export function programsHelp(progs, { title = "Programs residents can apply for", moreHref = "", checkedOn = "",
  moreText = "Likely-eligible estimates and income limits in the full report", collapsed = false } = {}) {
  const body = programLinks(progs, { heading: "h4", checkedOn });
  if (!body) return null;
  const more = moreHref ? el("p", { className: "prog-more" }, el("a", { href: moreHref, textContent: moreText })) : null;
  if (collapsed) {
    return el("details", { className: "prog-drop" },
      el("summary", {}, el("span", {}, title, el("span", { className: "count", textContent: ` ${progs.length} programs, with links to apply` }))),
      el("div", { className: "inner" }, body, more));
  }
  const s = el("section", { className: "prog-help" });
  s.setAttribute("aria-labelledby", "prog-help-h");
  s.append(el("h3", { id: "prog-help-h", textContent: title }), body, more);
  return s;
}

// Official permanent-resident population from the 2021 Reapportionment Plan, when available.
// One short line that still names its source and year (Business Rules: every figure cites source,
// year and geography); why it differs from the ACS estimate, and the page reference, open on demand.
// Printing opens it (beforeprint handlers), so exported summaries carry the full note.
export function planLine(data) {
  if (!data.plan) return null;
  return el("details", { className: "plan" },
    el("summary", {}, "Official redistricting population: ", el("strong", { textContent: data.plan.permanent_residents.toLocaleString("en-US") }),
      " · 2021 Reapportionment Plan (2020 Census base)"),
    el("p", {}, `${data.plan.note} `,
      el("a", { href: data.plan.source.url, target: "_blank", rel: "noopener", textContent: "Reapportionment Commission Final Report" }),
      `, Tables 9-10 (${data.plan.source.page}).`));
}


// A question asked in chat travels to the report page through this browser's storage, never the
// link, so it stays out of browser history, server logs and the Referer sent to other sites.
// The link carries only a random id; the report page reads the question once and deletes it.
const Q_PREFIX = "di-question-";
const Q_MAX_AGE_MS = 24 * 3600 * 1000;

function storeQuestion(question) {
  try {
    const id = Array.from(crypto.getRandomValues(new Uint8Array(9)), b => b.toString(16).padStart(2, "0")).join("");
    localStorage.setItem(Q_PREFIX + id, JSON.stringify({ q: question.slice(0, 200), t: Date.now() }));
    return id;
  } catch { return null; } // storage blocked: the report simply opens without the question
}

export function takeQuestion(id) {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) { // drop anything left over and stale
      const k = localStorage.key(i);
      if (k && k.startsWith(Q_PREFIX)) {
        const v = JSON.parse(localStorage.getItem(k) || "{}");
        if (!(v.t > Date.now() - Q_MAX_AGE_MS)) localStorage.removeItem(k);
      }
    }
    if (!id || !/^[0-9a-f]{18}$/.test(id)) return "";
    const v = JSON.parse(localStorage.getItem(Q_PREFIX + id) || "{}");
    localStorage.removeItem(Q_PREFIX + id);
    return typeof v.q === "string" ? v.q : "";
  } catch { return ""; }
}

export const reportUrl = (districtId, view, question) => {
  const u = new URL("/report.html", location.origin);
  u.searchParams.set("d", districtId);
  if (view && view !== "overview") u.searchParams.set("view", view);
  const qid = question ? storeQuestion(question) : null;
  if (qid) u.searchParams.set("qid", qid);
  return u.pathname + u.search;
};

// ---------- skeleton screens ----------
// Grey placeholders shaped like the content that is loading, so the page keeps its layout while
// data arrives. Each skeleton is hidden from screen readers; a short "Loading" line is read instead.
// The shimmer stops for people who ask for reduced motion (base.css).
export const sk = (cls = "", w = "") => el("span", { className: `sk ${cls}`, style: w ? `width:${w}` : "" });
const times = (n, f) => Array.from({ length: n }, (_, i) => f(i));
const WIDTHS = ["92%", "78%", "86%", "64%", "88%", "72%"];

export function skeleton(label, ...parts) {
  const vis = el("div", { className: "sk-wrap" }, ...parts);
  vis.setAttribute("aria-hidden", "true");
  return el("div", {}, el("p", { className: "sr-only", textContent: label }), vis);
}
export const skLines = (n = 2, w = WIDTHS) => el("div", { className: "sk-lines" }, ...times(n, i => sk("sk-line", w[i % w.length])));
// One headline card: title, big number, two comparison lines, source.
export const skFact = () => el("div", { className: "fact sk-card" }, sk("sk-line", "62%"), sk("sk-big", "48%"),
  el("div", { className: "sk-vs" }, sk("sk-line", "94%"), sk("sk-line", "80%"), sk("sk-line sk-small", "58%")));
export const skFacts = (n = 6) => el("div", { className: "facts" }, ...times(n, skFact));
export const skTable = (rows = 5) => el("div", { className: "sk-table" }, sk("sk-row sk-head"), ...times(rows, () => sk("sk-row")));
export const skAccordions = (n = 3) => el("div", { className: "sk-accs" }, ...times(n, i => el("div", { className: "sk-acc" }, sk("sk-line", ["36%", "24%", "44%"][i % 3]))));
export const skButtons = (n = 3) => el("div", { className: "sk-actions" }, ...times(n, () => sk("sk-btn")));
export const skTiles = (n = 3) => el("div", { className: "prog-links" }, ...times(n, () => el("div", { className: "prog-tile sk-card" },
  sk("sk-line", "70%"), skLines(2, ["90%", "60%"]), sk("sk-line", "84%"), sk("sk-btn sk-btn-wide"))));
// A district profile on the map page (one district, or two when comparing).
export const skProfile = (pair = false) => [sk("sk-h1", pair ? "70%" : "42%"),
  ...(pair ? [sk("sk-line", "52%"), sk("sk-line", "48%")] : [sk("sk-line", "38%")]),
  sk("sk-switch"), skFacts(6), skButtons(3), skAccordions(3)];
