"""The District Insight research assistant: Claude answering questions with tools that read
only our validated fact store (data/kyd.duckdb), never the web or the model's memory.

Every figure a tool returns carries a source id such as "S3". The model must cite figures with
those ids, and the API returns the matching source list (publisher, dataset, period, geography,
table links) with each answer, so a reader can check every number.

Configuration (.env): ANTHROPIC_API_KEY (required), KYD_MODEL (default claude-opus-5-5),
KYD_EFFORT (default medium).
"""

import json
import os
import re
import unicodedata

import anthropic
from dotenv import load_dotenv

from api import answer_check
from api import main as kyd

load_dotenv()
MODEL = os.getenv("KYD_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("KYD_EFFORT", "medium")
MAX_TOOL_ROUNDS = 10

SYSTEM_PROMPT = """You are the research assistant in District Insight, a tool for Hawaiʻi state \
legislators and their staff. You describe the people who live in a House or Senate district, \
compare the district with its county and the state, and point out where outreach could help \
residents use programs that already exist.

Rules for figures:
- Every number in your answer must come from a tool result in this conversation turn. Never use \
figures from memory or from earlier answers; call the tools again instead.
- Cite each figure with the source id the tool gave it, in square brackets, e.g. [S2]. Say the \
period (e.g. 2020-2024) and the geography when it is not obvious.
- If the tools do not have something, say plainly that it is not available in this tool's data, \
and say what related figures are available. Do not guess, estimate from general knowledge, or \
fill gaps with typical values.
- Give comparisons, not bare numbers: compare the district with its county and the state. When a \
tool marks a difference as within the margin of error, say it may not be a real difference.
- Census survey figures have margins of error: give the margin with each district survey figure \
you state, e.g. "15.0% (±2.3 points)". Tax and program-record figures have none.
- Cite only source ids a tool returned, and never name the tools in your answer. find_district \
returns no source id: when you use its shares, say in words that they are shares of 2020 Census \
residents.
- Tax-area figures describe the whole DOTAX tax area, not the district. County context figures \
describe the county, not the district. Say so when you use them.
- Program-need figures (income below the poverty line, households without SNAP, low-income \
uninsured) are not eligibility counts: each program has its own rules and the administering \
agency decides eligibility. Survey answers under-count program use (the survey finds about 68% \
of the SNAP households and Med-QUEST members in DHS records), so survey shares receiving SNAP or \
Medicaid are likely understated and the share of households not receiving SNAP is likely \
overstated; say so when you use them. County Med-QUEST and SNAP figures from get_local_context \
are program records.
- For programs, use get_programs: it returns each program's eligibility rules, income limits, how \
to apply, documents to bring and official link, all from saved official documents. Cite them, give \
the official link, and always say that final eligibility is decided by the agency. Never say a \
person or group "is eligible"; say they "may qualify". Do not state rules, limits or programs that \
get_programs does not return; if asked about another program, say it is not in this tool yet and \
suggest the agency's official site. To turn "% of poverty" into dollars, use the HHS Hawaiʻi \
poverty guidelines that get_programs returns.

Other rules:
- Describe groups of residents, never individuals. Do not infer anything about a specific person.
- Stay nonpartisan: present data without political commentary, opinions on policy, or advice on \
how to vote or campaign.
- Write in plain language for a busy legislator. Lead with the answer and keep it short: at most \
about four sentences, or up to five short bullet points. Give the two or three figures that \
answer the question, not every related figure. Do not use tables unless the user asks for one. \
The page shows a link under your answer to a full district report with every figure, comparison \
and source, so you can end with "The full report has more detail." instead of listing more. \
Spell Hawaiian place names with the ʻokina and kahakō.
- If the question does not name a district, use the district selected on the page if one is \
given; otherwise use find_district or ask which district they mean."""


# --- Source registry ------------------------------------------------------------------------

class Sources:
    """Numbers each distinct source as S1, S2, ... for one answer."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self._keys: dict[str, str] = {}

    def cite(self, publisher: str, dataset: str, period: str, geography: str,
             tables: list[dict] | None = None, note: str | None = None) -> str:
        tables = tables or []
        key = json.dumps([publisher, dataset, period, geography,
                          sorted(t["table_id"] for t in tables), note], ensure_ascii=False)
        if key not in self._keys:
            sid = f"S{len(self.items) + 1}"
            self._keys[key] = sid
            self.items.append({"id": sid, "publisher": publisher, "dataset": dataset,
                               "period": period, "geography": geography, "tables": tables,
                               "note": note})
        return self._keys[key]


# --- Formatting helpers (so the model copies numbers instead of doing arithmetic) -------------

def fmt_value(v: float | None, kind: str) -> str:
    if v is None:
        return "not available"
    if kind == "percent":
        return f"{100 * v:.1f}%"
    if kind == "dollars":
        return f"${v:,.0f}"
    return f"{v:,.0f}"


def fmt_moe(m: float | None, kind: str) -> str | None:
    if m is None:
        return None
    return f"±{100 * m:.1f} percentage points" if kind == "percent" else (
        f"±${m:,.0f}" if kind == "dollars" else f"±{m:,.0f}")


def fmt_diff(ref: dict | None, kind: str) -> str | None:
    d = ref and ref.get("difference")
    if not d:
        return None
    a = d["absolute"]
    if kind == "percent":
        size = f"{abs(100 * a):.1f} percentage points"
    elif kind == "dollars":
        size = f"${abs(a):,.0f}"
    else:
        size = f"{abs(a):,.0f}"
    word = "higher" if a > 0 else "lower" if a < 0 else "the same"
    text = f"{size} {word}" if a else "the same"
    if d.get("relative") is not None and kind == "dollars":
        text += f" ({abs(100 * d['relative']):.0f}% {word})"
    if d.get("within_margin_of_error"):
        text += "; within the margin of error, may not be a real difference"
    return text


def plain(s: str) -> str:
    """Lowercase, without ʻokina, apostrophes or kahakō, for matching place names."""
    s = unicodedata.normalize("NFD", s.lower().replace("ʻ", "").replace("'", "").replace("‘", ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def district_name(geo_id: str) -> str:
    chamber, n = geo_id.split("-")
    return f"{'House' if chamber == 'HD' else 'Senate'} District {n}"


def county_display(name: str | None) -> str | None:
    """Census county name ("Kauai County, Hawaii") in Hawaiian spelling ("Kauaʻi County")."""
    if not name:
        return name
    name = re.sub(r", Hawaii$", "", name)
    return name.replace("Hawaii County", "Hawaiʻi County").replace("Kauai County", "Kauaʻi County")


def check_district(district_id: str) -> str:
    gid = (district_id or "").strip().upper()
    if not re.fullmatch(r"(HD|SD)-\d{1,2}", gid) or not kyd.query(
            "SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
        raise ValueError(f"Unknown district id {district_id!r}. Use HD-1 to HD-51 or SD-1 to "
                         "SD-25, or call find_district.")
    return gid


# --- Tools ----------------------------------------------------------------------------------

def tool_find_district(args: dict, src: Sources) -> dict:
    q = args["query"].strip()
    p = plain(q)
    out: dict = {"query": q, "matches": []}

    m = re.search(r"\b(house|hd|representative|rep)\b\D*(\d{1,2})\b", p)
    s = re.search(r"\b(senate|sd|senator|sen)\b\D*(\d{1,2})\b", p)
    for found, prefix in ((m, "HD"), (s, "SD")):
        if found:
            gid = f"{prefix}-{int(found.group(2))}"
            if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                out["matches"].append({"district_id": gid, "name": district_name(gid),
                                       "why": "district number"})
    if not out["matches"]:
        n = re.fullmatch(r"(district\s*)?(\d{1,2})", p)
        if n:
            for prefix in ("HD", "SD"):
                gid = f"{prefix}-{int(n.group(2))}"
                if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                    out["matches"].append({"district_id": gid, "name": district_name(gid),
                                           "why": "district number (chamber not given)"})

    words = [w for w in re.findall(r"[a-z]+", p) if len(w) > 3]

    def shares(rows: list[dict], key: str) -> list[dict]:
        return [{"district_id": r["geo_id"], "name": district_name(r["geo_id"]),
                 "share_of_residents": f"{100 * r[key]:.0f}%"} for r in rows]

    # 5-digit ZIP codes (as Census ZIP code tabulation areas)
    for z in re.findall(r"\b(96\d{3})\b", q):
        rows = kyd.query("""SELECT geo_id, zcta_share FROM zcta_district WHERE zcta = ?
                            ORDER BY zcta_share DESC""", [z])
        out["matches"].append({"zip_code": z, "why": "ZIP code area; districts listed with the "
                               "share of its 2020 residents in each" if rows else
                               "ZIP code not found as a Census ZIP area (it may be a PO-box-only "
                               "ZIP with no residents)", "districts": shares(rows, "zcta_share")})

    # Census places (towns and CDPs), Census spelling without ʻokina, matched ignoring them
    places = kyd.query("SELECT place_fp, name FROM place")
    for pl in [pl for pl in places if plain(pl["name"]) in p
               or (plain(pl["name"]) in words and len(plain(pl["name"])) > 3)]:
        rows = kyd.query("""SELECT geo_id, place_share FROM place_district WHERE place_fp = ?
                            ORDER BY place_share DESC""", [pl["place_fp"]])
        out["matches"].append({"census_place": pl["name"],
                               "why": "Census place (town or CDP); districts listed with the share "
                                      "of its 2020 residents in each. The name is in Census "
                                      "spelling without ʻokina or kahakō (Pahoa for Pāhoa); write "
                                      "the Hawaiian spelling.",
                               "districts": shares(rows, "place_share")})

    # Neighborhoods and villages (USGS GNIS populated places, e.g. Kāhala, Kaimukī) that are not
    # Census places: one official reference point each, placed in the OPSD district shapes.
    # Skip a name already answered above as a Census place in the same county; Waimea on Oʻahu
    # is a GNIS village, while the Waimea Census places are on Kauaʻi and Hawaiʻi Island.
    census_names = {(plain(r["name"]), r["county"]) for r in kyd.query(
        """SELECT DISTINCT p.name, g.name AS county FROM place p JOIN block b USING (place_fp)
           JOIN geography g ON g.geo_id = b.county_geo_id""")}
    padded = f" {' '.join(re.findall(r'[a-z]+', p))} "
    named = [n for n in kyd.query("SELECT name, county, house_id, senate_id, feature_id "
                                  "FROM named_place WHERE house_id IS NOT NULL")
             if len(plain(n["name"])) > 3
             and not any(nm == plain(n["name"]) and plain(n["county"]) in plain(c)
                         for nm, c in census_names)
             and f" {' '.join(re.findall(r'[a-z]+', plain(n['name'])))} " in padded]
    if named:
        cite = src.cite("U.S. Geological Survey", "Geographic Names Information System (GNIS), "
                        "populated places", "published 2026-11-02",
                        "Official reference point of each named place, located in the State of "
                        "Hawaiʻi's 2022 district boundaries (Office of Planning and Sustainable "
                        "Development)", [],
                        "https://www.usgs.gov/tools/geographic-names-information-system-gnis")
    for n in named:
        out["matches"].append({
            "neighborhood": n["name"], "county": f"{n['county']} County",
            "why": "Neighborhood or village with no Census boundary. Its official USGS reference "
                   "point lies in the districts below. Say that this places the neighborhood's "
                   "reference point, and that parts near a district line may be in a neighboring "
                   "district. Write the name as given here (with ʻokina and kahakō).",
            "districts": [{"district_id": n["house_id"], "name": district_name(n["house_id"])},
                          {"district_id": n["senate_id"], "name": district_name(n["senate_id"])}],
            "cite": cite})

    # DOTAX tax-area names (e.g. "North Shore", "Molokai", "Waianae Coast")
    areas = kyd.query("SELECT area_id, name FROM tax_area")
    hit = [a for a in areas if plain(a["name"]) in p or any(
        w in plain(a["name"]).replace(",", " ").split() for w in words)]
    for a in hit:
        rows = kyd.query("""SELECT geo_id, area_share FROM tax_area_district
                            WHERE area_id = ? AND area_share > 0 ORDER BY area_share DESC""",
                         [a["area_id"]])
        out["matches"].append({"tax_area": a["name"],
                               "why": "DOTAX tax area; districts listed with the share of the "
                                      "area's 2020 residents in each",
                               "districts": shares(rows, "area_share")})
    if not out["matches"]:
        out["note"] = ("No match. This tool finds districts by number, ZIP code, Census place name "
                       "(towns and CDPs such as Kaneohe, Hilo, Waianae), USGS neighborhood name "
                       "(e.g. Kāhala, Kaimukī) and DOTAX tax-area name (e.g. Oʻahu North Shore, "
                       "Kona). It has no street-address lookup.")
    return out


def tool_list_measures(args: dict, src: Sources) -> dict:
    return {"measures": [{"metric_id": k, "label": m["label"],
                          "group": m.get("group", "District profile")}
                         for k, m in kyd.ordered_metrics()],
            "group_notes": {g: n for g, n in kyd.METRIC_GROUPS.items() if n}}


def tool_get_district_profile(args: dict, src: Sources) -> dict:
    gid = check_district(args["district_id"])
    geo_type = "house" if gid.startswith("HD") else "senate"
    groups = set(args.get("groups") or [])
    comps = kyd.build_comparisons(gid, geo_type)
    county_name = county_display(next((c["county"]["name"] for c in comps if c.get("county")),
                                      None))
    vals = kyd.fetch_values([gid])[gid]
    pop, pop_moe = vals.get("pop_total", (None, None))
    hh, hh_moe = vals.get("households_total", (None, None))
    acs = comps[0]["source"]
    out = {
        "district_id": gid, "name": district_name(gid), "county": county_name,
        "period": acs["year"],
        "population": {"value": fmt_value(pop, "people"), "moe": fmt_moe(pop_moe, "people"),
                       "cite": src.cite(acs["publisher"], acs["dataset"], acs["year"],
                                        f"{district_name(gid)}",
                                        kyd.table_links("B01001,B11001", acs["year"]))},
        "households": {"value": fmt_value(hh, "households"), "moe": fmt_moe(hh_moe, "households")},
        **({"official_permanent_resident_population": {
            "value": fmt_value(plan["permanent_residents"], "people"),
            "note": plan["note"],
            "cite": src.cite(plan["source"]["publisher"], plan["source"]["dataset"],
                             "2020 Census base", district_name(gid), [],
                             plan["source"]["page"])}} if (plan := kyd.district_plan(gid)) else {}),
        "measures": [],
        "group_notes": {},
    }
    for c in comps:
        if groups and c["group"] not in groups:
            continue
        kind = c["format"]
        cite = src.cite(acs["publisher"], acs["dataset"], acs["year"],
                        f"{district_name(gid)}, {county_name or 'its county'} and the State of "
                        "Hawaiʻi", c["source"]["tables"])
        out["measures"].append({
            "metric_id": c["metric_id"], "label": c["label"], "group": c["group"],
            "district": fmt_value(c["district"]["value"], kind),
            "district_moe": fmt_moe(c["district"]["moe"], kind),
            **({"reliability": "LOW RELIABILITY: the margin of error is large compared with the "
                               "estimate (coefficient of variation over 30%). Say so and treat "
                               "the figure with caution."}
               if c["district"].get("low_reliability") else {}),
            "county": fmt_value(c["county"]["value"], kind) if c.get("county") else None,
            "vs_county": fmt_diff(c.get("county"), kind),
            "state": fmt_value(c["state"]["value"], kind),
            "vs_state": fmt_diff(c.get("state"), kind),
            "cite": cite})
        if c["group_note"]:
            out["group_notes"][c["group"]] = c["group_note"]
    return out


def tool_get_local_context(args: dict, src: Sources) -> dict:
    """County/state context and the DOTAX tax areas that overlap the district."""
    gid = check_district(args["district_id"])
    county_id = kyd.district_county(gid)
    out: dict = {"district_id": gid, "name": district_name(gid)}

    def ctx_value(entry: dict | None, unit: str) -> str | None:
        # Context figures are stored as published: a BLS rate of 2.3 means 2.3%, not a fraction.
        if not entry:
            return None
        v = entry["value"]
        return "not available" if v is None else (f"{v:.1f}%" if unit == "percent"
                                                  else fmt_value(v, unit))

    ctx = kyd.build_context(county_id)
    out["county_and_state_context"] = {
        "applies_to": "The county and the state, not this district.",
        "figures": [{
            "label": c["label"], "period": c["period"],
            "county": ctx_value(c.get("county"), c["unit"]),
            "county_note": c["county"]["note"] if c.get("county") else None,
            "state": ctx_value(c.get("state"), c["unit"]),
            "state_note": c["state"]["note"] if c.get("state") else None,
            "caveat": c["caveat"],
            "cite": src.cite(c["source"]["publisher"], c["source"]["dataset"], c["period"],
                             "County and State of Hawaiʻi", c["source"]["tables"],
                             c["source"].get("original_source"))}
            for c in ctx]}

    ta = kyd.build_tax_areas(gid)
    if ta:
        cite = src.cite(ta["source"]["publisher"], ta["source"]["dataset"], ta["period"],
                        "DOTAX tax areas (whole areas), matched to districts by 2020 residents",
                        ta["source"]["tables"], ta["overlap_source"])
        cr = ta.get("credits")
        credits_cite = src.cite(cr["source"]["publisher"], cr["source"]["dataset"], cr["period"],
                                "DOTAX tax areas (whole areas) and the State of Hawaiʻi",
                                cr["source"]["tables"]) if cr else None
        out["tax_areas"] = {
            "applies_to": ta["applies_to"] + (
                " share_of_district_residents_in_area is the part of this district's residents "
                "who live in the area; share_of_area_residents_in_district is the part of the "
                "area's residents who live in this district. Do not swap them."),
            "caveat": ta["caveat"], "label": ta["label"],
            "period": ta["period"],
            "district_residents_in_no_tax_area":
                f"{100 * ta['district_residents_in_no_tax_area']:.1f}%",
            "areas": [{"tax_area": a["name"], "relation": a["relation"],
                       "median_income_on_tax_returns": fmt_value(a["median_agi"], "dollars"),
                       "resident_tax_returns": fmt_value(a["returns"], "returns"),
                       "share_of_district_residents_in_area":
                           f"{100 * a['share_of_district_residents']:.1f}%",
                       "share_of_area_residents_in_district":
                           f"{100 * (a['share_of_area_residents_in_district'] or 0):.1f}%",
                       "cite": cite,
                       **({"returns_claiming_hawaii_eitc": f"{100 * a['eitc_share']:.1f}%",
                           "returns_claiming_food_excise_credit":
                               f"{100 * a['food_excise_share']:.1f}%",
                           "credits_cite": credits_cite} if a.get("eitc_share") is not None
                          and credits_cite else {})} for a in ta["areas"]]}
        if ta.get("credits"):
            out["tax_areas"]["credit_claims_note"] = ta["credits"]["note"]
            out["tax_areas"]["state_returns_claiming_hawaii_eitc"] = (
                f"{100 * ta['credits']['state_eitc_share']:.1f}%")
            out["tax_areas"]["state_returns_claiming_food_excise_credit"] = (
                f"{100 * ta['credits']['state_food_excise_share']:.1f}%")
    return out


def tool_rank_districts(args: dict, src: Sources) -> dict:
    metric_id = args["metric_id"]
    metric = kyd.MAP_METRICS.get(metric_id)
    if metric is None:
        raise ValueError(f"Unknown metric_id {metric_id!r}. Call list_measures for valid ids.")
    chamber = args["chamber"]
    if chamber not in ("house", "senate"):
        raise ValueError("chamber must be 'house' or 'senate'")
    by = args.get("by", "share")
    if by == "count" and "numerator" not in metric:
        raise ValueError(f"{metric_id} has no count; rank by 'share' instead.")
    limit = max(1, min(int(args.get("limit", 10)), 51))
    ids = kyd.query("SELECT geo_id FROM geography WHERE geo_type = ?", [chamber])
    geo_ids = [r["geo_id"] for r in ids]
    vals = kyd.fetch_values(geo_ids + ["STATE-15"])
    kind = metric["format"]
    rows = []
    for g in geo_ids:
        if by == "count":
            v, m = vals.get(g, {}).get(metric["numerator"], (None, None))
            rows.append((g, v, m, "count"))
        else:
            v, m = kyd.metric_estimate(metric, vals.get(g, {}))
            rows.append((g, v, m, kind))
    rows = [r for r in rows if r[1] is not None]
    rows.sort(key=lambda r: r[1], reverse=args.get("highest_first", True))
    year = kyd.query("SELECT year FROM source WHERE source_id = 'acs5'")[0]["year"]
    tables_ids = ",".join(sorted({t for i in ([metric["value"]] if "value" in metric else
                                               [metric["numerator"], metric["denominator"]])
                                  for t in kyd.query("SELECT table_ids FROM indicator WHERE "
                                                     "indicator_id = ?", [i])[0]["table_ids"]
                                  .split(",")}))
    cite = src.cite("U.S. Census Bureau", "American Community Survey 5-year estimates", year,
                    f"All {chamber.title()} districts and the State of Hawaiʻi",
                    kyd.table_links(tables_ids, year))
    state_v, _ = kyd.metric_estimate(metric, vals.get("STATE-15", {}))
    num_label = (kyd.query("SELECT label FROM indicator WHERE indicator_id = ?",
                           [metric["numerator"]])[0]["label"] if by == "count" else None)
    return {
        "measure": num_label or metric["label"], "ranked_by": by, "chamber": chamber,
        "state_value": fmt_value(state_v, kind) if by == "share" else None,
        "note": "Neighboring ranks are often within each other's margins of error; treat the "
                "order as approximate.",
        "cite": cite,
        "districts": [{"rank": i + 1, "district_id": g, "name": district_name(g),
                       "value": fmt_value(v, k), "moe": fmt_moe(m, k)}
                      for i, (g, v, m, k) in enumerate(rows[:limit])]}


def tool_get_programs(args: dict, src: Sources) -> dict:
    """Programs from pipeline/programs.yaml, optionally with a district's related figures."""
    data = kyd.program_data()
    wanted = set(args.get("program_ids") or [])
    gid = args.get("district_id") or ""
    related: dict[str, list] = {}
    moes: dict[str, float | None] = {}
    if gid:
        gid = check_district(gid)
        geo_type = "house" if gid.startswith("HD") else "senate"
        comps = kyd.build_comparisons(gid, geo_type)
        moes = {c["metric_id"]: c["district"]["moe"] for c in comps}
        built = kyd.build_programs(comps, kyd.build_context(kyd.district_county(gid)), gid)
        related = {p["id"]: p for p in built}
    out = []
    for p in data["programs"]:
        if wanted and p["id"] not in wanted:
            continue
        cite = src.cite(p["agency"], f"{p['name']}: official program information",
                        f"saved {data['checked_on']}", "Program rules (statewide)",
                        [{"table_id": "official page", "url": p["url"]}])
        entry = {"program_id": p["id"], "name": p["name"], "agency": p["agency"],
                 "serves": p["serves"], "official_link": p["url"], "cite": cite,
                 "facts": [{"topic": f["topic"], "text": f["text"]} for f in p["facts"]]}
        if p.get("uptake_note"):
            entry["program_use"] = p["uptake_note"]
        lim = p.get("income_limits")
        if lim:
            key = next(k for k in lim if k.startswith("by_"))
            entry["income_limits"] = {"valid_for": lim["valid_for"], "description": lim["description"],
                                      "unit": lim["unit"], "columns": lim["columns"],
                                      key: {str(k): v for k, v in lim[key].items()}}
        if gid and p["id"] in related:
            r = related[p["id"]]
            acs = kyd.query("SELECT publisher, dataset, year FROM source WHERE source_id = 'acs5'")[0]
            mcite = src.cite(acs["publisher"], acs["dataset"], acs["year"],
                             f"{district_name(gid)} and the State of Hawaiʻi", [])
            entry["in_this_district"] = [{
                "measure": m["label"], "district": fmt_value(m["district"], m["format"]),
                "district_moe": fmt_moe(moes.get(m["metric_id"]), m["format"]) or "not available",
                "state": fmt_value(m["state"], m["format"]), "cite": mcite,
                **({"reliability": "LOW RELIABILITY"} if m["low_reliability"] else {})}
                for m in r["district_measures"]]
            entry["in_this_district_note"] = ("Our link between the program and district figures; "
                                              "not counts of eligible people. State each district "
                                              "figure with its district_moe.")
            le = r.get("likely_eligible")
            if le and le.get("estimated") and le.get("district"):
                d = le["district"]
                le_cite = src.cite(le["source"]["publisher"], le["source"]["dataset"],
                                   le["source"]["year"], f"{district_name(gid)}", [])
                entry["residents_likely_eligible"] = {
                    "district": fmt_value(d["value"], "count"),
                    "district_moe": (("about " if d["moe_status"] == "derived" else "")
                                     + (fmt_moe(d["moe"], "count") or "not available")),
                    **({"reliability": "LOW RELIABILITY"} if d.get("low_reliability") else {}),
                    "cut_used": le["acs_cut"], "likely_direction": le.get("direction_text"),
                    "caveat": le["caveat"], "final_eligibility": le["final_eligibility"],
                    "cite": le_cite}
            elif le and not le.get("estimated"):
                entry["residents_likely_eligible"] = {"not_estimated": le["reason"]}
        out.append(entry)
    pg = data["poverty_guidelines"]
    pg_cite = src.cite(pg["publisher"], pg["title"], "2026", "Hawaiʻi", [{"table_id": "PDF",
                                                                         "url": pg["url"]}])
    return {"note": data["note_on_eligibility"], "programs": out,
            "hhs_poverty_guidelines_hawaii_2026": {
                "unit": pg["unit"], "cite": pg_cite, "caution": pg["quote"],
                "by_household_size": {str(k): {f"{pct}%": v for pct, v in row.items()}
                                      for k, row in pg["by_household_size"].items()}}}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


DISTRICT_ID = {"type": "string", "description": "District id: HD-1 to HD-51 (House) or SD-1 to "
                                                "SD-25 (Senate)."}
TOOLS = [
    {"name": "find_district", "strict": True,
     "description": "Find district ids from a district number (e.g. 'House 13', 'Senate "
                    "District 7'), a ZIP code (e.g. '96744'), a town or Census place (e.g. "
                    "'Kāneʻohe', 'Hilo', 'Waiʻanae'), a neighborhood (e.g. 'Kāhala', 'Kaimukī') "
                    "or a DOTAX tax area (e.g. 'North Shore', 'Kona'). Places spanning several "
                    "districts come back with the share of their "
                    "2020 residents in each. Use this whenever the user names a place or a "
                    "district you do not have an id for.",
     "input_schema": _schema({"query": {"type": "string",
                                        "description": "The district or place as the user wrote it."}},
                             ["query"])},
    {"name": "list_measures", "strict": True,
     "description": "List every measure available for districts (id, label, group), with notes "
                    "on how each group should be read. Use it to find a metric_id for "
                    "rank_districts or to check whether a topic is covered.",
     "input_schema": _schema({}, [])},
    {"name": "get_district_profile", "strict": True,
     "description": "Census ACS 2020-2024 figures for one district, each compared with its "
                    "county and the state, with margins of error and whether each difference is "
                    "within the margin of error. Groups: 'District profile' (age, income, "
                    "poverty, housing, insurance, disability, language, families, jobs), "
                    "'Program need and uptake', 'Ethnic background', 'Jobs held by residents, by "
                    "industry'. Leave groups empty for all.",
     "input_schema": _schema({
         "district_id": DISTRICT_ID,
         "groups": {"type": "array", "items": {"type": "string", "enum": list(kyd.METRIC_GROUPS)},
                    "description": "Optional: only these groups. Empty list for all."}},
         ["district_id", "groups"])},
    {"name": "get_local_context", "strict": True,
     "description": "For one district: (1) county and state figures from other sources (DHS "
                    "SNAP program records, DOTAX median income on tax returns, BLS unemployment "
                    "rate, BEA income per person), which describe the county, not the district; "
                    "(2) the DOTAX tax areas the district's residents live in (e.g. Oʻahu North "
                    "Shore), with each whole area's median income on tax returns and the share of "
                    "its returns claiming the Hawaiʻi EITC and food/excise credit (program use), "
                    "tax year 2023, compared with the state; plus county claim counts.",
     "input_schema": _schema({"district_id": DISTRICT_ID}, ["district_id"])},
    {"name": "rank_districts", "strict": True,
     "description": "Rank all House or all Senate districts on one measure, e.g. to find where "
                    "outreach could reach the most people. by='share' ranks the rate; by='count' "
                    "ranks the number of people or households (only for rate measures).",
     "input_schema": _schema({
         "metric_id": {"type": "string", "description": "A metric_id from list_measures."},
         "chamber": {"type": "string", "enum": ["house", "senate"]},
         "by": {"type": "string", "enum": ["share", "count"]},
         "highest_first": {"type": "boolean"},
         "limit": {"type": "integer", "description": "How many districts to return (1-51)."}},
         ["metric_id", "chamber", "by", "highest_first", "limit"])},
]
TOOLS.append(
    {"name": "get_programs", "strict": True,
     "description": "Programs residents may qualify for (SNAP, Med-QUEST, Hawaiʻi EITC, food/excise "
                    "tax credit, WIC, Kūpuna Care, SSI): who they serve, eligibility rules, income "
                    "limits, how to apply, documents to bring, official link, from saved official "
                    "documents; plus the 2026 HHS poverty guidelines for Hawaiʻi. Give a district_id "
                    "to also get that district's related figures. Leave program_ids empty for all.",
     "input_schema": _schema({
         "district_id": {"type": "string", "description": "Optional district id (HD-n or SD-n); "
                                                          "empty string for none."},
         "program_ids": {"type": "array", "items": {"type": "string", "enum": [
             "snap", "med_quest", "hawaii_eitc", "food_excise_credit", "wic", "kupuna_care",
             "ssi"]}, "description": "Optional: only these programs. Empty list for all."}},
         ["district_id", "program_ids"])})
HANDLERS = {"find_district": tool_find_district, "list_measures": tool_list_measures,
            "get_programs": tool_get_programs,
            "get_district_profile": tool_get_district_profile,
            "get_local_context": tool_get_local_context, "rank_districts": tool_rank_districts}


def run_tool(name: str, args: dict, src: Sources) -> tuple[str, bool]:
    """(JSON result, is_error)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool {name}"}), True
    try:
        return json.dumps(handler(args, src), ensure_ascii=False), False
    except (ValueError, KeyError, TypeError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False), True


# --- Conversation ---------------------------------------------------------------------------

class AssistantUnavailable(Exception):
    pass


def answer(history: list[dict], selected_district: str | None = None, spend=None) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...], ending with the user's
    question. spend: an api.security.QuestionSpend (or None), checked before every model call.
    Returns {answer, sources, trace, stop_reason, unverified_numbers}."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AssistantUnavailable("The assistant needs ANTHROPIC_API_KEY in .env "
                                   "(see .env.example).")
    if not history or history[-1].get("role") != "user":
        raise ValueError("The last message must be the user's question.")

    messages: list[dict] = [{"role": m["role"], "content": str(m["content"])[:8000]}
                            for m in history[-12:] if m.get("role") in ("user", "assistant")
                            and m.get("content")]
    if messages and messages[0]["role"] != "user":
        messages = messages[1:]
    if not messages or messages[-1]["role"] != "user" or not messages[-1]["content"].strip():
        raise ValueError("The question is empty.")
    note = (f"(District selected on the page: {district_name(selected_district)}, id "
            f"{selected_district}.)" if selected_district else
            "(No district is selected on the page.)")
    messages[-1] = {"role": "user", "content": [{"type": "text", "text": messages[-1]["content"]},
                                                {"type": "text", "text": note}]}

    client = anthropic.Anthropic()
    src = Sources()
    trace: list[dict] = []
    tool_texts: list[str] = []  # every tool result, to check the numbers in the answer against
    response = None
    over_budget = False
    for _ in range(MAX_TOOL_ROUNDS):
        if spend is not None and not spend.allow():
            over_budget = True
            break
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if spend is not None:
            spend.record(response.usage)
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, is_error = run_tool(block.name, dict(block.input), src)
            tool_texts.append(result)
            trace.append({"tool": block.name, "input": block.input, "error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result,
                            **({"is_error": True} if is_error else {})})
        messages.append({"role": "user", "content": results})

    text = "".join(b.text for b in response.content if b.type == "text").strip() if response else ""
    if response is not None and response.stop_reason == "refusal":
        text = "I can't help with that request. I can answer questions about district data."
    elif over_budget and (response is None or response.stop_reason == "tool_use"):
        text = ("I stopped before finishing because the assistant reached its spending limit. "
                "Please ask a narrower question, or try again later.")
    elif response is not None and response.stop_reason == "tool_use":
        text = (text + "\n\n" if text else "") + ("I stopped before finishing because the "
                                                  "question needed too many lookups. Please ask "
                                                  "a narrower question.")
    # The model sometimes cites as "(S4)" or "(S1, S3)"; the page and the source list below
    # only recognise square brackets, so those figures would lose their source.
    text = re.sub(r"\((S\d+(?:\s*,\s*S\d+)*)\)", r"[\1]", text)
    # It also sometimes "cites" a tool, e.g. "[find_district]", despite the instructions. Tool
    # names mean nothing to readers and are not sources, so drop them.
    tool_names = "|".join(re.escape(t["name"]) for t in TOOLS)
    text = re.sub(rf"\s*\[(?:{tool_names})\]", "", text)
    # Every number the model wrote should appear in what its tools returned (or in the question).
    unverified = answer_check.unverified_numbers(text, tool_texts, [str(history[-1].get("content", ""))])
    cited = {sid for group in re.findall(r"\[([^\]]*)\]", text)
             for sid in re.findall(r"\bS\d+\b", group)}
    return {"answer": text,
            "sources": [s for s in src.items if s["id"] in cited],
            "sources_consulted": len(src.items),
            "trace": trace,
            "model": response.model if response else MODEL,
            "stop_reason": response.stop_reason if response else None,
            "unverified_numbers": unverified}
