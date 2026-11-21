// Number and text formatting shared by every page. Pure functions: no DOM access.

export const fmtMetric = (v, f) => v == null ? "Not available"
  : f === "dollars" ? "$" + Math.round(v).toLocaleString("en-US") : (v * 100).toFixed(1) + "%";

export const fmtCount = v => v == null ? "Not available" : Math.round(v).toLocaleString("en-US");

// "±" is read aloud as "plus or minus"; "pts" are percentage points.
export const fmtMoe = (m, f) => m == null ? "margin of error not available"
  : f === "dollars" ? "±$" + Math.round(m).toLocaleString("en-US")
  : f === "count" ? "±" + Math.round(m).toLocaleString("en-US")
  : "±" + (m * 100).toFixed(1) + " pts";

// Census county names lack the ʻokina ("Kauai County, Hawaii"); show the Hawaiian spelling.
export const shortCounty = n => n
  ? n.replace(/, Hawaii$/, "").replace(/^Hawaii County/, "Hawaiʻi County").replace(/^Kauai County/, "Kauaʻi County")
  : "its county";
export const shortGeo = g => g.split(" (")[0];

export const districtLabel = id => id
  ? `${id.startsWith("HD") ? "House" : "Senate"} District ${id.split("-")[1]}` : "";

// Difference between two estimates, in the same shape as the API's `difference` object
// (api/main.py compare()): within the margin of error when |A - B| <= sqrt(MOE_A^2 + MOE_B^2).
export function compareEstimates(a, b) {
  if (!a || !b || a.value == null || b.value == null) return null;
  const diff = a.value - b.value;
  const moe = a.moe != null && b.moe != null ? Math.sqrt(a.moe ** 2 + b.moe ** 2) : null;
  return {
    absolute: diff,
    relative: b.value ? diff / b.value : null,
    moe,
    within_margin_of_error: moe == null ? null : Math.abs(diff) <= moe,
  };
}

// "16 November 2026": the date a printout was made.
export const fmtToday = () => new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

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
  const flag = diff.within_margin_of_error === true ? "Within margin of error"
    : diff.within_margin_of_error === null ? "No margin of error published" : "";
  // Compact form for the headline cards: size only ("14%" or "2.1 pts"), direction in `dir`.
  const size = f === "dollars" ? `${Math.abs((diff.relative || 0) * 100).toFixed(0)}%` : `${Math.abs(diff.absolute * 100).toFixed(1)} pts`;
  const dir = text === "about the same" ? 0 : diff.absolute > 0 ? 1 : -1;
  const sure = diff.within_margin_of_error === false ? "real" : diff.within_margin_of_error === true ? "within" : "unknown";
  return { text, flag, size, dir, sure };
}
