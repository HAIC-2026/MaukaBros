// Print builder (report page): choose what goes on paper, then print a document built for it.
// Three kinds of printout share one masthead (district, who it is for, date, live link) and one
// colophon (sources). The document is built only for printing and removed afterwards, so the
// screen never changes. Every figure keeps its margin of error and source line on paper.
import { el, renderKeyFact, renderPairFact, missingFact, factKey, renderDetails, countyOf, planLine, cardStyle, CARD_STYLES,
  renderSection, renderPairSection } from "/js/render.js";
import { fmtToday, fmtCount } from "/js/format.js";
import { presetById } from "/js/presets.js";

const FORMATS = [
  { id: "packet", label: "Briefing packet", hint: "The views you choose, with a contents page and page numbers." },
  { id: "brief", label: "One-page brief", hint: "Six headline figures and where residents can get help, on one sheet." },
  { id: "handout", label: "Resident handout", hint: "Programs, phone numbers and web addresses in plain, large type. No statistics." },
];
const OPTIONS = [
  // [key, label, helper, formats it applies to, single district only]
  ["refs", "County and state comparisons", "Off prints district figures only, each still with its margin of error.", ["packet", "brief"], true],
  ["calc", "How each figure is calculated", "The two published counts behind each percentage.", ["packet"], false],
  ["newPage", "Start each view on a new page", "", ["packet"], false],
  ["large", "Large print", "Bigger type throughout, for easier reading.", ["packet", "brief", "handout"], false],
  ["ink", "Ink saver", "No shaded panels or color fills.", ["packet", "brief", "handout"], false],
];
const DEFAULTS = { format: "packet", style: "", refs: true, calc: false, newPage: true, large: false, ink: false, by: "", for: "", note: "" };
const STORE = "di-print-options"; // this browser only: a convenience, never needed to print

const loadOpts = () => { try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE) || "{}") }; } catch { return { ...DEFAULTS }; } };
const saveOpts = o => { try { localStorage.setItem(STORE, JSON.stringify(o)); } catch { /* storage blocked */ } };

const PHONE = /(?:1-)?(?:\(\d{3}\)\s?|\d{3}-)\d{3}-\d{4}/g;
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };
const plainUrl = u => u.replace(/^https?:\/\//, "").replace(/\/$/, "");
// Set attributes el() can't (data-*, aria-*), and return the node.
const attr = (n, a) => { Object.entries(a).forEach(([k, v]) => n.setAttribute(k, v)); return n; };

/**
 * Wire the print builder to a page. `getCtx()` returns the report as it stands:
 *   { data, dataVs, view, tabs, sub, link }
 * (tabs: the report views in order; sub: the line under the title; link: the live report's address)
 * Returns { open } to show the dialog.
 */
export function initPrintBuilder(getCtx) {
  let chosen = null;      // view ids picked for the packet (kept while the page is open)
  let appendix = false;   // source data appendix
  const dlg = el("dialog", { className: "pb", id: "print-builder" });
  dlg.setAttribute("aria-labelledby", "pb-title");
  document.body.append(dlg);

  function open() {
    const ctx = getCtx();
    if (!ctx || !ctx.data) return;
    if (!chosen) chosen = new Set([ctx.view]);
    const pair = !!ctx.dataVs;
    const opts = loadOpts();
    if (!opts.style) opts.style = cardStyle();

    const form = el("form", { method: "dialog" });
    const head = el("header", { className: "pb-head" },
      el("p", { className: "pb-kicker", textContent: "Print builder" }),
      el("h2", { id: "pb-title", textContent: `Print ${pair ? `${ctx.data.geo_id} and ${ctx.dataVs.geo_id}` : ctx.data.name}` }),
      el("p", { className: "pb-lead", textContent: "Build a printout for a briefing, a hearing or a resident. Every figure prints with its margin of error and source." }),
      attr(el("button", { className: "pb-x", type: "button", onclick: () => dlg.close() }), { "aria-label": "Close" }));

    // --- kind of printout: selectable tiles with a small drawing of the page
    const formats = el("fieldset", { className: "pb-formats" }, el("legend", { textContent: "Kind of printout" }),
      el("div", { className: "pb-tiles" }, ...FORMATS.map(f => {
        const input = el("input", { type: "radio", name: "pb-format", value: f.id, checked: opts.format === f.id,
          onchange: () => { opts.format = f.id; sync(); } });
        return el("label", { className: "pb-tile" }, input, thumb(f.id),
          el("span", { className: "pb-tile-text" }, el("strong", { textContent: f.label }), el("span", { textContent: f.hint })));
      })));

    // --- views for the packet
    const boxes = new Map();
    const viewList = el("div", { className: "pb-views" }, ...ctx.tabs.map(p => {
      const box = el("input", { type: "checkbox", value: p.id, checked: chosen.has(p.id),
        onchange: e => { e.target.checked ? chosen.add(p.id) : chosen.delete(p.id); sync(); } });
      boxes.set(p.id, box);
      const extra = p.sections.length ? ` · ${p.sections.length} ${p.sections.length === 1 ? "table" : "tables"}` : "";
      return el("label", { className: "pb-check" }, box, el("span", {},
        el("strong", { textContent: p.label }), p.id === ctx.view ? el("span", { className: "pb-here", textContent: "On screen" }) : null,
        el("span", { className: "pb-help", textContent: `${p.metrics.length} figures${extra}` })));
    }));
    const appendixBox = el("input", { type: "checkbox", checked: appendix, onchange: e => { appendix = e.target.checked; sync(); } });
    if (!pair) viewList.append(el("label", { className: "pb-check pb-appendix" }, appendixBox, el("span", {},
      el("strong", { textContent: "Source data appendix" }), el("span", { className: "pb-help", textContent: "Every measure and the published counts behind it" }))));
    const setAll = on => { ctx.tabs.forEach(p => { boxes.get(p.id).checked = on; on ? chosen.add(p.id) : chosen.delete(p.id); }); sync(); };
    const views = attr(el("fieldset", { className: "pb-group" },
      el("legend", { textContent: "Views to include" }),
      el("div", { className: "pb-quick" },
        el("button", { type: "button", className: "pb-link", textContent: "All views", onclick: () => setAll(true) }),
        el("button", { type: "button", className: "pb-link", textContent: "Only the view on screen", onclick: () => { setAll(false); boxes.get(ctx.view).checked = true; chosen.add(ctx.view); sync(); } }),
        el("button", { type: "button", className: "pb-link", textContent: "Clear", onclick: () => setAll(false) })),
      viewList), { "data-for": "packet" });

    // --- how the headline figures are drawn
    const style = attr(el("fieldset", { className: "pb-group" },
      el("legend", { textContent: "Draw headline figures as" }),
      el("div", { className: "pb-seg" }, ...CARD_STYLES.map(([k, label, hint]) => el("label", { title: hint },
        el("input", { type: "radio", name: "pb-style", value: k, checked: opts.style === k, onchange: () => { opts.style = k; sync(); } }),
        el("span", { textContent: label })))),
      el("p", { className: "pb-help", id: "pb-style-hint" })), { "data-for": "packet brief" });

    // --- options
    const optRows = OPTIONS.filter(([, , , , single]) => !(single && pair)).map(([key, label, help, fmts]) =>
      attr(el("label", { className: "pb-check" },
        el("input", { type: "checkbox", checked: !!opts[key], onchange: e => { opts[key] = e.target.checked; sync(); } }),
        el("span", {}, el("strong", { textContent: label }), help ? el("span", { className: "pb-help", textContent: help }) : null)), { "data-for": fmts.join(" ") }));
    const options = el("fieldset", { className: "pb-group" }, el("legend", { textContent: "Options" }), el("div", { className: "pb-opts" }, ...optRows));

    // --- personal touches on the masthead
    const field = (key, label, ph, max, area) => {
      const input = el(area ? "textarea" : "input", { id: "pb-" + key, maxLength: max, placeholder: ph, value: opts[key] || "",
        oninput: e => { opts[key] = e.target.value; saveOpts(opts); } });
      if (!area) input.type = "text"; else input.rows = 2;
      return el("div", { className: "field" }, el("label", { htmlFor: "pb-" + key, textContent: label }), input);
    };
    const personal = el("fieldset", { className: "pb-group" }, el("legend", { textContent: "Personalize the first page" }),
      el("div", { className: "pb-fields" },
        field("for", "Prepared for", "e.g. Mānoa neighborhood board, 3 December", 80),
        field("by", "Prepared by", "e.g. Office of Representative …, phone", 80)),
      field("note", "Note at the top (optional)", "A sentence or two for the reader", 280, true),
      el("p", { className: "pb-help", textContent: "Remembered in this browser only. Never sent anywhere." }));

    const summary = attr(el("p", { className: "pb-summary" }), { "aria-live": "polite" });
    const printBtn = el("button", { className: "btn", type: "submit", textContent: "Print" });
    const foot = el("footer", { className: "pb-foot" },
      el("div", { className: "pb-foot-text" }, summary,
        el("button", { type: "button", className: "pb-link", textContent: "Print the screen as is instead",
          onclick: () => { dlg.close(); window.print(); } })),
      el("div", { className: "pb-buttons" },
        el("button", { className: "btn pb-cancel", type: "button", textContent: "Cancel", onclick: () => dlg.close() }), printBtn));

    form.append(head, el("div", { className: "pb-body" }, formats, views, style, options, personal), foot);
    form.addEventListener("submit", e => {
      e.preventDefault();
      if (printBtn.disabled) return;
      saveOpts(opts);
      dlg.close();
      printDoc(ctx, opts, ctx.tabs.filter(p => chosen.has(p.id)), appendix && !pair);
    });
    dlg.replaceChildren(form);

    function sync() {
      dlg.querySelectorAll("[data-for]").forEach(n => { n.hidden = !n.dataset.for.split(" ").includes(opts.format); });
      const hint = CARD_STYLES.find(([k]) => k === opts.style);
      $q("#pb-style-hint").textContent = hint ? hint[2] : "";
      const n = ctx.tabs.filter(p => chosen.has(p.id)).length;
      const parts = [FORMATS.find(f => f.id === opts.format).label];
      if (opts.format === "packet") parts.push(n ? `${n} ${n === 1 ? "view" : "views"}${appendix && !pair ? " + source data" : ""}` : "no views chosen");
      if (opts.format !== "handout") parts.push(`${CARD_STYLES.find(([k]) => k === opts.style)[1]} figures`);
      if (opts.large) parts.push("large print");
      if (opts.ink) parts.push("ink saver");
      summary.textContent = parts.join(" · ");
      printBtn.disabled = opts.format === "packet" && !n && !(appendix && !pair);
      saveOpts(opts);
    }
    const $q = s => dlg.querySelector(s);
    sync();
    dlg.showModal();
    const first = $q('input[name="pb-format"]:checked');
    if (first) first.focus();
  }

  return { open };
}

// A tiny drawing of each kind of page, for the format tiles. Decorative.
function thumb(kind) {
  const s = cls => el("span", { className: cls });
  const t = el("span", { className: `pb-thumb t-${kind}` });
  t.setAttribute("aria-hidden", "true");
  if (kind === "packet") t.append(s("bar"), s("line w70"), s("grid2"), s("line"), s("line w60"));
  else if (kind === "brief") t.append(s("bar"), s("grid3"), s("line"), s("line w80"), s("line w60"));
  else t.append(s("big"), s("line thick"), s("line thick w70"), s("big"), s("line thick w80"));
  return t;
}

// ---------- the printed document ----------
function printDoc(ctx, o, views, appendix) {
  const doc = buildDoc(ctx, o, views, appendix);
  const root = document.documentElement;
  const page = el("style", { id: "pd-page", textContent: pageRule(ctx, o) });
  document.head.append(page);
  document.body.append(doc);
  const marks = ["pd-on", `pd-f-${o.format}`, o.large && "pd-large"].filter(Boolean);
  root.classList.add(...marks);
  if (o.format === "brief") fitOnePage(doc);
  const done = () => {
    root.classList.remove(...marks);
    doc.remove(); page.remove();
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  // Let the browser lay the document out before the print preview takes its snapshot.
  requestAnimationFrame(() => setTimeout(() => window.print(), 0));
}

// The one-page brief must stay on one sheet whatever the district, paper or type size: measure it at
// the printable size of the smaller page (A4 width, Letter height, inside the margins below) and,
// if it is taller, scale it down. `zoom` reflows the text wider as it shrinks, so the fit holds.
// Letter inside our margins is 940px tall; budget 900px (about 9.4in) so a browser that uses its own,
// larger margins or adds its header and footer still keeps the brief on one sheet.
const PAGE_H = 900;
function fitOnePage(doc) {
  const root = document.documentElement;
  doc.style.zoom = "";
  root.classList.add("pd-measure");
  doc.classList.add("pd-measuring");
  const h = doc.getBoundingClientRect().height;
  doc.classList.remove("pd-measuring");
  root.classList.remove("pd-measure");
  if (h > PAGE_H) doc.style.zoom = (Math.floor(PAGE_H / h * 0.98 * 1000) / 1000).toString(); // 2% spare for rounding
  return h;
}

// Page margins, and for the packet a running footer with page numbers (browsers without @page
// margin boxes simply leave them out).
function pageRule(ctx, o) {
  const q = s => '"' + s.replace(/["\\]/g, "\\$&") + '"';
  const who = ctx.dataVs ? `${ctx.data.geo_id} and ${ctx.dataVs.geo_id}` : ctx.data.name;
  const foot = o.format === "packet"
    ? `@bottom-left { content: ${q(`District Insight · ${who}`)}; font: 8pt "IBM Plex Sans", sans-serif; color: #525252; }
       @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt "IBM Plex Sans", sans-serif; color: #525252; }`
    : "";
  return `@media print { @page { margin: 0.55in 0.6in 0.65in; ${foot} } }`;
}

function buildDoc(ctx, o, views, appendix) {
  const pair = !!ctx.dataVs;
  const cls = ["pd", `pd-${o.format}`, o.ink && "pd-ink", !o.refs && !pair && "pd-norefs", !o.calc && "pd-nocalc"];
  const doc = el("article", { id: "print-doc", className: cls.filter(Boolean).join(" ") });
  doc.append(masthead(ctx, o));
  if (o.format === "packet") {
    const parts = views.map(p => ({ title: p.label, blurb: pair ? "Both districts side by side, with the state for reference." : p.blurb, body: () => viewBody(ctx, p, o) }));
    if (appendix) parts.push({ title: "Source data", blurb: "Every measure, and the published Census counts behind each percentage, for checking.", body: () => [renderDetails(ctx.data)] });
    if (!pair && ctx.data.plan) doc.append(el("div", { className: "pd-plan" }, planLine(ctx.data)));
    if (parts.length > 1) doc.append(el("nav", { className: "pd-toc" }, el("h2", { textContent: "In this packet" }),
      el("ol", {}, ...parts.map(x => el("li", {}, el("strong", { textContent: x.title }), el("span", { textContent: x.blurb }))))));
    parts.forEach((x, i) => {
      const sec = el("section", { className: "pd-view" + (o.newPage && (i > 0 || parts.length > 1) ? " pd-break" : "") },
        el("header", { className: "pd-view-head" }, el("span", { className: "pd-num", textContent: String(i + 1) }),
          el("div", {}, el("h2", { textContent: x.title }), el("p", { textContent: x.blurb }))));
      sec.append(...x.body().filter(Boolean));
      doc.append(sec);
    });
  } else if (o.format === "brief") {
    doc.append(...briefBody(ctx, o).filter(Boolean));
  } else {
    doc.append(...handoutBody(ctx));
  }
  doc.append(colophon(ctx, o));
  doc.querySelectorAll("details").forEach(d => { d.open = true; });
  return doc;
}

const ids = ctx => ({ a: { id: ctx.data.geo_id, name: ctx.data.name }, b: ctx.dataVs && { id: ctx.dataVs.geo_id, name: ctx.dataVs.name } });

function factsGrid(ctx, metricIds, style) {
  const grid = el("div", { className: "facts" });
  const find = (d, id) => d && d.comparisons.find(c => c.metric_id === id);
  const { a, b } = ids(ctx);
  metricIds.forEach(id => {
    if (ctx.dataVs) {
      const ca = find(ctx.data, id), cb = find(ctx.dataVs, id);
      grid.append(ca || cb ? renderPairFact(ca, cb, a, b, style) : missingFact(id));
    } else {
      const c = find(ctx.data, id);
      grid.append(c ? renderKeyFact(c, { style }) : missingFact(id));
    }
  });
  return grid;
}

function viewBody(ctx, p, o) {
  const { a, b } = ids(ctx);
  const notes = (p.notes || []).map(n => el("p", { className: "muted small", textContent: n }));
  const key = factKey(o.style, ctx.dataVs ? { a: a.id, b: b.id } : null);
  const county = countyOf(ctx.data);
  const A = { ...ctx.data, id: ctx.data.geo_id }, B = ctx.dataVs && { ...ctx.dataVs, id: ctx.dataVs.geo_id };
  const sections = p.sections.map(s => ctx.dataVs ? renderPairSection(s, A, B, ctx.view) : renderSection(s, ctx.data, county));
  return [...notes, factsGrid(ctx, p.metrics, o.style), o.refs || ctx.dataVs ? key : null, ...sections];
}

// One sheet: the six overview figures, then each program with a phone number and web address.
function briefBody(ctx, o) {
  const { a, b } = ids(ctx);
  const pair = !!ctx.dataVs;
  const out = [el("h2", { className: "pd-h", textContent: "Headline figures" }),
    factsGrid(ctx, presetById("overview").metrics, o.style)];
  if (o.refs || pair) out.push(factKey(o.style, pair ? { a: a.id, b: b.id } : null));
  const progs = ctx.data.programs || [];
  if (!progs.length) return out;
  const t = el("table", { className: "pd-progs" });
  const cols = ["Program", "Who it helps", ...(pair ? [] : ["Likely eligible"]), "How to reach them"];
  const h = t.createTHead().insertRow();
  cols.forEach(c => h.append(el("th", { scope: "col", textContent: c })));
  const body = t.createTBody();
  progs.forEach(p => {
    const tr = body.insertRow();
    tr.append(el("th", { scope: "row", textContent: p.name }), el("td", { textContent: p.serves }));
    if (!pair) {
      const le = p.likely_eligible, d = le && le.estimated && le.district;
      tr.append(el("td", {}, d && d.value != null ? `about ${fmtCount(d.value)}` : "No estimate",
        d && d.value != null && d.moe != null ? el("span", { className: "moe", textContent: `±${fmtCount(d.moe)}` }) : null));
    }
    tr.append(el("td", {}, ...contactLines(p)));
  });
  out.push(el("h2", { className: "pd-h", textContent: "Where residents can get help" }), el("div", { className: "table-wrap" }, t));
  return out;
}

// Phone numbers found in a program's apply and contact facts, then its web address.
function contactLines(p) {
  const text = (p.facts || []).filter(f => f.topic === "apply" || f.topic === "contact").map(f => f.text).join(" ");
  const phones = [...new Set(text.match(PHONE) || [])].slice(0, 1); // the first is the main line
  return [...phones.map(n => el("span", { className: "pd-phone", textContent: n })), el("span", { className: "pd-url", textContent: hostOf(p.url) })];
}

// For residents: no statistics, just who each program helps and how to reach it.
function handoutBody(ctx) {
  const progs = ctx.data.programs || [];
  const facts = (p, topics, n) => (p.facts || []).filter(f => topics.includes(f.topic)).slice(0, n).map(f => el("li", { textContent: f.text }));
  return [
    el("p", { className: "pd-lead", textContent: "Help with food, health care, taxes and living costs. Each agency decides who qualifies, " +
      "so if one of these sounds like you, call or visit the official page to ask." }),
    el("div", { className: "pd-cards" }, ...progs.map(p => {
      const who = facts(p, ["eligibility"], 3), how = facts(p, ["apply", "contact"], 3);
      return el("article", { className: "pd-card" },
        el("h2", { textContent: p.name }),
        el("p", { className: "pd-serves", textContent: p.serves }),
        el("div", { className: "pd-card-cols" },
          who.length ? el("div", {}, el("h3", { textContent: "Who may qualify" }), el("ul", {}, ...who)) : null,
          how.length ? el("div", {}, el("h3", { textContent: "How to apply" }), el("ul", {}, ...how)) : null),
        el("p", { className: "pd-web" }, el("span", { textContent: "Online: " }), el("strong", { textContent: plainUrl(p.url) }),
          el("span", { className: "pd-agency", textContent: ` · ${p.agency}. Checked ${p.checked_on}.` })));
    })),
  ];
}

function masthead(ctx, o) {
  const pair = !!ctx.dataVs;
  const title = o.format === "handout"
    ? `Help for residents of ${pair ? `${ctx.data.name} and ${ctx.dataVs.name}` : ctx.data.name}`
    : pair ? `${ctx.data.name} compared with ${ctx.dataVs.name}` : ctx.data.name;
  const kicker = { packet: "District briefing packet", brief: "District brief", handout: "Programs and help" }[o.format];
  const meta = [["Prepared for", o.for], ["Prepared by", o.by], ["Printed", fmtToday()],
    o.format !== "handout" && ["Live version", plainUrl(ctx.link)]].filter(m => m && m[1] && m[1].trim());
  const head = el("header", { className: "pd-mast" },
    el("p", { className: "pd-kicker" }, el("span", { textContent: "District Insight" }), ` · ${kicker}`),
    el("h1", { textContent: title }),
    o.format !== "handout" && ctx.sub ? el("p", { className: "pd-sub", textContent: ctx.sub }) : null,
    meta.length ? el("dl", { className: "pd-meta" }, ...meta.map(([k, v]) => el("div", {}, el("dt", { textContent: k }), el("dd", { textContent: v.trim() })))) : null);
  const frag = [head];
  if (o.note && o.note.trim()) frag.push(el("aside", { className: "pd-note" },
    el("p", { className: "pd-note-label", textContent: o.by && o.by.trim() ? `A note from ${o.by.trim()}` : "Note" }),
    el("p", { textContent: o.note.trim() })));
  return el("div", { className: "pd-top" }, ...frag);
}

function colophon(ctx, o) {
  const c = ctx.data.comparisons[0];
  const year = c ? c.source.year : "";
  const checked = [...new Set((ctx.data.programs || []).map(p => p.checked_on).filter(Boolean))].sort();
  const lines = o.format === "brief"
    ? [`District figures: U.S. Census Bureau, ACS 5-year${year ? ` ${year}` : ""}, table under each figure; ± is the 90% margin of error. ` +
       (ctx.dataVs ? "" : "Likely eligible: residents under the program's income limit, from the same survey; an estimate, not an eligibility count. ") +
       "Program details quoted from each agency's official pages. Informational only: each agency decides who qualifies."]
    : o.format === "handout"
    ? ["Program details are quoted from each agency's official pages" + (checked.length ? `, checked ${checked[0]}${checked.length > 1 ? ` to ${checked[checked.length - 1]}` : ""}` : "") +
        ". Rules and limits change, so confirm with the agency before you apply.",
       "Informational only, not eligibility advice."]
    : [`District figures: U.S. Census Bureau, American Community Survey 5-year estimates${year ? ` (${year})` : ""}, with the Census table named under each figure.`,
       "± is the 90% margin of error. \u201cWithin margin of error\u201d means a difference may not be real; \u201cClear difference\u201d means it lies beyond both margins.",
       "Program details are quoted from each agency's official pages. Informational only, not eligibility advice."];
  return el("footer", { className: "pd-colophon" }, ...lines.map(t => el("p", { textContent: t })),
    el("p", { className: "pd-made", textContent: `Made with District Insight${o.format === "handout" ? "" : ` · ${plainUrl(ctx.link)}`}` }));
}

