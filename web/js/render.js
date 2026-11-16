// DOM builders for district figures, shared by the map page and the report page.
// Every value is inserted with textContent (via el()), never as HTML.
import { fmtMetric, fmtMoe, diffText, shortCounty, shortGeo } from "./format.js";

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
    tr.append(el("th", { scope: "row", textContent: c.label }));
    const v = (e, withMoe) => {
      const td = el("td", {}, fmtMetric(e && e.value, c.format));
      if (withMoe && e && e.value != null) td.append(el("span", { className: "moe", textContent: fmtMoe(e.moe, c.format) }));
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

// Short county name, or "" when the district's county is not known.
export const countyOf = data => {
  const c = data.comparisons[0] && data.comparisons[0].county;
  return c && c.name ? shortCounty(c.name) : "";
};

// Every figure behind a profile: all comparisons plus every published count, with sources.
export function renderDetails(data) {
  const wrap = el("div");
  wrap.append(el("p", { className: "muted small", textContent:
    "Percentages are calculated from published counts. Margins of error use the Census Bureau's method for proportions. A difference inside its margin of error may not be a real difference." }),
    comparisonTable(data.comparisons, countyOf(data)));

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
    wrap.append(el("h3", { className: "subhead", textContent: "Every figure behind this profile" }),
      el("p", { className: "muted small", textContent:
        "All figures: " + data.facts[0].source.publisher + ", " + data.facts[0].source.dataset + ". Geography: " + data.facts[0].source.geography +
        ". Reported directly for this geography; not estimated or apportioned by us." }),
      el("div", { className: "table-wrap" }, t2));
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
  if (ctx.some(c => c.indicator_id.startsWith("snap_")))
    notes.push("SNAP counts are program records from the Hawaiʻi Department of Human Services: how many people the program actually served.");
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
  ["Tax area", ta.label, "Resident tax returns", "Share of this district's land in the area", "Share of the area's land in this district"]
    .forEach(x => h.append(el("th", { scope: "col", textContent: x })));
  const b = t.createTBody();
  ta.areas.forEach(a => {
    const tr = b.insertRow();
    const th = el("th", { scope: "row", textContent: a.name });
    if (a.relation !== "overlaps") th.append(el("span", { className: "flag", textContent: "Touches the edge of the district only (under 1% of its land)" }));
    tr.append(th, el("td", { textContent: money(a.median_agi) }),
      el("td", { textContent: a.returns == null ? "Not available" : Math.round(a.returns).toLocaleString("en-US") }),
      el("td", { textContent: pct(a.share_of_district_land) }), el("td", { textContent: pct(a.share_of_area_land_in_district) }));
  });
  if (ctx) {
    [[ctx.county, countyName || "County"], [ctx.state, "State"]].forEach(([e, name]) => {
      if (!e) return;
      b.insertRow().append(el("th", { scope: "row", textContent: `For comparison: ${name}` }), el("td", { textContent: money(e.value) }),
        el("td"), el("td"), el("td"));
    });
  }
  const src = el("p", { className: "muted small" }, `Source: ${ta.source.publisher}, ${ta.source.dataset}, `);
  ta.source.tables.forEach((x, i) => { if (i) src.append(", "); src.append(el("a", { href: x.url, target: "_blank", rel: "noopener", textContent: x.table_id })); });
  src.append(`. ${ta.source.vintage ? ta.source.vintage + ". " : ""}Downloaded ${ta.source.retrieved_at}. Matched to districts with: ${ta.overlap_source}`);
  const notes = [ta.applies_to,
    "Land area is only a rough guide to where people live: an area can cover much of a district's land but few of its residents.",
    ta.caveat];
  if (ta.district_land_in_no_tax_area >= 0.01)
    notes.push(`${pct(ta.district_land_in_no_tax_area)} of this district's land is outside every ZIP code area that DOTAX lists.`);
  return el("div", {}, ...notes.filter(Boolean).map(n => el("p", { className: "muted small", textContent: n })),
    el("div", { className: "table-wrap" }, t), src);
}

export function renderTaxAreas(data, countyName) {
  const body = taxAreasBody(data, countyName);
  return body && el("details", {}, el("summary", { textContent: "Income by tax area (areas that overlap this district)" }),
    el("div", { className: "inner" }, body));
}

export const reportUrl = (districtId, view, question) => {
  const u = new URL("/report.html", location.origin);
  u.searchParams.set("d", districtId);
  if (view && view !== "overview") u.searchParams.set("view", view);
  if (question) u.searchParams.set("q", question.slice(0, 200));
  return u.pathname + u.search;
};
