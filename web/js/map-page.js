// Map page (index.html): district list, map, profile and research assistant.
// Kept out of the HTML so the Content Security Policy can forbid inline scripts.
import { fmtMetric, fmtCount, fmtMoe, shortCounty, districtLabel, compareEstimates } from "/js/format.js";
import { $, el, tableLinks, renderKeyFact, renderPairFact, renderContext, renderTaxAreas, programsHelp, planLine, reportUrl, factKey, cardStyleSwitch, countyOf,
  skeleton, sk, skLines, skProfile, skAccordions } from "/js/render.js";
import { presetById, presetFor, districtFor, REPORT_TABS } from "/js/presets.js";
import { initPrintBuilder } from "/js/print-builder.js";
import { renderMarkdown } from "/js/markdown.js";

const COLORS = ["#defbe6", "#a7f0ba", "#42be65", "#198038", "#0e6027"]; // Carbon green 10, 20, 40, 60, 70
const NA_COLOR = "#c6c6c6";
const OCEAN = "#dde8ef";
const DIMMED = 0.5;    // opacity of the other districts while one is selected
const FIFTHS = ["lowest fifth", "second-lowest fifth", "middle fifth", "second-highest fifth", "highest fifth"];
const REDUCE_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;
const rgba = (hex, a) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16), a];
const STATE_EXTENT = { xmin: -160.5, ymin: 18.8, xmax: -154.6, ymax: 22.4 };
const AREAS = [ // quick zoom buttons; county ids come from the boundary file
  { label: "Statewide", county: null },
  { label: "Hawaiʻi Island", county: "COUNTY-001" },
  { label: "Maui, Molokaʻi, Lānaʻi", county: "COUNTY-009" },
  { label: "Oʻahu", county: "COUNTY-003" },
  { label: "Kauaʻi", county: "COUNTY-007" },
];
// The map offers a short list of headline measures (the brief's core indicators and the outreach
// example). The API serves every measure; the report and the assistant still use all of them.
const MAP_CHOICES = [
  ["median_household_income", "Household income"],
  ["poverty_rate", "Poverty"],
  ["share_65_plus", "Kūpuna (65+)"],
  ["rent_burden_rate", "Rent burden"],
  ["unemployment_rate", "Unemployment"],
  ["poor_households_without_snap_share", "Below poverty, no SNAP"],
];
const state = { chamber: "house", districtId: null, vsId: null, mapData: null, districts: [], edges: [] };
let view, fillLayer, hoverLayer, selLayer, GraphicCtor, ExtentCtor;
let placeLabels = () => {}; // set once the map loads

// ---------- district numbers on the map ----------
// Drawn as HTML over the map in the page's own font (Esri's map labels need its font service,
// which this site doesn't use). Each number sits inside its district, on the widest horizontal
// stretch of its largest piece, and shows only where it fits without overlapping another.
const ringArea = r => { let a = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) a += (r[j][0] + r[i][0]) * (r[j][1] - r[i][1]); return Math.abs(a / 2); };
function labelSpot(geom) {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  const rings = polys.reduce((best, p) => ringArea(p[0]) > ringArea(best[0]) ? p : best);
  const ys = rings[0].map(c => c[1]);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  let best = null;
  [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8].forEach(f => {
    const y = y0 + f * (y1 - y0);
    const xs = [];
    rings.forEach(r => { for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const a = r[j], b = r[i];
      if ((a[1] > y) !== (b[1] > y)) xs.push(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
    } });
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) { // inside the shape between each pair of crossings
      const w = xs[k + 1] - xs[k];
      if (!best || w > best.w * 1.25) best = { w, y, x0: xs[k], x1: xs[k + 1] }; // favor the middle lines
    }
  });
  return best && { lon: (best.x0 + best.x1) / 2, lat: best.y, x0: best.x0, x1: best.x1 };
}

// ---------- summary ----------
// The map page shows the headline figures; the report page (report.html) has every view.
let redraw = null; // redraws the current profile, e.g. after the card view changes
let shown = null;   // the profile on screen, { data, dataVs }, for the print builder
const popLineOf = data => {
  const pop = data.facts.find(f => f.indicator_id === "pop_total");
  return pop && pop.value_status === "ok"
    ? `About ${fmtCount(pop.value)} residents (${fmtMoe(pop.moe, "count")})` : "Population not available";
};
// Switching the card view redraws in place and keeps focus on the switch.
const viewSwitch = () => cardStyleSwitch(() => {
  if (redraw) redraw();
  const b = document.querySelector('#main .cs-switch button[aria-pressed="true"]');
  if (b) b.focus();
});

function renderProfile(data) {
  redraw = () => renderProfile(data);
  shown = { data, dataVs: null };
  const comps = data.comparisons;
  const keyComps = presetById("overview").metrics.map(id => comps.find(c => c.metric_id === id)).filter(Boolean);
  const county = comps[0] && comps[0].county ? shortCounty(comps[0].county.name) : "";
  const popLine = popLineOf(data);

  const facts = el("div", { className: "facts" });
  keyComps.forEach(c => facts.append(renderKeyFact(c)));

  const programs = programsHelp(data.programs, { moreHref: reportUrl(data.geo_id, "programs"), collapsed: true });
  const actions = el("div", { className: "actions" },
    el("a", { className: "btn i-forward", href: reportUrl(data.geo_id), textContent: "Full report" }),
    el("button", { className: "btn secondary i-print", type: "button", textContent: "Print / PDF", onclick: () => printBuilder.open() }),
    el("button", { className: "btn secondary i-copy", type: "button", textContent: "Copy link",
      onclick: e => { navigator.clipboard && navigator.clipboard.writeText(location.href); e.target.textContent = "Link copied"; } }));

  const context = renderContext(data, county);
  const taxAreas = renderTaxAreas(data, county);
  $("main").replaceChildren(
    el("h2", { className: "district", textContent: data.name }),
    el("p", { className: "sub", textContent: county ? `${county} · ${popLine}` : popLine }),
    ...[planLine(data), viewSwitch(), facts, factKey(), actions, programs, taxAreas, context].filter(Boolean));
}

// Two districts side by side: the overview figures as paired cards, each difference tested
// against both margins of error. The full comparison (every view) is on the report page.
function renderPairProfile(a, b) {
  redraw = () => renderPairProfile(a, b);
  shown = { data: a, dataVs: b };
  const A = { id: a.geo_id, name: a.name }, B = { id: b.geo_id, name: b.name };
  const byId = (d, id) => d.comparisons.find(c => c.metric_id === id);
  const facts = el("div", { className: "facts" });
  presetById("overview").metrics.forEach(id => {
    const ca = byId(a, id), cb = byId(b, id);
    if (ca || cb) facts.append(renderPairFact(ca, cb, A, B));
  });
  const who = (d, cls) => el("p", { className: `pair-who ${cls}` }, el("strong", { textContent: d.geo_id }),
    ` · ${[countyOf(d), popLineOf(d)].filter(Boolean).join(" · ")}`);
  const full = `${reportUrl(a.geo_id)}&vs=${encodeURIComponent(b.geo_id)}`;
  const actions = el("div", { className: "actions" },
    el("a", { className: "btn i-forward", href: full, textContent: "Full comparison" }),
    el("button", { className: "btn secondary i-print", type: "button", textContent: "Print / PDF", onclick: () => printBuilder.open() }),
    el("button", { className: "btn secondary i-copy", type: "button", textContent: "Copy link",
      onclick: e => { navigator.clipboard && navigator.clipboard.writeText(location.href); e.target.textContent = "Link copied"; } }),
    // Leaves the comparison, so it looks different from the actions on it: borderless, with a close icon.
    el("button", { className: "btn ghost i-close stop-compare", type: "button", textContent: "Stop comparing",
      onclick: () => { state.vsId = null; selectDistrict(a.geo_id, true); } }));
  // Programs and their official pages are the same for every district.
  const programs = programsHelp(a.programs, { moreHref: `${reportUrl(a.geo_id, "programs")}&vs=${encodeURIComponent(b.geo_id)}`,
    moreText: "Likely-eligible estimates for both districts in the full comparison", collapsed: true });
  const note = a.geo_type !== b.geo_type ? el("p", { className: "pair-note", textContent:
    "House and Senate districts overlap, so the margin-of-error test is approximate." }) : null;
  $("main").replaceChildren(
    el("h2", { className: "district", textContent: `${a.name} vs ${b.name}` }),
    ...[who(a, "a"), who(b, "b"), note, viewSwitch(), facts, factKey(undefined, { a: A.id, b: B.id }), actions, programs].filter(Boolean));

}

// ---------- research assistant ----------
// Answers stay short; each one links to the report view that holds the full picture.
const chat = { history: [], busy: false, n: 0 };

function chatContext() {
  $("chat-ctx").textContent = !state.districtId ? "No district selected"
    : `Selected: ${districtLabel(state.districtId)}${state.vsId ? `, compared with ${districtLabel(state.vsId)}` : ""}`;
}
function openChat() { $("chat").hidden = false; $("chat-open").hidden = true; chatContext(); }
function closeChat() { $("chat").hidden = true; $("chat-open").hidden = false; $("chat-open").focus(); }

function reportCard(question, trace) {
  const id = districtFor(trace, state.districtId);
  if (!id) return null;
  const preset = presetById(presetFor(question, trace));
  return el("a", { className: "report-card", href: reportUrl(id, preset.id, question) },
    el("div", {}, el("strong", { textContent: "Open full report" }),
      el("span", { className: "meta", textContent: `${districtLabel(id)} · ${preset.label}` })),
    el("span", { className: "go", textContent: "→", ariaHidden: "true" }));
}

function sourcesBlock(sources, id) {
  const ol = el("ol");
  sources.forEach(s => {
    const li = el("li", { id: `src-${id}-${s.id}`, value: s.id.slice(1) },
      `${s.publisher}, ${s.dataset}, ${s.period}. ${s.geography}. `);
    (s.tables || []).forEach((t, k) => { if (k) li.append(", "); li.append(el("a", { href: t.url, target: "_blank", rel: "noopener", textContent: t.table_id })); });
    if (s.note) li.append(el("span", { textContent: ` ${s.note.replace(/^Source:\s*/, "")}` }));
    ol.append(li);
  });
  return el("details", { className: "sources" }, el("summary", { textContent: `Sources (${sources.length})` }), ol);
}

async function ask(question) {
  question = (question || "").trim();
  if (!question || chat.busy) return;
  openChat();
  chat.busy = true; $("chat-send").disabled = true;
  chat.history.push({ role: "user", content: question });
  const log = $("chat-log");
  log.append(el("div", { className: "msg user", textContent: question }));
  const pending = el("div", { className: "msg thinking" }, "Looking up the figures…", skeleton("", skLines(3)));
  log.append(pending); log.scrollTop = log.scrollHeight;
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chat.history, district_id: state.districtId }) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `The assistant returned an error (${r.status}).`);
    const id = ++chat.n;
    const box = el("div", { className: "msg" }, renderMarkdown(data.answer || "(No answer.)", id));
    const card = reportCard(question, data.trace || []);
    if (card) box.append(card);
    // Numbers the server could not match to the data the assistant looked up.
    if (data.unverified_numbers && data.unverified_numbers.length) {
      box.append(el("p", { className: "flag answer-check", textContent:
        `Check before using: ${data.unverified_numbers.join(", ")} ${data.unverified_numbers.length === 1 ? "is" : "are"} not in the data looked up. Rely on the sources below.` }));
    }
    if (data.sources && data.sources.length) box.append(sourcesBlock(data.sources, id));
    if (data.trace && data.trace.length) {
      box.append(el("details", {}, el("summary", { textContent: `Data looked up (${data.trace.length})` }),
        el("pre", { textContent: data.trace.map(t => `${t.tool}(${JSON.stringify(t.input)})${t.error ? "  → error" : ""}`).join("\n") })));
    }
    pending.replaceWith(box);
    // The server signs each answer; it ignores earlier answers sent back without a valid signature.
    chat.history.push({ role: "assistant", content: data.answer || "", signature: data.signature || null });
  } catch (e) {
    pending.replaceWith(el("div", { className: "msg error", textContent: e.message }));
    chat.history.pop();
  } finally {
    chat.busy = false; $("chat-send").disabled = false;
    log.scrollTop = log.scrollHeight;
  }
}

// A citation number opens its (collapsed) source list before jumping to the source.
$("chat-log").addEventListener("click", e => {
  const a = e.target.closest("sup a");
  if (!a) return;
  const target = document.getElementById(a.getAttribute("href").slice(1));
  const box = target && target.closest("details");
  if (box) box.open = true;
});
$("ask-form").addEventListener("submit", e => { e.preventDefault(); const q = $("ask-input").value; $("ask-input").value = ""; ask(q); });
$("chat-form").addEventListener("submit", e => { e.preventDefault(); const q = $("chat-input").value; $("chat-input").value = ""; ask(q); });
$("chat-input").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); } });
$("chat-close").addEventListener("click", closeChat);
$("chat-open").addEventListener("click", () => { openChat(); $("chat-input").focus(); });
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("chat").hidden && $("chat").contains(document.activeElement)) closeChat(); });
$("chat-clear").addEventListener("click", () => { chat.history = []; $("chat-log").replaceChildren(); $("chat-input").focus(); });

// Print / PDF on a district opens the same print builder as the full report (packet, one-page
// brief or resident handout). Ctrl+P / Cmd+P opens it too while a district is shown; on the
// landing page, or from the builder's "Print the screen as is", the browser prints the page.
const printBuilder = initPrintBuilder(() => {
  if (!shown) return null;
  const { data, dataVs } = shown;
  const year = data.comparisons[0] ? data.comparisons[0].source.year : "";
  const sub = dataVs
    ? [year && `Census ACS 5-year ${year}`, "Differences tested against both margins of error"]
    : [countyOf(data), popLineOf(data), year && `Census ACS 5-year ${year}`];
  const link = new URL(reportUrl(data.geo_id) + (dataVs ? `&vs=${encodeURIComponent(dataVs.geo_id)}` : ""), location.origin).href;
  return { data, dataVs, view: "overview", tabs: REPORT_TABS, sub: sub.filter(Boolean).join(" · "), link };
});
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "p" && shown && !document.querySelector("dialog[open]")) {
    e.preventDefault();
    printBuilder.open();
  }
});

// Open every section when printing so the page prints as a complete one-pager.
window.addEventListener("beforeprint", () => document.querySelectorAll("#main details").forEach(d => d.open = true));

// ---------- selection ----------
const ringsOf = g => g.type === "Polygon" ? g.coordinates : g.coordinates.flat(1);
const polygon = g => ({ type: "polygon", rings: ringsOf(g), spatialReference: { wkid: 4326 } });

// Fill for one district: its class color, faded when another district is selected.
function fillSymbol(g) {
  const sel = state.districtId;
  const alpha = !sel || g.attributes.geo_id === sel ? 1 : DIMMED;
  const base = g.attributes.k < 0 ? NA_COLOR : COLORS[g.attributes.k];
  return { type: "simple-fill", color: rgba(base, alpha), outline: { color: [22, 22, 22, 0.2], width: 0.5 } };
}
const outline = (color, width) => ({ type: "simple-fill", color: [0, 0, 0, 0], outline: { color, width } });

// Selected district: the others fade, and it gets a slim dark edge over a white halo. A district
// being compared (same chamber only, since the map shows one chamber) gets a dashed edge.
function drawSelection(zoom) {
  selLayer.removeAll();
  placeLabels();
  fillLayer.graphics.forEach(g => { g.symbol = fillSymbol(g); });
  const find = id => id && state.mapData && state.mapData.features.find(x => x.properties.geo_id === id);
  const f = find(state.districtId), fv = find(state.vsId);
  if (!f) { if (zoom) showState(); return; }
  holdState = false;
  const geometry = polygon(f.geometry);
  selLayer.addMany([new GraphicCtor({ geometry, symbol: outline([255, 255, 255, 0.95], 3) }),
                    new GraphicCtor({ geometry, symbol: outline("#393939", 1.5) })]);
  if (fv) {
    const gv = polygon(fv.geometry);
    selLayer.addMany([new GraphicCtor({ geometry: gv, symbol: outline([255, 255, 255, 0.95], 3) }),
                      new GraphicCtor({ geometry: gv, symbol: { ...outline("#393939", 1.5), outline: { color: "#393939", width: 1.5, style: "dash" } } })]);
  }
  if (zoom) {
    markArea(null);
    let ext = selLayer.graphics.getItemAt(0).geometry.extent;
    if (fv) ext = ext.clone().union(selLayer.graphics.getItemAt(2).geometry.extent);
    goTo(ext.expand(fv ? 1.6 : 2.6));
  }
}
const goTo = (target, animate = true) => view.when(() => view.goTo(target, { animate: animate && !REDUCE_MOTION }).catch(() => {}));
function goExtent(e, animate = true) {
  goTo(new ExtentCtor({ ...e, spatialReference: { wkid: 4326 } }).expand(1.08), animate);
}
// With no district chosen the map shows the whole state. Until someone pans or zooms, it re-fits
// whenever its box changes size (fonts loading, the header settling, the layout switching between
// the landing page and a district), so the state is never left cropped or off-center.
let holdState = !/^(HD|SD)-\d{1,2}$/i.test(new URL(location.href).searchParams.get("d") || "");
function showState(animate = true) {
  holdState = true;
  markArea(AREAS[0].label);
  goExtent(STATE_EXTENT, animate);
}
function countyExtent(countyId) {
  if (!state.mapData) return null;
  let x0 = 999, y0 = 999, x1 = -999, y1 = -999;
  const walk = a => { if (typeof a[0] === "number") { x0 = Math.min(x0, a[0]); x1 = Math.max(x1, a[0]); y0 = Math.min(y0, a[1]); y1 = Math.max(y1, a[1]); } else a.forEach(walk); };
  state.mapData.features.filter(f => f.properties.county_geo_id === countyId).forEach(f => walk(f.geometry.coordinates));
  return x0 === 999 ? null : { xmin: x0, ymin: y0, xmax: x1, ymax: y1 };
}

// District data, fetched once per page visit.
const loaded = new Map();
function fetchDistrict(id) {
  if (!loaded.has(id)) loaded.set(id, fetch("/api/districts/" + encodeURIComponent(id)).then(async res => {
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    return res.json();
  }).catch(err => { loaded.delete(id); throw err; }));
  return loaded.get(id);
}

// "Compare with": every district except the one chosen, both chambers.
function fillVsList() {
  const sel = $("vs");
  sel.replaceChildren(new Option("None", ""));
  [["house", "House"], ["senate", "Senate"]].forEach(([type, label]) => {
    const g = el("optgroup", { label });
    state.districts.filter(d => d.geo_type === type && d.geo_id !== state.districtId).forEach(d => g.append(new Option(d.name, d.geo_id)));
    sel.append(g);
  });
  sel.disabled = !state.districtId;
  sel.closest(".field").hidden = !state.districtId;
  sel.value = state.vsId || "";
}

async function selectDistrict(id, zoom = true) {
  state.districtId = id || null;
  if (!state.districtId || state.vsId === state.districtId) state.vsId = null;
  const vs = state.vsId;
  $("district").value = id || "";
  $("intro").hidden = !!id;
  document.querySelector(".layout").classList.toggle("is-landing", !id);
  fillVsList();
  chatContext();
  $("report-link").hidden = !id;
  if (id) $("report-link").href = vs ? `${reportUrl(id)}&vs=${encodeURIComponent(vs)}` : reportUrl(id);
  const url = new URL(location.href);
  id ? url.searchParams.set("d", id) : url.searchParams.delete("d");
  vs ? url.searchParams.set("vs", vs) : url.searchParams.delete("vs");
  history.replaceState(null, "", url);
  drawSelection(zoom);
  shown = null;
  if (!id) { renderLanding(); return; }
  $("main").replaceChildren(skeleton(`Loading ${districtLabel(id)}${vs ? ` and ${districtLabel(vs)}` : ""}…`, ...skProfile(!!vs)));
  try {
    const [data, dataVs] = await Promise.all([fetchDistrict(id), vs ? fetchDistrict(vs) : null]);
    if (state.districtId !== id || state.vsId !== vs) return; // user already moved on
    dataVs ? renderPairProfile(data, dataVs) : renderProfile(data);
  } catch (err) {
    $("main").replaceChildren(el("p", { className: "error", textContent: "Could not load this district. " + err.message }));
  }
}

// ---------- find a district by place (no AI: GET /api/find, the assistant's own lookup) ----------
const KIND = { zip_code: "ZIP code", census_place: "Town", neighborhood: "Neighborhood", tax_area: "DOTAX tax area" };
// A match's districts as two labeled rows, House then Senate, each in the order the API gives (largest share first).
function findChambers(ds) {
  return [["House", "HD-"], ["Senate", "SD-"]].map(([ch, prefix]) => {
    const mine = ds.filter(d => d.district_id.startsWith(prefix));
    if (!mine.length) return null;
    const list = el("div", { className: "find-list" }, ...mine.map(d => el("button", { type: "button", className: "find-go",
      onclick: () => goFind(d.district_id), ariaLabel: d.name + (d.share_of_residents ? `, ${d.share_of_residents} of residents` : "") },
      d.name.replace(/^(House|Senate) /, ""), d.share_of_residents ? el("span", { className: "find-share", textContent: d.share_of_residents }) : null)));
    return el("div", { className: "find-ch" }, el("span", { className: "find-ch-label", textContent: ch }), list);
  }).filter(Boolean);
}
function findResults(r) {
  const out = [];
  r.matches.forEach(m => {
    if (m.district_id) { // a district number
      out.push(el("div", { className: "find-hit" }, el("button", { type: "button", className: "find-go",
        textContent: m.name, onclick: () => goFind(m.district_id) })));
      return;
    }
    const kind = Object.keys(KIND).find(k => m[k]);
    const title = el("p", { className: "find-title" }, el("strong", { textContent: m[kind] }),
      el("span", { className: "find-kind", textContent: m.county ? `${KIND[kind]}, ${m.county}` : KIND[kind] }));
    const body = (m.districts || []).length ? findChambers(m.districts)
      : [el("p", { className: "muted small", textContent: "No residents found for this ZIP code (it may be PO-box only)." })];
    out.push(el("div", { className: "find-hit" }, title, ...body));
  });
  if (!out.length) return [el("p", { className: "small", textContent: "No match. Try a town, neighborhood, ZIP code or district number. Street addresses aren't supported." })];
  const shares = r.matches.some(m => (m.districts || []).some(d => d.share_of_residents));
  const hood = r.matches.some(m => m.neighborhood);
  if (shares) out.push(el("p", { className: "find-note", textContent: "% = share of the area's 2020 residents in each district (2020 Census blocks)." }));
  if (hood) out.push(el("p", { className: "find-note", textContent: "Neighborhoods are placed by one reference point; edges may fall in the next district." }));
  return out;
}
function closeFind() { $("find-results").hidden = true; }
function goFind(id) { closeFind(); openDistrict(id); }
$("find-form").addEventListener("submit", async e => {
  e.preventDefault();
  const q = $("find-input").value.trim();
  if (!q) return;
  const box = $("find-results");
  box.hidden = false;
  box.replaceChildren(skeleton("Searching…", sk("sk-line", "40%"), el("div", { className: "find-list" }, sk("sk-pill", "8rem"), sk("sk-pill", "6.5rem")),
    sk("sk-line", "30%"), el("div", { className: "find-list" }, sk("sk-pill", "8rem"))));
  try {
    const res = await fetch("/api/find?q=" + encodeURIComponent(q.slice(0, 100)));
    if (!res.ok) throw new Error(res.statusText);
    const r = await res.json();
    box.replaceChildren(el("button", { type: "button", className: "find-close", ariaLabel: "Close results", textContent: "×", onclick: () => { closeFind(); $("find-input").focus(); } }),
      ...findResults(r));
  } catch (err) {
    box.replaceChildren(el("p", { className: "error small", textContent: "Search failed. " + err.message }));
  }
});
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("find-results").hidden) { closeFind(); $("find-input").focus(); } });
document.addEventListener("click", e => { if (!$("find-form").contains(e.target)) closeFind(); });

// ---------- landing: one outreach opportunity, statewide ----------
// Households below the poverty level that did not receive SNAP (ACS B22003), with the districts
// that have the most of them. Every number shows its margin of error and source (GET /api/outreach).
let outreachData = null;
let programList = null; // GET /api/programs: every program with its official page, for the landing

// Landing placeholders: the outreach highlight (headline number, two ranked lists).
const outreachSkeleton = () => [skeleton("Loading the outreach highlight…", sk("sk-line", "14rem"), sk("sk-h2", "82%"), sk("sk-block"),
  skLines(2, ["70%", "55%"]), el("div", { className: "where" }, ...[0, 1].map(() => el("div", {}, sk("sk-line", "50%"), skLines(5, ["100%"])))))];
function landingSkeleton() {
  $("main").replaceChildren(el("section", { className: "outreach" }, ...outreachSkeleton()));
}

// Landing: the opening section (index.html) explains the site; below it, one outreach example
// (the brief's Success Scenario) and the programs list.
function renderLanding() {
  const slot = el("section", { className: "outreach" }, ...outreachSkeleton());
  slot.setAttribute("aria-labelledby", "outreach-h");
  const progSlot = el("div", { className: "prog-landing" }, skAccordions(1));
  $("main").replaceChildren(slot, progSlot);
  const fill = d => { if (slot.isConnected) slot.replaceChildren(...outreachSection(d)); };
  const fillProgs = d => { if (progSlot.isConnected) progSlot.replaceChildren(...[programsHelp(d.programs, { checkedOn: d.checked_on, collapsed: true })].filter(Boolean)); };
  if (programList) fillProgs(programList);
  else fetch("/api/programs").then(r => r.ok ? r.json() : Promise.reject(new Error(r.statusText)))
    .then(d => { programList = d; fillProgs(d); })
    .catch(() => progSlot.remove());
  if (outreachData) return fill(outreachData);
  fetch("/api/outreach").then(r => r.ok ? r.json() : Promise.reject(new Error(r.statusText)))
    .then(d => { outreachData = d; fill(d); })
    .catch(() => slot.remove()); // the landing still works without the highlight
}

async function openDistrict(id) {
  const chamber = id.startsWith("HD") ? "house" : "senate";
  if (chamber !== state.chamber) {
    state.chamber = chamber;
    $("ch-house").setAttribute("aria-pressed", chamber === "house");
    $("ch-senate").setAttribute("aria-pressed", chamber === "senate");
    state.districtId = id;
    fillDistrictList();
    await drawMap();
  }
  await selectDistrict(id, true);
  const h = document.querySelector("#main h2.district");
  if (h) { h.tabIndex = -1; h.focus(); }
}

function outreachSection(d) {
  const s = d.state;
  const pct = v => (v * 100).toFixed(0) + "%";
  const list = (title, rows) => {
    const ol = el("ol");
    rows.forEach(r => ol.append(el("li", {}, el("button", { type: "button", onclick: () => openDistrict(r.geo_id) },
      el("span", { className: "name", textContent: r.name }),
      el("span", { className: "n", textContent: fmtCount(r.count) + " households" }),
      el("span", { className: "detail", textContent:
        `${fmtMoe(r.count_moe, "count")} · ${fmtMetric(r.share, "percent")} (${fmtMoe(r.share_moe, "percent")}) of its households below poverty`
        + (r.low_reliability ? " · low reliability" : "") })))));
    const [a, b] = rows;
    const close = a && b && compareEstimates({ value: a.count, moe: a.count_moe }, { value: b.count, moe: b.count_moe });
    return el("div", {}, el("h3", { textContent: title }), ol,
      close && close.within_margin_of_error !== false
        ? el("p", { className: "order-note", textContent: `${a.name} and ${b.name} are within each other's margin of error, so treat them as tied.` })
        : null);
  };
  const src = el("p", { className: "src" }, `Source: ${d.source.publisher}, ACS 5-year ${d.source.year}, `);
  tableLinks(d.source, src);
  src.append(" · State and legislative districts · Income rule: ",
    el("a", { href: d.program.url, target: "_blank", rel: "noopener", textContent: "Hawaiʻi DHS SNAP page" }), ".");
  return [
    el("p", { className: "kicker", textContent: "Outreach example: SNAP" }),
    el("h2", { id: "outreach-h", textContent: `${pct(s.share)} of Hawaiʻi households below the poverty line get no SNAP` }),
    el("div", { className: "headline" },
      el("p", { className: "big", textContent: fmtCount(s.count) }),
      el("p", { className: "big-label", textContent: `households statewide (${fmtMoe(s.count_moe, "count")}), ${fmtMetric(s.share, "percent")} (${fmtMoe(s.share_moe, "percent")}) of those below poverty. Their incomes are well under SNAP's limit.` })),
    el("div", { className: "where" }, list("Most households, House", d.house), list("Most households, Senate", d.senate)),
    el("details", { className: "about" }, el("summary", { textContent: "About these figures" }),
      el("div", { className: "inner" }, el("p", { textContent: d.income_rule }),
        el("p", { textContent: `${d.caveat} Final eligibility is decided by ${d.program.agency.split(" (")[0]}.` }))),
    el("div", { className: "actions" },
      el("button", { className: "btn secondary", type: "button", textContent: "Show on map",
        onclick: () => { $("metric").value = d.metric_id; drawMap(); } })),
    src,
  ];
}

function fillDistrictList() {
  const sel = $("district");
  sel.replaceChildren(new Option("Choose...", ""));
  state.districts.filter(d => d.geo_type === state.chamber).forEach(d => sel.append(new Option(d.name, d.geo_id)));
  const prefix = state.chamber === "house" ? "HD" : "SD";
  sel.value = state.districtId && state.districtId.startsWith(prefix) ? state.districtId : "";
}
function setChamber(chamber) {
  state.chamber = chamber;
  $("ch-house").setAttribute("aria-pressed", chamber === "house");
  $("ch-senate").setAttribute("aria-pressed", chamber === "senate");
  if (state.districtId && !state.districtId.startsWith(chamber === "house" ? "HD" : "SD")) state.districtId = null;
  fillDistrictList();
  drawMap().then(() => selectDistrict(state.districtId, false));
}

// ---------- map ----------
let mapDrawn = null;
async function drawMap() {
  const metric = $("metric").value;
  if (!metric) return;
  $("mapnote").textContent = "Loading map...";
  try {
    const res = await fetch(`/api/map/${metric}/${state.chamber}`);
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    state.mapData = await res.json();
    mapDrawn(state.mapData);
  } catch (err) {
    $("mapnote").replaceChildren(el("span", { className: "error", textContent: "Could not load the map. " + err.message }));
    $("map-sk").hidden = true;
  }
}

require(["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/Extent",
  "esri/geometry/support/webMercatorUtils", "esri/core/reactiveUtils"],
  function (Map, MapView, GraphicsLayer, Graphic, Extent, webMercatorUtils, reactiveUtils) {
    GraphicCtor = Graphic; ExtentCtor = Extent;
    fillLayer = new GraphicsLayer();
    hoverLayer = new GraphicsLayer();
    selLayer = new GraphicsLayer();
    const map = new Map();
    map.addMany([fillLayer, hoverLayer, selLayer]); // hover and selection outlines sit on top
    view = new MapView({ container: "viewDiv", map, background: { color: OCEAN },
      extent: new Extent({ ...STATE_EXTENT, spatialReference: { wkid: 4326 } }).expand(1.05),
      ui: { components: ["zoom", "attribution"] } }); // Esri requires its attribution (pipeline/sources.yaml)

    // Keep the map on Hawaiʻi: the center can't be panned off the islands, and zooming out stops a
    // little past the whole state, so nobody gets lost in empty ocean. No rotation either.
    view.constraints.rotationEnabled = false;
    const limitZoomOut = () => {
      if (!view.width || !view.height) return;
      const m = 111319.49; // meters per degree, as the view measures scale
      const res = Math.max((STATE_EXTENT.xmax - STATE_EXTENT.xmin) * m / view.width,
                           (STATE_EXTENT.ymax - STATE_EXTENT.ymin) * m / Math.cos(20.6 * Math.PI / 180) / view.height);
      view.constraints.minScale = res * (96 / 0.0254) * 1.8; // pixels at 96 dpi; 1.8 = some room around the state
    };
    view.when(() => {
      const box = new Extent({ ...STATE_EXTENT, spatialReference: { wkid: 4326 } });
      view.constraints.geometry = view.spatialReference.isWebMercator ? webMercatorUtils.geographicToWebMercator(box) : box;
      limitZoomOut();
    });
    view.on("resize", () => { limitZoomOut(); if (holdState) goExtent(STATE_EXTENT, false); });
    // Moving the map by hand (drag, wheel, keys, double-click or the zoom buttons) lets it stay put.
    view.on(["drag", "mouse-wheel", "double-click", "key-down"], () => { holdState = false; });
    view.when(() => view.container.addEventListener("click", e => { if (e.target.closest(".esri-zoom")) holdState = false; }));

    const quantileEdges = (values, n) => {
      const v = values.filter(x => x !== null).sort((a, b) => a - b);
      return Array.from({ length: n + 1 }, (_, i) => v[Math.min(v.length - 1, Math.floor(i * (v.length - 1) / n))]);
    };
    const classOf = (v, edges) => { // 0..4, or -1 when not available
      if (v == null) return -1;
      for (let i = COLORS.length - 1; i > 0; i--) if (v >= edges[i]) return i;
      return 0;
    };

    // District numbers: one label per district, re-placed whenever the map moves.
    let labels = [];
    const labelBox = el("div", { className: "map-labels" });
    labelBox.setAttribute("aria-hidden", "true"); // the district list is the accessible alternative
    view.when(() => (view.container.querySelector(".esri-view-surface") || view.container).append(labelBox));
    const screenOf = (lon, lat) => {
      const [x, y] = view.spatialReference.isWebMercator ? webMercatorUtils.lngLatToXY(lon, lat) : [lon, lat];
      return view.toScreen({ type: "point", x, y, spatialReference: view.spatialReference });
    };
    const buildLabels = data => {
      labels = data.features.map(f => {
        const spot = labelSpot(f.geometry);
        const id = f.properties.geo_id;
        const node = el("span", { className: "map-label", textContent: id.replace(/^[A-Z]+-/, "") });
        return spot && { id, spot, node };
      }).filter(Boolean);
      labelBox.replaceChildren(...labels.map(l => l.node));
      labels.forEach(l => { l.w = 7.5 * l.node.textContent.length + 4; l.h = 14; }); // size before the map is on screen
    };
    placeLabels = () => {
      if (!view || !view.ready || !labels.length) return;
      const placed = [];
      const sel = [state.districtId, state.vsId];
      const order = labels.map(l => {
        const p = screenOf(l.spot.lon, l.spot.lat), a = screenOf(l.spot.x0, l.spot.lat), b = screenOf(l.spot.x1, l.spot.lat);
        return { l, p, room: p ? Math.abs(b.x - a.x) : 0, pick: sel.includes(l.id) };
      }).sort((x, y) => (y.pick - x.pick) || (y.room - x.room)); // selected first, then the roomiest
      order.forEach(({ l, p, room, pick }) => {
        const inView = p && p.x > 0 && p.y > 0 && p.x < view.width && p.y < view.height;
        const box = inView && { x0: p.x - l.w / 2 - 2, x1: p.x + l.w / 2 + 2, y0: p.y - l.h / 2, y1: p.y + l.h / 2 };
        const fits = inView && (pick || room >= l.w + 6) && !placed.some(q => q.x0 < box.x1 && box.x0 < q.x1 && q.y0 < box.y1 && box.y0 < q.y1);
        l.node.hidden = !fits;
        l.node.classList.toggle("sel", pick);
        if (fits) { placed.push(box); l.node.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%)`; }
      });
    };
    reactiveUtils.watch(() => [view.extent, view.width, view.height], () => placeLabels());

    mapDrawn = function (data) {
      const edges = quantileEdges(data.features.map(f => f.properties.value), COLORS.length);
      state.edges = edges;
      fillLayer.removeAll();
      hoverLayer.removeAll();
      data.features.forEach(f => {
        const g = new Graphic({
          geometry: polygon(f.geometry),
          attributes: { geo_id: f.properties.geo_id, name: f.properties.name, value: f.properties.value,
                        k: classOf(f.properties.value, edges) },
        });
        g.symbol = fillSymbol(g);
        fillLayer.add(g);
      });
      renderLegend(data, edges);
      buildLabels(data);
      $("map-sk").hidden = true;
      const s = data.meta.source;
      const note = el("span", {}, `Census ACS 5-year ${s.year}, `);
      tableLinks(s, note);
      note.append(` · Boundaries: Hawaiʻi Statewide GIS Program (OPSD), 2022`);
      $("mapnote").replaceChildren(note);
      drawSelection(false);
    };

    const districtAt = async event => {
      const hit = await view.hitTest(event, { include: [fillLayer] });
      const r = hit.results.find(x => x.graphic && x.graphic.attributes && x.graphic.attributes.geo_id);
      return r ? r.graphic : null;
    };
    // Clicking a district selects it and centers the map on it.
    view.on("click", async e => { const g = await districtAt(e); if (g) selectDistrict(g.attributes.geo_id, true); });

    // Hover: thin white outline on the district, and a tooltip that follows the pointer.
    let hoverPending = false, hoverId = null;
    const tip = $("map-tip");
    const clearHover = () => { hoverLayer.removeAll(); hoverId = null; tip.hidden = true; $("hover").textContent = ""; };
    view.on("pointer-move", e => {
      if (hoverPending) return;
      hoverPending = true;
      requestAnimationFrame(async () => {
        const g = await districtAt(e);
        hoverPending = false;
        if (!g) { clearHover(); return; }
        const a = g.attributes;
        const value = a.value == null ? "Not available" : fmtMetric(a.value, state.mapData.meta.format);
        if (a.geo_id !== hoverId) {
          hoverId = a.geo_id;
          hoverLayer.removeAll();
          hoverLayer.add(new Graphic({ geometry: g.geometry, symbol: outline([255, 255, 255, 1], 2) }));
          tip.replaceChildren(el("strong", { textContent: a.name }),
            el("span", { className: "tip-value", textContent: value }),
            el("span", { className: "tip-note", textContent: a.k < 0 ? "Not published"
              : `${FIFTHS[a.k][0].toUpperCase() + FIFTHS[a.k].slice(1)} of ${state.chamber === "house" ? "House" : "Senate"} districts` }));
          $("hover").textContent = `${a.name}: ${value}`;
        }
        // Keep the tooltip inside the map: flip it left or up near the right or bottom edge.
        tip.hidden = false;
        const w = tip.offsetWidth, h = tip.offsetHeight;
        const x = e.x + 16 + w > view.width ? e.x - 16 - w : e.x + 16;
        const y = e.y + 16 + h > view.height ? e.y - 16 - h : e.y + 16;
        tip.style.transform = `translate(${Math.max(0, x)}px, ${Math.max(0, y)}px)`;
      });
    });
    view.on("pointer-leave", clearHover);
    init();
  });

// Legend: a segmented color bar, the class limits under it, and where the state falls on it.
function renderLegend(data, edges) {
  const fmt = v => fmtMetric(v, data.meta.format);
  const pct = i => `${i * 100 / COLORS.length}%`;
  const bar = el("div", { className: "lg-bar" }, ...COLORS.map(c => el("span", { style: `background:${c}` })));
  const ticks = el("div", { className: "lg-ticks" }, ...edges.map((v, i) => el("span", {
    className: i === 0 ? "first" : i === edges.length - 1 ? "last" : "", style: `left:${pct(i)}`, textContent: fmt(v) })));
  const parts = [el("span", { className: "title", textContent: data.meta.label })];
  const s = data.meta.state_value;
  if (s != null && edges[0] != null) {
    let k = 0;
    while (k < COLORS.length - 1 && s >= edges[k + 1]) k++;
    const span = edges[k + 1] - edges[k];
    const within = span > 0 ? Math.min(1, Math.max(0, (s - edges[k]) / span)) : 0.5;
    const at = Math.min(92, Math.max(8, (k + within) * 100 / COLORS.length));
    parts.push(el("div", { className: "lg-state" },
      el("span", { style: `left:${at}%`, textContent: `State ${fmt(s)}` })));
  }
  parts.push(bar, ticks);
  if (data.features.some(f => f.properties.value == null))
    parts.push(el("span", { className: "lg-na" }, el("span", { className: "sw" }), "Not available"));
  $("legend").replaceChildren(...parts);
  $("legend").setAttribute("aria-label", `${data.meta.label}: five groups from ${fmt(edges[0])} to ${fmt(edges[edges.length - 1])}. State: ${fmt(s)}.`);
}

function markArea(label) {
  $("islands").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.textContent === label));
}
function buildIslandButtons() {
  $("islands").replaceChildren(...AREAS.map(a => el("button", { type: "button", textContent: a.label,
    onclick: () => { if (!a.county) return showState(); holdState = false; markArea(a.label); goExtent(countyExtent(a.county) || STATE_EXTENT); } })));
  markArea(AREAS[0].label);
}

async function init() {
  try {
    const [dRes, mRes] = await Promise.all([fetch("/api/districts"), fetch("/api/map/metrics")]);
    if (!dRes.ok || !mRes.ok) throw new Error("Data service unavailable");
    state.districts = await dRes.json();
    const metrics = await mRes.json();
    const served = new Set(metrics.map(m => m.metric_id));
    $("metric").replaceChildren(...MAP_CHOICES.filter(([id]) => served.has(id)).map(([id, label]) => new Option(label, id)));
    $("metric").value = MAP_CHOICES[0][0];

    buildIslandButtons();

    const params = new URL(location.href).searchParams;
    const known = id => id && state.districts.some(d => d.geo_id === id);
    const wanted = (params.get("d") || "").toUpperCase(), wantedVs = (params.get("vs") || "").toUpperCase();
    if (known(wanted)) {
      state.districtId = wanted;
      state.chamber = state.districtId.startsWith("HD") ? "house" : "senate";
      if (known(wantedVs) && wantedVs !== wanted) state.vsId = wantedVs;
    }
    $("ch-house").setAttribute("aria-pressed", state.chamber === "house");
    $("ch-senate").setAttribute("aria-pressed", state.chamber === "senate");
    fillDistrictList();
    await drawMap();
    if (state.districtId) { $("district").value = state.districtId; selectDistrict(state.districtId, true); }
    else { renderLanding(); showState(false); } // land on the whole state, fitted to the map's final size
  } catch (err) {
    $("main").replaceChildren(el("p", { className: "error", textContent: "Could not load. " + err.message }));
  }
}

// Keep the sticky map just below the sticky header, whatever its height.
const setHdr = () => document.documentElement.style.setProperty("--hdr", $("hdr").offsetHeight + "px");
window.addEventListener("resize", setHdr); window.addEventListener("load", setHdr); setHdr();

$("ch-house").addEventListener("click", () => setChamber("house"));
$("ch-senate").addEventListener("click", () => setChamber("senate"));
$("district").addEventListener("change", e => selectDistrict(e.target.value, true));
$("vs").addEventListener("change", e => { state.vsId = e.target.value || null; selectDistrict(state.districtId, true); });

$("metric").addEventListener("change", () => drawMap());

// First paint: a skeleton of whatever the link asks for, until the map and data are ready.
{
  const q = new URL(location.href).searchParams;
  const d = (q.get("d") || "").toUpperCase(), vs = (q.get("vs") || "").toUpperCase();
  if (/^(HD|SD)-\d{1,2}$/.test(d)) {
    $("intro").hidden = true;
    document.querySelector(".layout").classList.remove("is-landing");
    $("main").replaceChildren(skeleton(`Loading ${districtLabel(d)}…`, ...skProfile(/^(HD|SD)-\d{1,2}$/.test(vs))));
  } else landingSkeleton();
  $("vs").closest(".field").hidden = !/^(HD|SD)-\d{1,2}$/.test(d);
}

// "District Insight" (top left) returns to the landing page in place once the map is ready;
// before that, the link simply loads "/".
$("brand").addEventListener("click", e => {
  if (!selLayer || !mapDrawn) return;
  e.preventDefault();
  closeFind();
  state.vsId = null;
  selectDistrict(null, true); // re-fits the whole state and marks "Statewide"
  window.scrollTo({ top: 0, behavior: REDUCE_MOTION ? "auto" : "smooth" });
});

// Opening section buttons: jump to the place search, or open the assistant.
$("intro-find").addEventListener("click", () => {
  const f = $("find-input");
  f.scrollIntoView({ block: "center", behavior: REDUCE_MOTION ? "auto" : "smooth" });
  f.focus({ preventScroll: true });
});
$("intro-ask").addEventListener("click", () => { openChat(); $("chat-input").focus(); });
