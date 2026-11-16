// DOM builders for district figures, shared by the map page and the report page.
// Every value is inserted with textContent (via el()), never as HTML.
import { fmtMetric, fmtMoe, diffText, shortCounty, shortGeo, compareEstimates } from "./format.js";

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

// One headline figure: value, margin of error, comparison with county and state, source.
export function renderKeyFact(c) {
  const card = el("article", { className: "fact" }, el("h3", { textContent: c.label }));
  card.append(el("p", { className: "big", textContent: fmtMetric(c.district.value, c.format) }));
  card.append(el("p", { className: "moe", textContent: c.district.value != null ? fmtMoe(c.district.moe, c.format)
    : "The Census Bureau did not publish this figure for this district" }));
  if (c.district.low_reliability) card.append(el("p", { className: "flag small", style: "margin:0 0 0.5rem", textContent: "Low reliability: large margin of error. Treat with caution." }));
  const vs = el("div", { className: "vs" });
  const line = (name, ref) => {
    const d = diffText(ref && ref.difference, c.format);
    const row = el("div", { className: "row" }, el("span", { className: "hl", textContent: d.text }),
      ` than ${name} (${fmtMetric(ref && ref.value, c.format)})`);
    if (d.short) row.append(el("em", { textContent: d.short, title: d.flag }));
    return row;
  };
  if (c.county) vs.append(line(shortCounty(c.county.name), c.county));
  vs.append(line("the state", c.state));
  card.append(vs, srcLine(c.source));
  return card;
}

// Placeholder for a figure a preset asks for but the data store does not have.
export function missingFact(label) {
  return el("article", { className: "fact missing" }, el("h3", { textContent: label }),
    el("p", { className: "big", textContent: "Not available" }),
    el("p", { className: "moe", textContent: "Not in this tool's data yet" }));
}

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
      if (withMoe && e && e.low_reliability) td.append(el("span", { className: "flag", textContent: "Low reliability: the margin of error is large compared with the estimate. Treat with caution." }));
      return td;
    };
    const d = ref => {
      const x = diffText(ref && ref.difference, c.format);
      const td = el("td", {}, x.text);
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
  const cols = ["Measure", a.name, b.name, `Difference, ${a.id} compared with ${b.id}`, "State"];
  const head = t.createTHead().insertRow();
  head.setAttribute("role", "row");
  // District codes never break at their hyphen.
  const nb = id => el("span", { style: "white-space:nowrap", textContent: id });
  const heads = [cols[0], cols[1], cols[2], el("span", {}, "Difference, ", nb(a.id), " compared with ", nb(b.id)), cols[4]];
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
    if (e.low_reliability) out.push(el("span", { className: "flag", textContent: "Low reliability: large margin of error. Treat with caution." }));
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
    const text = same ? d.text : `${diff.within_margin_of_error ? "about " : ""}${d.text} in ${a.id}`;
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
    "For checking. Every measure for this district with its county and state, and the published Census counts behind each percentage. Percentages are calculated from those counts; margins of error use the Census Bureau's method for proportions. A difference inside its margin of error may not be a real difference." }));

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
        : `${f.moe_status === "derived" ? "about " : ""}plus or minus ${unitFmt(f.moe)}` }));
    } else {
      vt.append("Not available", el("span", { className: "flag", textContent: "Too few cases for the source to publish" }));
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
  const notes = ["These sources publish figures for counties (or islands) and the state only, not for legislative districts. They describe the county this district is in, not the district itself, and cover different years from the district figures. No margin of error is published for them."];
  if (ctx.some(c => /^(snap_|medquest_|dotax_.*_claims$)/.test(c.indicator_id)))
    notes.push("SNAP and Med-QUEST counts are program records from the Hawaiʻi Department of Human Services, and tax-credit claims are DOTAX records: how many people actually used each program.");
  return el("div", {}, ...notes.map(n => el("p", { className: "muted small", textContent: n })), el("div", { className: "table-wrap" }, t));
}

export function renderContext(data, countyName) {
  const body = contextBody(data, countyName);
  return body && el("details", {}, el("summary", { textContent: "County and state context (not figures for this district)" }),
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
  ["Tax area", ta.label, "Resident tax returns", "Returns claiming the Hawaiʻi EITC", "Share of this district's residents in the area", "Share of the area's residents in this district"]
    .forEach(x => h.append(el("th", { scope: "col", textContent: x })));
  const b = t.createTBody();
  ta.areas.forEach(a => {
    const tr = b.insertRow();
    const th = el("th", { scope: "row", textContent: a.name });
    if (a.relation !== "overlaps") th.append(el("span", { className: "flag", textContent: "Touches the edge of the district only (under 1% of its residents)" }));
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
  const notes = [ta.applies_to,
    "Residents are 2020 Census counts, used only to match areas to the district.",
    ta.caveat];
  if (ta.district_residents_in_no_tax_area >= 0.01)
    notes.push(`${pct(ta.district_residents_in_no_tax_area)} of this district's 2020 residents live in ZIP code areas that DOTAX does not list.`);
  return el("div", {}, ...notes.filter(Boolean).map(n => el("p", { className: "muted small", textContent: n })),
    el("div", { className: "table-wrap" }, t), src);
}

export function renderTaxAreas(data, countyName) {
  const body = taxAreasBody(data, countyName);
  return body && el("details", {}, el("summary", { textContent: "Income by tax area (areas that overlap this district)" }),
    el("div", { className: "inner" }, body));
}

// Programs (pipeline/programs.yaml). Every fact is quoted from a saved official document.
export function programsBody(data) {
  const progs = data.programs || [];
  if (!progs.length) return null;
  const inner = el("div", {},
    el("p", { className: "muted small", textContent:
      "Programs that serve groups found in this district. Figures under \"In this district\" are the district's own Census figures, chosen by us to show where each program may matter; they are not counts of eligible people. "
      + (progs[0].note || "") }));
  const val = (v, f) => v == null ? "Not available" : f === "dollars" ? "$" + Math.round(v).toLocaleString("en-US") : f === "percent" ? (100 * v).toFixed(1) + "%" : Math.round(v).toLocaleString("en-US");
  const money = v => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: Number.isInteger(v) ? 0 : 2, maximumFractionDigits: 2 });
  progs.forEach(p => {
    const box = el("details", { className: "program" }, el("summary", {}, p.name, el("span", { className: "moe", textContent: p.serves })));
    const body = el("div", { className: "inner" });
    if (p.district_measures.length) {
      const ul = el("ul");
      p.district_measures.forEach(m => {
        const li = el("li", {}, `${m.label}: `, el("strong", { textContent: val(m.district, m.format) }), ` (state ${val(m.state, m.format)})`);
        if (m.low_reliability) li.append(el("span", { className: "flag", textContent: " Low reliability: treat with caution." }));
        ul.append(li);
      });
      body.append(el("h4", { textContent: "In this district" }), ul);
    }
    if (p.uptake.length) {
      const ul = el("ul");
      p.uptake.forEach(u => ul.append(el("li", { textContent: `${u.label}, ${u.period}: county ${val(u.county)}, state ${val(u.state)} (program records)` })));
      body.append(el("h4", { textContent: "Program use in the county" }), ul);
    }
    if (p.uptake_note) body.append(el("p", { className: "small", textContent: p.uptake_note }));
    const section = (title, topics) => {
      const fs = p.facts.filter(f => topics.includes(f.topic));
      if (!fs.length) return;
      const ul = el("ul");
      fs.forEach(f => ul.append(el("li", { textContent: f.text })));
      body.append(el("h4", { textContent: title }), ul);
    };
    section("Who may qualify", ["eligibility"]);
    const lim = p.income_limits;
    if (lim) {
      const rowsKey = Object.keys(lim).find(k => k.startsWith("by_"));
      const t = el("table");
      const h = t.createTHead().insertRow();
      [rowsKey === "by_household_size" ? "Household size" : rowsKey === "by_children" ? "Children claimed" : rowsKey === "by_federal_agi" ? "Federal AGI" : "", ...lim.columns]
        .forEach(x => h.append(el("th", { scope: "col", textContent: x })));
      const tb = t.createTBody();
      Object.entries(lim[rowsKey]).slice(0, rowsKey === "by_household_size" ? 4 : 99).forEach(([k, vals]) => {
        const tr = tb.insertRow();
        tr.append(el("th", { scope: "row", textContent: k }));
        vals.forEach(v => tr.append(el("td", { textContent: money(v) })));
      });
      body.append(el("h4", { textContent: "Income limits" }),
        el("p", { className: "muted small", textContent: `${lim.description} ${lim.valid_for}.${rowsKey === "by_household_size" ? " Larger households: see the official source." : ""}` }),
        el("div", { className: "table-wrap" }, t));
    }
    section("How to apply", ["apply", "contact"]);
    section("What to bring", ["documents"]);
    section("Coming changes", ["change"]);
    body.append(el("p", { className: "src" }, `${p.agency}. `,
      el("a", { href: p.url, target: "_blank", rel: "noopener", textContent: "Official information" }),
      `. Saved ${p.checked_on}. ${p.note}`));
    box.append(body);
    inner.append(box);
  });
  return inner;
}

export function renderPrograms(data) {
  const body = programsBody(data);
  return el("details", {}, el("summary", { textContent: "Programs residents may qualify for" }),
    el("div", { className: "inner" }, body || el("p", { className: "muted", textContent: "No program information is loaded for this district." })));
}

// Official permanent-resident population from the 2021 Reapportionment Plan, when available.
export function planLine(data) {
  if (!data.plan) return null;
  return el("p", { className: "muted small plan" },
    `Official permanent-resident population (2021 Reapportionment Plan, 2020 Census base): ${data.plan.permanent_residents.toLocaleString("en-US")}. `,
    el("span", { textContent: data.plan.note + " " }),
    el("a", { href: data.plan.source.url, target: "_blank", rel: "noopener", textContent: "Reapportionment Commission Final Report" }),
    `, Tables 9-10 (${data.plan.source.page}).`);
}

export const reportUrl = (districtId, view, question) => {
  const u = new URL("/report.html", location.origin);
  u.searchParams.set("d", districtId);
  if (view && view !== "overview") u.searchParams.set("view", view);
  if (question) u.searchParams.set("q", question.slice(0, 200));
  return u.pathname + u.search;
};
