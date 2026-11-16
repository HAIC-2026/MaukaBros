// Number and text formatting shared by every page. Pure functions: no DOM access.

export const fmtMetric = (v, f) => v == null ? "Not available"
  : f === "dollars" ? "$" + Math.round(v).toLocaleString("en-US") : (v * 100).toFixed(1) + "%";

export const fmtCount = v => v == null ? "Not available" : Math.round(v).toLocaleString("en-US");

export const fmtMoe = (m, f) => m == null ? "margin of error not available"
  : f === "dollars" ? "plus or minus $" + Math.round(m).toLocaleString("en-US")
  : f === "count" ? "plus or minus " + Math.round(m).toLocaleString("en-US")
  : "plus or minus " + (m * 100).toFixed(1) + " points";

export const shortCounty = n => n ? n.replace(/, Hawaii$/, "") : "its county";
export const shortGeo = g => g.split(" (")[0];

export const districtLabel = id => id
  ? `${id.startsWith("HD") ? "House" : "Senate"} District ${id.split("-")[1]}` : "";

// Plain-language difference between a district and a reference area, with a margin-of-error flag.
export function diffText(diff, f) {
  if (!diff) return { text: "not available", flag: "", short: "" };
  let text;
  if (f === "dollars") {
    const r = (diff.relative || 0) * 100;
    text = Math.abs(r) < 0.5 ? "about the same" : `${Math.abs(r).toFixed(0)}% ${r > 0 ? "higher" : "lower"}`;
  } else {
    const p = diff.absolute * 100;
    text = Math.abs(p) < 0.05 ? "about the same" : `${Math.abs(p).toFixed(1)} points ${p > 0 ? "higher" : "lower"}`;
  }
  const flag = diff.within_margin_of_error === true ? "Within the margin of error: may not be a real difference"
    : diff.within_margin_of_error === null ? "Margin of error not available: treat as uncertain" : "";
  const short = diff.within_margin_of_error === true ? "within margin of error"
    : diff.within_margin_of_error === null ? "margin not available" : "";
  return { text, flag, short };
}
