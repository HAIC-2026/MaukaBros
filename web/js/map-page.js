// Map page (index.html): district list, map, profile and research assistant.
// Kept out of the HTML so the Content Security Policy can forbid inline scripts.
import { fmtMetric, fmtCount, fmtMoe, shortCounty, districtLabel, compareEstimates } from "/js/format.js";
import { $, el, tableLinks, renderKeyFact, renderContext, renderTaxAreas, renderPrograms, planLine, reportUrl } from "/js/render.js";
import { presetById, presetFor, districtFor } from "/js/presets.js";
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
const state = { chamber: "house", districtId: null, mapData: null, districts: [], edges: [] };
let view, fillLayer, hoverLayer, selLayer, GraphicCtor, ExtentCtor;

// ---------- summary ----------
// The map page shows the headline figures; the report page (report.html) has every view.
function renderProfile(data) {
  const comps = data.comparisons;
  const keyComps = presetById("overview").metrics.map(id => comps.find(c => c.metric_id === id)).filter(Boolean);
  const pop = data.facts.find(f => f.indicator_id === "pop_total");
  const county = comps[0] && comps[0].county ? shortCounty(comps[0].county.name) : "";

  const popLine = pop && pop.value_status === "ok"
    ? `About ${fmtCount(pop.value)} residents (${fmtMoe(pop.moe, "count")})` : "Population not available";

  const facts = el("div", { className: "facts" });
  keyComps.forEach(c => facts.append(renderKeyFact(c)));

  const programs = renderPrograms(data);
  const actions = el("div", { className: "actions" },
    el("a", { className: "btn i-launch", href: reportUrl(data.geo_id), target: "_blank", rel: "noopener" },
      "Open full report", el("span", { className: "sr-only", textContent: " (opens in a new tab)" })),
    el("button", { className: "btn secondary i-print", type: "button", textContent: "Print or save as PDF", onclick: () => window.print() }),
    el("button", { className: "btn secondary i-copy", type: "button", textContent: "Copy link to this district",
      onclick: e => { navigator.clipboard && navigator.clipboard.writeText(location.href); e.target.textContent = "Link copied"; } }));

  const context = renderContext(data, county);
  const taxAreas = renderTaxAreas(data, county);
  $("main").replaceChildren(
    el("h2", { className: "district", textContent: data.name }),
    el("p", { className: "sub", textContent: county ? `${county} · ${popLine}` : popLine }),
    ...[planLine(data), facts, actions, taxAreas, context, programs].filter(Boolean));
}

// ---------- research assistant ----------
// Answers stay short; each one links to the report view that holds the full picture.
const chat = { history: [], busy: false, n: 0 };

function chatContext() {
  $("chat-ctx").textContent = state.districtId ? `Selected: ${districtLabel(state.districtId)}` : "No district selected";
}
function openChat() { $("chat").hidden = false; chatContext(); }

function reportCard(question, trace) {
  const id = districtFor(trace, state.districtId);
  if (!id) return null;
  const preset = presetById(presetFor(question, trace));
  return el("a", { className: "report-card", href: reportUrl(id, preset.id, question), target: "_blank", rel: "noopener" },
    el("div", {}, el("strong", { textContent: "Open full report" }),
      el("span", { className: "meta", textContent: `${districtLabel(id)} · ${preset.label} · opens in a new tab` })),
    el("span", { className: "go", textContent: "↗", ariaHidden: "true" }));
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
  const pending = el("div", { className: "msg thinking", textContent: "Looking up the figures…" });
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
        `Check before using: ${data.unverified_numbers.join(", ")} ${data.unverified_numbers.length === 1 ? "was" : "were"} not found in the data the assistant looked up. Rely on the sources below and the district pages.` }));
    }
    if (data.sources && data.sources.length) box.append(sourcesBlock(data.sources, id));
    if (data.trace && data.trace.length) {
      box.append(el("details", {}, el("summary", { textContent: `What the assistant looked up (${data.trace.length})` }),
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
$("chat-close").addEventListener("click", () => { $("chat").hidden = true; $("ask-input").focus(); });
$("chat-clear").addEventListener("click", () => { chat.history = []; $("chat-log").replaceChildren(); $("chat-input").focus(); });

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

// Selected district: the others fade, and it gets a slim dark edge over a white halo.
function drawSelection(zoom) {
  selLayer.removeAll();
  fillLayer.graphics.forEach(g => { g.symbol = fillSymbol(g); });
  const f = state.mapData && state.mapData.features.find(x => x.properties.geo_id === state.districtId);
  if (!f) { if (zoom) goExtent(STATE_EXTENT); return; }
  const geometry = polygon(f.geometry);
  selLayer.addMany([new GraphicCtor({ geometry, symbol: outline([255, 255, 255, 0.95], 3) }),
                    new GraphicCtor({ geometry, symbol: outline("#393939", 1.5) })]);
  if (zoom) { markArea(null); goTo(selLayer.graphics.getItemAt(0).geometry.extent.expand(2.6)); }
}
const goTo = target => view.when(() => view.goTo(target, { animate: !REDUCE_MOTION }).catch(() => {}));
function goExtent(e) {
  goTo(new ExtentCtor({ ...e, spatialReference: { wkid: 4326 } }).expand(1.08));
}
function countyExtent(countyId) {
  if (!state.mapData) return null;
  let x0 = 999, y0 = 999, x1 = -999, y1 = -999;
  const walk = a => { if (typeof a[0] === "number") { x0 = Math.min(x0, a[0]); x1 = Math.max(x1, a[0]); y0 = Math.min(y0, a[1]); y1 = Math.max(y1, a[1]); } else a.forEach(walk); };
  state.mapData.features.filter(f => f.properties.county_geo_id === countyId).forEach(f => walk(f.geometry.coordinates));
  return x0 === 999 ? null : { xmin: x0, ymin: y0, xmax: x1, ymax: y1 };
}

async function selectDistrict(id, zoom = true) {
  state.districtId = id || null;
  $("district").value = id || "";
  chatContext();
  $("report-link").hidden = !id;
  if (id) $("report-link").href = reportUrl(id);
  const url = new URL(location.href);
  id ? url.searchParams.set("d", id) : url.searchParams.delete("d");
  history.replaceState(null, "", url);
  drawSelection(zoom);
  if (!id) { renderLanding(); return; }
  $("main").replaceChildren(el("p", { className: "muted", textContent: "Loading..." }));
  try {
    const res = await fetch("/api/districts/" + encodeURIComponent(id));
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    if (state.districtId !== id) return; // user already moved on
    renderProfile(data);
  } catch (err) {
    $("main").replaceChildren(el("p", { className: "error", textContent: "Could not load this district. " + err.message }));
  }
}

// ---------- landing: one outreach opportunity, statewide ----------
// Households below the poverty level that did not receive SNAP (ACS B22003), with the districts
// that have the most of them. Every number shows its margin of error and source (GET /api/outreach).
let outreachData = null;

function renderLanding() {
  const intro = el("div", { className: "empty" }, el("h2", { textContent: "Who lives in your district?" }),
    el("p", { textContent: "Choose a district above, or click one on the map, to see a sourced profile of its residents." }));
  const slot = el("section", { className: "outreach" });
  slot.setAttribute("aria-labelledby", "outreach-h");
  $("main").replaceChildren(intro, slot);
  const fill = d => { if (slot.isConnected) slot.replaceChildren(...outreachSection(d)); };
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
        `${fmtMoe(r.count_moe, "count")} · ${fmtMetric(r.share, "percent")} of its households below poverty (${fmtMoe(r.share_moe, "percent")})`
        + (r.low_reliability ? " · low reliability: large margin of error" : "") })))));
    const [a, b] = rows;
    const close = a && b && compareEstimates({ value: a.count, moe: a.count_moe }, { value: b.count, moe: b.count_moe });
    return el("div", {}, el("h3", { textContent: title }), ol,
      close && close.within_margin_of_error !== false
        ? el("p", { className: "order-note", textContent: `The order of ${a.name} and ${b.name} may not be a real difference: it is within the margin of error.` })
        : null);
  };
  const src = el("p", { className: "src" }, `Source: ${d.source.publisher}, ACS 5-year ${d.source.year}, `);
  tableLinks(d.source, src);
  src.append(". State of Hawaiʻi and Census state legislative districts. Income rule: ",
    el("a", { href: d.program.url, target: "_blank", rel: "noopener", textContent: "Hawaiʻi DHS SNAP page" }), ".");
  return [
    el("p", { className: "kicker", textContent: "Outreach opportunity · SNAP" }),
    el("h2", { id: "outreach-h", textContent: `${pct(s.share)} of Hawaiʻi households below the poverty level did not receive SNAP` }),
    el("div", { className: "headline" },
      el("p", { className: "big", textContent: fmtCount(s.count) }),
      el("p", { className: "big-label", textContent: `households statewide had incomes below the poverty level and did not receive SNAP in the past 12 months: ${fmtMetric(s.share, "percent")} of all households below poverty.` }),
      el("p", { className: "moe", textContent: `Count ${fmtMoe(s.count_moe, "count")} households; share ${fmtMoe(s.share_moe, "percent")}.` })),
    el("p", { className: "why", textContent: `These households have incomes under the poverty level, well inside SNAP's income limit. ${d.income_rule}` }),
    el("div", { className: "where" }, list("Most households, House", d.house), list("Most households, Senate", d.senate)),
    el("p", { className: "caveat", textContent: `${d.caveat} Final eligibility is always decided by ${d.program.agency.split(" (")[0]}.` }),
    el("div", { className: "actions" },
      el("button", { className: "btn secondary", type: "button", textContent: "Color the map by this measure",
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
  }
}

require(["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/Extent"],
  function (Map, MapView, GraphicsLayer, Graphic, Extent) {
    GraphicCtor = Graphic; ExtentCtor = Extent;
    fillLayer = new GraphicsLayer();
    hoverLayer = new GraphicsLayer();
    selLayer = new GraphicsLayer();
    const map = new Map();
    map.addMany([fillLayer, hoverLayer, selLayer]); // hover and selection outlines sit on top
    view = new MapView({ container: "viewDiv", map, background: { color: OCEAN },
      extent: new Extent({ ...STATE_EXTENT, spatialReference: { wkid: 4326 } }).expand(1.05),
      ui: { components: ["zoom", "attribution"] } }); // Esri requires its attribution (pipeline/sources.yaml)

    const quantileEdges = (values, n) => {
      const v = values.filter(x => x !== null).sort((a, b) => a - b);
      return Array.from({ length: n + 1 }, (_, i) => v[Math.min(v.length - 1, Math.floor(i * (v.length - 1) / n))]);
    };
    const classOf = (v, edges) => { // 0..4, or -1 when not available
      if (v == null) return -1;
      for (let i = COLORS.length - 1; i > 0; i--) if (v >= edges[i]) return i;
      return 0;
    };

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
      const s = data.meta.source;
      const note = el("span", {}, `Census ACS 5-year ${s.year}, `);
      tableLinks(s, note);
      note.append(`. Districts drawn from the Hawaiʻi Statewide GIS Program (OPSD) 2022 boundaries.`);
      $("mapnote").replaceChildren(note);
      drawSelection(false);
    };

    const districtAt = async event => {
      const hit = await view.hitTest(event, { include: [fillLayer] });
      const r = hit.results.find(x => x.graphic && x.graphic.attributes && x.graphic.attributes.geo_id);
      return r ? r.graphic : null;
    };
    view.on("click", async e => { const g = await districtAt(e); if (g) selectDistrict(g.attributes.geo_id, false); });

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
            el("span", { className: "tip-note", textContent: a.k < 0 ? "Not published for this district"
              : `In the ${FIFTHS[a.k]} of ${state.chamber === "house" ? "House" : "Senate"} districts` }));
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
    onclick: () => { markArea(a.label); goExtent(a.county ? countyExtent(a.county) || STATE_EXTENT : STATE_EXTENT); } })));
  markArea(AREAS[0].label);
}

async function init() {
  try {
    const [dRes, mRes] = await Promise.all([fetch("/api/districts"), fetch("/api/map/metrics")]);
    if (!dRes.ok || !mRes.ok) throw new Error("Data service unavailable");
    state.districts = await dRes.json();
    const metrics = await mRes.json();
    const groups = {};
    metrics.forEach(m => (groups[m.group] = groups[m.group] || el("optgroup", { label: m.group })).append(new Option(m.label, m.metric_id)));
    $("metric").replaceChildren(...Object.values(groups));
    $("metric").value = "median_household_income";
    buildIslandButtons();

    const wanted = new URL(location.href).searchParams.get("d");
    if (wanted && /^(HD|SD)-\d+$/i.test(wanted)) {
      state.districtId = wanted.toUpperCase();
      state.chamber = state.districtId.startsWith("HD") ? "house" : "senate";
    }
    $("ch-house").setAttribute("aria-pressed", state.chamber === "house");
    $("ch-senate").setAttribute("aria-pressed", state.chamber === "senate");
    fillDistrictList();
    await drawMap();
    if (state.districtId) { $("district").value = state.districtId; selectDistrict(state.districtId, true); }
    else renderLanding();
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
$("metric").addEventListener("change", () => drawMap());
