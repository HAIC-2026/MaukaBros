// Report page (report.html): district report, views, comparison of two districts.
// Kept out of the HTML so the Content Security Policy can forbid inline scripts.
import { $, el, renderKeyFact, renderPairFact, missingFact, comparisonTable, renderDetails, contextBody, taxAreasBody, programsBody, planLine, countyOf, pairTable, reportUrl, takeQuestion, likelyEligibleBody, likelyEligiblePair, factKey, cardStyleSwitch } from "/js/render.js";
import { fmtCount, fmtMoe, fmtToday } from "/js/format.js";
import { PRESETS, presetById } from "/js/presets.js";

const params = new URL(location.href).searchParams;
const state = {
  id: (params.get("d") || "").toUpperCase(), vs: (params.get("vs") || "").toUpperCase(),
  view: presetById(params.get("view")).id, data: null, dataVs: null, list: [],
};
const comparing = () => !!(state.data && state.dataVs);

// The question (if any) comes from browser storage by a one-time id; it is never in the link.
const question = takeQuestion(params.get("qid")).trim();
if (question) { $("from-q").hidden = false; $("from-q").textContent = `From your question: “${question}”`; }

function syncUrl() {
  const u = new URL(location.href);
  state.id ? u.searchParams.set("d", state.id) : u.searchParams.delete("d");
  state.id && state.vs ? u.searchParams.set("vs", state.vs) : u.searchParams.delete("vs");
  state.view !== "overview" ? u.searchParams.set("view", state.view) : u.searchParams.delete("view");
  u.searchParams.delete("qid"); // used once on load; never kept in the address bar or history
  u.searchParams.delete("q");   // older links that carried the question itself
  history.replaceState(null, "", u);
  $("back").href = state.id ? "/?d=" + encodeURIComponent(state.id) : "/";
}

// ---------- tabs (WAI-ARIA tabs pattern, automatic activation) ----------
function buildTabs() {
  $("tabs").replaceChildren(...PRESETS.map(p => el("button", {
    type: "button", role: "tab", id: "tab-" + p.id, textContent: p.label,
    onclick: () => selectView(p.id, false),
  })));
  $("panel").setAttribute("aria-labelledby", "tab-" + state.view);
  markTabs();
}
function markTabs() {
  PRESETS.forEach(p => {
    const t = $("tab-" + p.id);
    const on = p.id === state.view;
    t.setAttribute("aria-selected", on);
    t.setAttribute("aria-controls", "panel");
    t.tabIndex = on ? 0 : -1;
  });
}
$("tabs").addEventListener("keydown", e => {
  const i = PRESETS.findIndex(p => p.id === state.view);
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: PRESETS.length - 1 }[e.key];
  if (next === undefined) return;
  e.preventDefault();
  selectView(PRESETS[(next + PRESETS.length) % PRESETS.length].id, true);
});
function selectView(id, focusTab) {
  state.view = id;
  markTabs();
  $("panel").setAttribute("aria-labelledby", "tab-" + id);
  if (focusTab) $("tab-" + id).focus();
  syncUrl();
  renderPanel();
}

// ---------- panel ----------
function renderSection(s, data, county) {
  let body = null;
  if (s.type === "group") {
    // The section heading already says what the rows are, so drop the repeated label prefix.
    const comps = data.comparisons.filter(c => c.group === s.group)
      .map(c => ({ ...c, label: c.label.replace(/^Employed residents working in:\s*/, "") }));
    if (comps.length) body = el("div", {},
      comps[0].group_note ? el("p", { className: "muted small", textContent: comps[0].group_note }) : null,
      comparisonTable(comps, county, { groupRows: false }));
  } else if (s.type === "taxAreas") body = taxAreasBody(data, county);
  else if (s.type === "context") body = contextBody(data, county, s.ids);
  else if (s.type === "programs") body = programsBody(data);
  else if (s.type === "likelyEligible") body = likelyEligibleBody(data);
  else if (s.type === "note") body = el("div", { className: "card" }, el("p", { className: "muted", style: "margin:0", textContent: s.text }));
  return el("section", { className: "block" }, el("h2", { textContent: s.title }),
    body || el("p", { className: "muted", textContent: "Not available for this district." }));
}

// A section in comparison mode. Metric groups compare side by side; tax areas, county context
// and programs describe one district or its county, so they link to each district's own report.
function renderPairSection(s, a, b) {
  let body;
  if (s.type === "group") {
    const comps = a.comparisons.filter(c => c.group === s.group);
    const strip = x => ({ ...x, comparisons: x.comparisons.map(c => ({ ...c, label: c.label.replace(/^Employed residents working in:\s*/, "") })) });
    body = comps.length ? el("div", {},
      comps[0].group_note ? el("p", { className: "muted small", textContent: comps[0].group_note }) : null,
      pairTable(comps.map(c => c.metric_id), strip(a), strip(b))) : null;
  } else if (s.type === "note") {
    body = el("div", { className: "card" }, el("p", { className: "muted", style: "margin:0", textContent: s.text }));
  } else if (s.type === "likelyEligible") {
    body = likelyEligiblePair(a, b);
  } else {
    const what = s.type === "taxAreas" ? "Tax areas overlap each district differently"
      : s.type === "programs" ? "Program details are the same for every district"
      : "These describe each district's county, not the district";
    const link = d => el("a", { href: reportUrl(d.geo_id, state.view), textContent: d.name });
    body = el("div", { className: "card" }, el("p", { className: "muted", style: "margin:0" },
      `${what}, so they aren't compared. See `, link(a), " and ", link(b), "."));
  }
  return el("section", { className: "block" }, el("h2", { textContent: s.title }),
    body || el("p", { className: "muted", textContent: "Not available for these districts." }));
}

function printLine(label) {
  const data = state.data;
  const year = data && data.comparisons[0] ? data.comparisons[0].source.year : "";
  $("print-view").textContent = [`Generated ${fmtToday()}`, year && `Data: Census ACS 5-year ${year}`, `View: ${label}`].filter(Boolean).join(" · ");
}

function renderPanel() {
  const data = state.data;
  if (!data) return;
  const p = presetById(state.view);
  const notes = el("div", { className: "notes" }, ...(p.notes || []).map(n => el("p", { className: "muted small", textContent: n })));
  printLine(p.label);
  const viewSwitch = () => cardStyleSwitch(() => {
    renderPanel();
    const b = document.querySelector('#panel .cs-switch button[aria-pressed="true"]');
    if (b) b.focus();
  });
  if (comparing()) {
    const a = { ...data, id: data.geo_id }, b = { ...state.dataVs, id: state.dataVs.geo_id };
    const byId = (d, id) => d.comparisons.find(c => c.metric_id === id);
    const facts = el("div", { className: "facts" });
    p.metrics.forEach(id => {
      const ca = byId(a, id), cb = byId(b, id);
      facts.append(ca || cb ? renderPairFact(ca, cb, { id: a.id, name: a.name }, { id: b.id, name: b.name }) : missingFact(id));
    });
    $("panel").replaceChildren(el("p", { className: "blurb", textContent: `${p.label}: both districts side by side, with the state for reference.` }), notes, viewSwitch(),
      facts, factKey(undefined, { a: a.id, b: b.id }),
 ...p.sections.map(s => renderPairSection(s, a, b)));
    document.title = `${data.geo_id} compared with ${state.dataVs.geo_id} · ${p.label} · District Insight`;
    return;
  }
  const county = countyOf(data);
  const facts = el("div", { className: "facts" });
  p.metrics.forEach(id => {
    const c = data.comparisons.find(x => x.metric_id === id);
    facts.append(c ? renderKeyFact(c, { place: data.name }) : missingFact(id));
  });
  $("panel").replaceChildren(el("p", { className: "blurb", textContent: p.blurb }), notes, viewSwitch(),
    facts, factKey(), ...p.sections.map(s => renderSection(s, data, county)));
  document.title = `${data.name} · ${p.label} · District Insight`;
}

// ---------- data ----------
const popLine = data => {
  const pop = data.facts.find(f => f.indicator_id === "pop_total");
  return pop && pop.value_status === "ok"
    ? `About ${fmtCount(pop.value)} residents (${fmtMoe(pop.moe, "count")})` : "Population not available";
};

async function fetchDistrict(id) {
  const res = await fetch("/api/districts/" + encodeURIComponent(id));
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function pairCard(data, cls) {
  const card = el("article", { className: "pcard " + cls }, el("h2", { textContent: data.name }),
    el("p", { textContent: countyOf(data) || "County not known" }), el("p", { textContent: popLine(data) }));
  if (data.plan) card.append(el("p", { className: "muted", textContent:
    `Redistricting population (2021 plan): ${data.plan.permanent_residents.toLocaleString("en-US")}` }));
  card.append(el("a", { href: reportUrl(data.geo_id, state.view), textContent: "Full report" }));
  return card;
}

// Fill the "Compare with" list: every district except the one chosen.
function fillVsOptions() {
  const sel = $("vs");
  sel.replaceChildren(new Option("None", ""));
  [["house", "House"], ["senate", "Senate"]].forEach(([type, label]) => {
    const g = el("optgroup", { label });
    state.list.filter(d => d.geo_type === type && d.geo_id !== state.id).forEach(d => g.append(new Option(d.name, d.geo_id)));
    sel.append(g);
  });
  sel.disabled = !state.id;
  sel.value = state.vs || "";
}

async function load() {
  const { id, vs } = state;
  state.data = null; state.dataVs = null;
  $("district").value = id || "";
  fillVsOptions();
  syncUrl();
  $("pair").hidden = true; $("pair-note").hidden = true;
  if (!id) {
    $("title").textContent = "Choose a district";
    $("sub").textContent = "Pick a district above.";
    $("plan").replaceChildren(); $("panel").replaceChildren(); $("all-inner").replaceChildren();
    return;
  }
  $("panel").replaceChildren(el("p", { className: "muted", textContent: "Loading…" }));
  try {
    const [data, dataVs] = await Promise.all([fetchDistrict(id), vs ? fetchDistrict(vs) : null]);
    if (state.id !== id || state.vs !== vs) return; // user already moved on
    state.data = data; state.dataVs = dataVs;
    const year = data.comparisons[0] ? data.comparisons[0].source.year : "";
    if (dataVs) {
      $("title").textContent = `${data.name} compared with ${dataVs.name}`;
      $("sub").textContent = [year && `Census ACS 5-year ${year}`, "Differences tested against both margins of error"].filter(Boolean).join(" · ");
      $("plan").replaceChildren();
      $("pair").replaceChildren(pairCard(data, "a"), pairCard(dataVs, "b"));
      $("pair").hidden = false;
      if (data.geo_type !== dataVs.geo_type) {
        $("pair-note").textContent = "House and Senate districts overlap. Rates and medians compare, but some residents are in both, so the margin-of-error test is approximate.";

        $("pair-note").hidden = false;
      }
      $("all").hidden = true;
    } else {
      $("title").textContent = data.name;
      $("sub").textContent = [countyOf(data), popLine(data), year && `Census ACS 5-year ${year}`].filter(Boolean).join(" · ");
      $("plan").replaceChildren(...[planLine(data)].filter(Boolean));
      $("all-inner").replaceChildren(renderDetails(data));
      $("all").hidden = false;
    }
    renderPanel();
  } catch (err) {
    $("title").textContent = "District report";
    $("panel").replaceChildren(el("p", { className: "error", textContent: "Could not load this district. " + err.message }));
  }
}

async function init() {
  buildTabs();
  try {
    const res = await fetch("/api/districts");
    if (!res.ok) throw new Error("Data service unavailable");
    state.list = await res.json();
    const sel = $("district");
    sel.replaceChildren(new Option("Choose…", ""));
    [["house", "House"], ["senate", "Senate"]].forEach(([type, label]) => {
      const g = el("optgroup", { label });
      state.list.filter(d => d.geo_type === type).forEach(d => g.append(new Option(d.name, d.geo_id)));
      sel.append(g);
    });
    const known = id => state.list.some(d => d.geo_id === id);
    if (state.id && !known(state.id)) state.id = "";
    if (!state.id || !known(state.vs) || state.vs === state.id) state.vs = "";
  } catch (err) {
    $("panel").replaceChildren(el("p", { className: "error", textContent: "Could not load. " + err.message }));
    return;
  }
  load();
}

$("district").addEventListener("change", e => {
  state.id = e.target.value;
  if (!state.id || state.vs === state.id) state.vs = "";
  load();
});
$("vs").addEventListener("change", e => { state.vs = e.target.value; load(); });
$("print").addEventListener("click", () => window.print());
$("copy").addEventListener("click", e => {
  const u = new URL(location.href);
  u.searchParams.delete("qid"); // the question was the sender's; the report stands alone
  u.searchParams.delete("q");
  if (navigator.clipboard) navigator.clipboard.writeText(u.href).then(() => { e.target.textContent = "Link copied"; });
});
window.addEventListener("beforeprint", () => document.querySelectorAll("details").forEach(d => d.open = true));
init();
