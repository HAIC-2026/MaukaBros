// Minimal, safe Markdown for assistant answers: paragraphs, lists, pipe tables, **bold**, and
// [S#] citations as links to the answer's source list. Builds DOM nodes; never inserts HTML.
import { el } from "./render.js";

function inline(text, answerId) {
  const out = [];
  text.split(/(\*\*[^*]+\*\*|\[[^\]]*\bS\d+\b[^\]]*\])/g).forEach(part => {
    if (!part) return;
    if (part.startsWith("**") && part.endsWith("**")) out.push(el("strong", { textContent: part.slice(2, -2) }));
    else if (/^\[[^\]]*\bS\d+\b[^\]]*\]$/.test(part)) {
      const sup = el("sup");
      (part.match(/S\d+/g) || []).forEach((sid, i) => {
        if (i) sup.append(",");
        sup.append(el("a", { href: `#src-${answerId}-${sid}`, textContent: sid.slice(1), title: "Source " + sid.slice(1) }));
      });
      out.push(sup);
    } else out.push(document.createTextNode(part));
  });
  return out;
}

export function renderMarkdown(md, answerId) {
  const frag = document.createDocumentFragment();
  const lines = md.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^\s*\|/.test(line)) {                       // pipe table
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const t = el("table"); const body = el("tbody");
      rows.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r)).forEach((r, k) => {
        const tr = document.createElement("tr");
        cells(r).forEach(c => tr.append(el(k === 0 ? "th" : "td", {}, ...inline(c, answerId))));
        (k === 0 ? t.createTHead() : body).append(tr);
      });
      t.append(body); frag.append(el("div", { className: "table-wrap" }, t)); continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {          // list
      const ordered = /^\s*\d+\./.test(line);
      const list = el(ordered ? "ol" : "ul");
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i]))
        list.append(el("li", {}, ...inline(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""), answerId)));
      frag.append(list); continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^\s*(\||[-*]\s|\d+\.\s)/.test(lines[i]))
      para.push(lines[i++].replace(/^#+\s*/, ""));
    const p = el("p", {}, ...inline(para.join(" "), answerId));
    if (/^#+\s/.test(line)) p.style.fontWeight = "600";
    frag.append(p);
  }
  return frag;
}
