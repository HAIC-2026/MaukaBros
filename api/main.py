"""REST API for district profiles, served from the fact store.

    python -m uvicorn api.main:app --reload

Then open http://127.0.0.1:8000 for the preview page, or http://127.0.0.1:8000/docs for the API docs.
"""

import json
import math
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "kyd.duckdb"

app = FastAPI(title="Know Your District API")

def table_links(table_ids: str, period: str) -> list[dict]:
    """Links to the official Census page for each ACS table behind a figure.

    The page lists the table's variables. The year in the URL is the last year of the 5-year
    period (e.g. "2020-2024" -> 2024), which is how the Census API names the dataset.
    """
    end_year = period.split("-")[-1].strip()
    return [{"table_id": t, "url": f"https://api.census.gov/data/{end_year}/acs/acs5/groups/{t}.html"}
            for t in table_ids.split(",") if t]


# Geography each figure describes, shown next to its source (brief: cite source, year, geography).
GEOGRAPHY_LABELS = {
    "house": "State House district (Census state legislative district, lower chamber)",
    "senate": "State Senate district (Census state legislative district, upper chamber)",
    "state": "State of Hawaiʻi",
    "county": "County",
}


def query(sql: str, params: list | None = None) -> list[dict]:
    if not DB_PATH.exists():
        raise HTTPException(503, "Data store not built. Run: python pipeline/build.py")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()


@app.get("/api/districts")
def list_districts() -> list[dict]:
    return query("""
        SELECT geo_id, geo_type, name, district_number
        FROM geography
        WHERE geo_type IN ('house', 'senate')
        ORDER BY geo_type, district_number
    """)


@app.get("/api/comparisons")
def list_comparisons() -> list[dict]:
    """State and county geographies, for comparing a district against its county and the state."""
    return query("""
        SELECT geo_id, geo_type, name
        FROM geography
        WHERE geo_type IN ('state', 'county')
        ORDER BY geo_type DESC, name
    """)


@app.get("/api/districts/{geo_id}")
def get_district(geo_id: str) -> dict:
    geo_id = geo_id.upper()
    district = query("SELECT geo_id, geo_type, name FROM geography WHERE geo_id = ?", [geo_id])
    if not district:
        raise HTTPException(404, f"Unknown district: {geo_id}")

    rows = query("""
        SELECT f.indicator_id, i.label, i.unit, i.table_ids, f.value, f.moe,
               f.value_status, f.moe_status, f.method,
               s.publisher, s.dataset, s.year, s.url
        FROM fact f
        JOIN indicator i USING (indicator_id)
        JOIN source s USING (source_id)
        WHERE f.geo_id = ?
        ORDER BY i.indicator_id
    """, [geo_id])

    geography = GEOGRAPHY_LABELS.get(district[0]["geo_type"], district[0]["geo_type"])
    facts = [
        {
            "indicator_id": r["indicator_id"],
            "label": r["label"],
            "unit": r["unit"],
            "value": r["value"],
            "moe": r["moe"],
            "value_status": r["value_status"],
            "moe_status": r["moe_status"],
            "method": r["method"],
            "source": {
                "publisher": r["publisher"],
                "dataset": r["dataset"],
                "table_ids": r["table_ids"],
                "tables": table_links(r["table_ids"], r["year"]),
                "year": r["year"],
                "url": r["url"],
                "geography": geography,
            },
        }
        for r in rows
    ]
    is_district = district[0]["geo_type"] in ("house", "senate")
    comparisons = build_comparisons(geo_id, district[0]["geo_type"]) if is_district else []
    context = build_context(district_county(geo_id)) if is_district else []
    tax_areas = build_tax_areas(geo_id) if is_district else None
    return {**district[0], "facts": facts, "comparisons": comparisons, "county_context": context,
            "tax_areas": tax_areas}


def build_tax_areas(geo_id: str) -> dict | None:
    """DOTAX tax areas that overlap the district (docs/GEOGRAPHY_METHOD.md). Each area's figures
    are DOTAX's figures for the whole area, never a district figure."""
    rows = query("""
        SELECT a.name, a.returns, a.median_agi, t.relation, t.district_share, t.area_share
        FROM tax_area_district t JOIN tax_area a USING (area_id)
        WHERE t.geo_id = ? ORDER BY t.relation, t.district_share DESC""", [geo_id])
    if not rows:
        return None
    src = query("""SELECT s.publisher, s.dataset, s.url, s.vintage, s.retrieved_at, i.table_id,
                          i.table_url, i.caveat
                   FROM source s JOIN context_indicator i ON i.indicator_id = 'dotax_median_agi'
                   WHERE s.source_id = 'dotax_individual_income'""")[0]
    return {
        "label": "Median income on resident tax returns",
        "period": "Tax year 2023",
        "areas": [{"name": r["name"], "relation": r["relation"], "returns": r["returns"],
                   "median_agi": r["median_agi"],
                   "share_of_district_land": r["district_share"],
                   "share_of_area_land_in_district": r["area_share"]} for r in rows],
        "district_land_in_no_tax_area": max(0.0, 1 - sum(r["district_share"] for r in rows)),
        "applies_to": "Each figure is for the whole tax area, as published by DOTAX, not for "
                      "this district. Areas are matched to the district by land overlap; no "
                      "figure is split or estimated.",
        "caveat": src["caveat"],
        "source": {"publisher": src["publisher"], "dataset": src["dataset"], "url": src["url"],
                   "vintage": src["vintage"], "retrieved_at": src["retrieved_at"].date().isoformat(),
                   "tables": [{"table_id": "Table A-13", "url": src["table_url"]},
                              {"table_id": "Table A-14 (ZIP codes in each area)",
                               "url": src["table_url"]}]},
        "overlap_source": "U.S. Census Bureau, 2024 State Legislative District to 2020 ZIP Code "
                          "Tabulation Area relationship files (land area of each overlap).",
    }


def build_context(county_id: str | None) -> list[dict]:
    """County and state figures from sources that do not publish by legislative district
    (BEA, BLS, DBEDT Data Book). Each is labeled with its own source, period and geography; none of them
    describes the district itself."""
    geos = ["STATE-15"] + ([county_id] if county_id else [])
    rows = query(f"""
        SELECT c.geo_id, g.name, c.indicator_id, i.label, i.unit, i.table_id, i.table_url,
               i.table_title, i.original_source, i.caveat, c.period, c.value, c.value_status, c.note,
               s.publisher, s.dataset, s.url, s.vintage, s.retrieved_at
        FROM context_fact c
        JOIN context_indicator i USING (indicator_id)
        JOIN source s USING (source_id)
        JOIN geography g USING (geo_id)
        WHERE c.geo_id IN ({",".join("?" * len(geos))})
        ORDER BY CASE c.source_id WHEN 'dbedt_databook' THEN 1 WHEN 'dotax_individual_income' THEN 2
                 WHEN 'bea_cainc1' THEN 3 ELSE 4 END,
                 c.indicator_id
    """, geos)
    out: dict[str, dict] = {}
    for r in rows:
        item = out.setdefault(r["indicator_id"], {
            "indicator_id": r["indicator_id"], "label": r["label"], "unit": r["unit"],
            "period": r["period"], "caveat": r["caveat"],
            "source": {"publisher": r["publisher"], "dataset": r["dataset"], "url": r["url"],
                       "vintage": r["vintage"], "table_title": r["table_title"],
                       "original_source": r["original_source"],
                       "retrieved_at": r["retrieved_at"].date().isoformat(),
                       "tables": [{"table_id": r["table_id"], "url": r["table_url"]}]},
            "county": None, "state": None,
            "applies_to": "The county and the state, not this district. The source does not "
                          "publish figures by legislative district.",
        })
        entry = {"geo_id": r["geo_id"], "name": r["name"],
                 "value": r["value"] if r["value_status"] == "ok" else None,
                 "value_status": r["value_status"], "note": r["note"]}
        item["state" if r["geo_id"] == "STATE-15" else "county"] = entry
    return list(out.values())


# --- Map support ---------------------------------------------------------------------------
# Metrics a map can color by. A count would mislead on a map because districts differ in size,
# so most are rates: numerator / denominator, both indicator ids from pipeline/indicators.yaml.
# Rates are computed here from published estimates. Each rate's margin of error uses the Census
# Bureau's formula for a proportion (numerator is a subset of the denominator); see
# metric_estimate().
MAP_METRICS = {
    "median_household_income": {
        "label": "Median household income", "format": "dollars", "value": "median_household_income"},
    "poverty_rate": {
        "label": "Residents below the poverty level", "format": "percent",
        "numerator": "pop_below_poverty", "denominator": "pop_poverty_universe"},
    "share_65_plus": {
        "label": "Residents age 65 and older (kūpuna)", "format": "percent",
        "numerator": "pop_65_plus", "denominator": "pop_total"},
    "rent_burden_rate": {
        "label": "Renter households paying 30% or more of income on rent", "format": "percent",
        "numerator": "rent_burdened_households", "denominator": "renter_households"},
    "snap_share": {
        "label": "Households receiving SNAP", "format": "percent",
        "numerator": "snap_households", "denominator": "households_total"},
    "no_insurance_rate": {
        "label": "Residents with no health insurance", "format": "percent",
        "numerator": "pop_no_health_insurance", "denominator": "pop_insurance_universe"},
    "medicaid_share": {
        "label": "Residents with Medicaid or other means-tested public health coverage",
        "format": "percent", "numerator": "pop_medicaid", "denominator": "pop_medicaid_universe"},
    "social_security_share": {
        "label": "Households with Social Security income", "format": "percent",
        "numerator": "households_social_security", "denominator": "households_ss_universe"},
    "disability_rate": {
        "label": "Residents with a disability", "format": "percent",
        "numerator": "pop_with_disability", "denominator": "pop_disability_universe"},
    "limited_english_share": {
        "label": "Limited English speaking households", "format": "percent",
        "numerator": "households_limited_english", "denominator": "households_language_universe"},
    "kupuna_alone_share": {
        "label": "Households with someone 65+ where the person lives alone", "format": "percent",
        "numerator": "households_65_plus_living_alone", "denominator": "households_with_65_plus"},
    "unemployment_rate": {
        "label": "Unemployed share of the civilian labor force", "format": "percent",
        "numerator": "unemployed", "denominator": "labor_force"},
    "under_18_share": {
        "label": "Residents under age 18", "format": "percent",
        "numerator": "pop_under_18", "denominator": "pop_total"},
    "median_gross_rent": {
        "label": "Median gross rent", "format": "dollars", "value": "median_gross_rent"},
    "income_under_50k_share": {
        "label": "Households with income under $50,000", "format": "percent",
        "numerator": "households_income_under_50k", "denominator": "households_total"},
    "income_200k_plus_share": {
        "label": "Households with income of $200,000 or more", "format": "percent",
        "numerator": "households_income_200k_plus", "denominator": "households_total"},
    "nhpi_share": {
        "label": "Native Hawaiian and Pacific Islander residents (alone or in combination)",
        "format": "percent", "numerator": "pop_nhpi", "denominator": "pop_total",
        "group": "Ethnic background"},
    # Added 2026-11-16 (pipeline/indicators.yaml). Ethnic groups are "alone or in combination":
    # a person is counted in each group they report, so the shares overlap.
    "asian_share": {
        "label": "Asian residents (alone or in combination)", "format": "percent",
        "numerator": "pop_asian", "denominator": "pop_total", "group": "Ethnic background"},
    "filipino_share": {
        "label": "Filipino residents (alone or in combination)", "format": "percent",
        "numerator": "pop_filipino", "denominator": "pop_total", "group": "Ethnic background"},
    "japanese_share": {
        "label": "Japanese residents (alone or in combination)", "format": "percent",
        "numerator": "pop_japanese", "denominator": "pop_total", "group": "Ethnic background"},
    "white_share": {
        "label": "White residents (alone or in combination)", "format": "percent",
        "numerator": "pop_white", "denominator": "pop_total", "group": "Ethnic background"},
    "hispanic_share": {
        "label": "Hispanic or Latino residents (any race)", "format": "percent",
        "numerator": "pop_hispanic", "denominator": "pop_total", "group": "Ethnic background"},
    "two_or_more_races_share": {
        "label": "Residents of two or more races", "format": "percent",
        "numerator": "pop_two_or_more_races", "denominator": "pop_total",
        "group": "Ethnic background"},
    "households_with_children_share": {
        "label": "Households with children under 18", "format": "percent",
        "numerator": "households_with_children", "denominator": "households_children_universe"},
    "single_parent_share": {
        "label": "Households with children under 18 and a single parent (no spouse present)",
        "format": "percent", "numerator": "households_single_parent",
        "denominator": "households_children_universe"},
    "owner_cost_burden_rate": {
        "label": "Homeowners paying 30% or more of income on housing costs", "format": "percent",
        "numerator": "owner_cost_burdened_households",
        "denominator": "owner_households_cost_computed"},
    "kupuna_poverty_rate": {
        "label": "Residents age 60 and older below the poverty level", "format": "percent",
        "numerator": "pop_60_plus_below_poverty", "denominator": "pop_60_plus_poverty_universe"},
    # Program need: income relative to the poverty line. Not eligibility counts (program rules
    # are applied separately, in a written method).
    "under_125pct_poverty_share": {
        "label": "Residents with income under 125% of the poverty level", "format": "percent",
        "numerator": "pop_under_125pct_poverty", "denominator": "pop_ratio_universe",
        "group": "Program need and uptake"},
    "under_200pct_poverty_share": {
        "label": "Residents with income under 200% of the poverty level", "format": "percent",
        "numerator": "pop_under_200pct_poverty", "denominator": "pop_ratio_universe",
        "group": "Program need and uptake"},
    "poor_households_without_snap_share": {
        "label": "Households below the poverty level that did not receive SNAP",
        "format": "percent", "numerator": "households_below_poverty_no_snap",
        "denominator": "households_below_poverty", "group": "Program need and uptake"},
    "low_income_uninsured_rate": {
        "label": "Residents with income under 138% of the poverty level who have no health "
                 "insurance", "format": "percent", "numerator": "pop_under_138pct_uninsured",
        "denominator": "pop_under_138pct_poverty", "group": "Program need and uptake"},
}
for _m in ("snap_share", "medicaid_share", "no_insurance_rate"):
    MAP_METRICS[_m]["group"] = "Program need and uptake"
# Industry of employed residents (ACS C24050): share of employed residents 16+ in each industry.
# Where residents work by industry, wherever the job is located; not jobs inside the district.
INDUSTRIES = {
    "ind_agriculture": "Agriculture, forestry, fishing and hunting, and mining",
    "ind_construction": "Construction",
    "ind_manufacturing": "Manufacturing",
    "ind_wholesale": "Wholesale trade",
    "ind_retail": "Retail trade",
    "ind_transport_utilities": "Transportation and warehousing, and utilities",
    "ind_information": "Information",
    "ind_finance_real_estate": "Finance and insurance, and real estate, and rental and leasing",
    "ind_professional": "Professional, scientific, and management, and administrative, and "
                        "waste management services",
    "ind_education_health": "Educational services, and health care and social assistance",
    "ind_arts_accommodation_food": "Arts, entertainment, and recreation, and accommodation "
                                   "and food services",
    "ind_other_services": "Other services, except public administration",
    "ind_public_administration": "Public administration",
}
for _id, _label in INDUSTRIES.items():
    MAP_METRICS[_id + "_share"] = {
        "label": f"Employed residents working in: {_label}", "format": "percent",
        "group": "Jobs held by residents, by industry",
        "numerator": _id, "denominator": "employed_total"}
# Display order of metric groups, and the note shown under each group's heading.
METRIC_GROUPS = {
    "District profile": None,
    "Program need and uptake": (
        "Income compared with the federal poverty line, and whether residents say they receive "
        "help. These are not eligibility counts: each program has its own rules, and final "
        "eligibility is always decided by the agency. Survey answers count fewer SNAP households "
        "than DHS program records (see County and state context), so the share of households "
        "not receiving SNAP is likely overstated."),
    "Ethnic background": (
        "Share of residents. \"Alone or in combination\" counts a person in every group they "
        "report, so the shares add up to more than 100%."),
    "Jobs held by residents, by industry": (
        "Share of employed residents age 16 and older, wherever they work."),
}


def ordered_metrics() -> list[tuple[str, dict]]:
    order = list(METRIC_GROUPS)
    return sorted(MAP_METRICS.items(),
                  key=lambda kv: order.index(kv[1].get("group", "District profile")))


BOUNDARY_DIR = ROOT / "data" / "boundaries"


def metric_estimate(metric: dict, vals: dict) -> tuple[float | None, float | None]:
    """(value, margin of error) for a map/comparison metric.

    vals maps indicator id -> (value, moe), with value None when the source did not publish it.
    For a rate, the margin of error follows the ACS handbook formula for a proportion
    (numerator is a subset of the denominator):
        moe = sqrt(moe_num^2 - p^2 * moe_den^2) / den, falling back to
        sqrt(moe_num^2 + p^2 * moe_den^2) / den if the term under the root is negative.
    """
    if "value" in metric:
        value, moe = vals.get(metric["value"], (None, None))
        return value, moe
    (num, moe_n), (den, moe_d) = (vals.get(metric["numerator"], (None, None)),
                                  vals.get(metric["denominator"], (None, None)))
    if num is None or not den:
        return None, None
    p = num / den
    if moe_n is None or moe_d is None:
        return p, None
    inner = moe_n**2 - p**2 * moe_d**2
    return p, math.sqrt(inner if inner >= 0 else moe_n**2 + p**2 * moe_d**2) / den


def fetch_values(geo_ids: list[str]) -> dict[str, dict]:
    """{geo_id: {indicator_id: (value, moe)}}; value is None unless the source published it."""
    rows = query(f"""
        SELECT geo_id, indicator_id, value, moe, value_status FROM fact
        WHERE geo_id IN ({",".join("?" * len(geo_ids))})""", geo_ids)
    out: dict[str, dict] = {}
    for r in rows:
        ok = r["value_status"] == "ok"
        out.setdefault(r["geo_id"], {})[r["indicator_id"]] = (
            r["value"] if ok else None, r["moe"] if ok else None)
    return out


_district_counties: dict[str, str] | None = None


def district_county(geo_id: str) -> str | None:
    """County geo_id for a district, from the county recorded in the state boundary file."""
    global _district_counties
    if _district_counties is None:
        found: dict[str, str] = {}
        for chamber in ("house", "senate"):
            path = BOUNDARY_DIR / f"{chamber}.geojson"
            if path.exists():
                for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
                    found[f["properties"]["geo_id"]] = f["properties"].get("county_geo_id")
        _district_counties = found
    return _district_counties.get(geo_id)


def compare(metric_id: str, district_vals: dict, ref_vals: dict | None) -> dict | None:
    metric = MAP_METRICS[metric_id]
    d_value, d_moe = metric_estimate(metric, district_vals)
    if ref_vals is None:
        return None
    r_value, r_moe = metric_estimate(metric, ref_vals)
    out = {"value": r_value, "moe": r_moe, "difference": None}
    if d_value is not None and r_value is not None:
        diff = d_value - r_value
        moe = (math.sqrt(d_moe**2 + r_moe**2) if d_moe is not None and r_moe is not None
               else None)
        out["difference"] = {
            "absolute": diff,  # percentage points (as a fraction) for rates, dollars for medians
            "relative": diff / r_value if r_value else None,
            "moe": moe,
            "within_margin_of_error": None if moe is None else abs(diff) <= moe,
        }
    return out


def build_comparisons(geo_id: str, geo_type: str) -> list[dict]:
    county_id = district_county(geo_id)
    ind_tables = {r["indicator_id"]: r["table_ids"]
                  for r in query("SELECT indicator_id, table_ids FROM indicator")}
    src = query("SELECT publisher, dataset, year, url FROM source WHERE source_id = 'acs5'")[0]
    geos = [geo_id, "STATE-15"] + ([county_id] if county_id else [])
    vals = fetch_values(geos)
    names = {r["geo_id"]: r["name"] for r in query(
        f"SELECT geo_id, name FROM geography WHERE geo_id IN ({','.join('?' * len(geos))})", geos)}
    out = []
    for metric_id, metric in ordered_metrics():
        d_value, d_moe = metric_estimate(metric, vals.get(geo_id, {}))
        used = [metric["value"]] if "value" in metric else [metric["numerator"],
                                                            metric["denominator"]]
        tables = {t["table_id"]: t for i in used for t in table_links(ind_tables[i], src["year"])}
        out.append({
            "metric_id": metric_id, "label": metric["label"], "format": metric["format"],
            "group": metric.get("group", "District profile"),
            "group_note": METRIC_GROUPS[metric.get("group", "District profile")],
            "source": {**src, "geography": GEOGRAPHY_LABELS[geo_type],
                       "tables": list(tables.values())},
            "district": {"value": d_value, "moe": d_moe},
            "state": {"geo_id": "STATE-15", "name": names.get("STATE-15"),
                      **(compare(metric_id, vals.get(geo_id, {}), vals.get("STATE-15")) or {})},
            "county": ({"geo_id": county_id, "name": names.get(county_id),
                        **(compare(metric_id, vals.get(geo_id, {}), vals.get(county_id)) or {})}
                       if county_id else None),
        })
    return out


@app.get("/api/map/metrics")
def list_map_metrics() -> list[dict]:
    return [{"metric_id": k, "label": m["label"], "format": m["format"],
             "group": m.get("group", "District profile")}
            for k, m in ordered_metrics()]


@app.get("/api/map/{metric_id}/{chamber}")
def map_layer(metric_id: str, chamber: str) -> dict:
    """GeoJSON district shapes for one chamber with one metric's value on each feature."""
    metric = MAP_METRICS.get(metric_id)
    if metric is None:
        raise HTTPException(404, f"Unknown metric: {metric_id}")
    if chamber not in ("house", "senate"):
        raise HTTPException(404, "chamber must be 'house' or 'senate'")
    path = BOUNDARY_DIR / f"{chamber}.geojson"
    if not path.exists():
        raise HTTPException(503, "Boundaries not built. Run: python pipeline/boundaries.py")

    ids = [metric["value"]] if "value" in metric else [metric["numerator"], metric["denominator"]]
    rows = query(f"""
        SELECT f.geo_id, f.indicator_id, f.value, f.moe, f.value_status, s.year, s.publisher,
               s.dataset, s.url, i.table_ids
        FROM fact f JOIN source s USING (source_id) JOIN indicator i USING (indicator_id)
        WHERE f.indicator_id IN ({",".join("?" * len(ids))})
          AND f.geo_id IN (SELECT geo_id FROM geography
                           WHERE geo_type IN (?, 'state'))
    """, [*ids, chamber])

    by_geo: dict[str, dict] = {}
    source = None
    tables: dict[str, dict] = {}
    for r in rows:
        ok = r["value_status"] == "ok"
        by_geo.setdefault(r["geo_id"], {})[r["indicator_id"]] = (
            r["value"] if ok else None, r["moe"] if ok else None)
        source = {"publisher": r["publisher"], "dataset": r["dataset"], "year": r["year"],
                  "url": r["url"]}
        for t in table_links(r["table_ids"], r["year"]):
            tables[t["table_id"]] = t
    if source:
        source["tables"] = list(tables.values())  # every ACS table behind this map value

    def metric_value(vals: dict) -> float | None:
        return metric_estimate(metric, vals)[0]

    collection = json.loads(path.read_text(encoding="utf-8"))
    for feature in collection["features"]:
        geo_id = feature["properties"]["geo_id"]
        value = metric_value(by_geo.get(geo_id, {}))
        feature["properties"]["name"] = f"{chamber.title()} District {feature['properties']['district_number']}"
        feature["properties"]["value"] = value
        feature["properties"]["value_available"] = value is not None

    state_value = metric_value(by_geo.get("STATE-15", {}))
    collection["meta"] = {
        "metric_id": metric_id, "label": metric["label"], "format": metric["format"],
        "geography": GEOGRAPHY_LABELS[chamber],
        "state_value": state_value, "source": source,
        "uncertainty": "Margins of error are shown in each district's comparison table.",
    }
    return collection


# Serve the preview page. Mounted last so /api routes take priority.
class ChatRequest(BaseModel):
    messages: list[dict]                 # [{"role": "user"|"assistant", "content": str}, ...]
    district_id: str | None = None       # district selected on the page, if any


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    """The research assistant (api/agent.py). Answers only from this fact store, with sources."""
    from api import agent  # imported here: agent.py imports this module

    selected = req.district_id.upper() if req.district_id else None
    if selected and not query("SELECT 1 FROM geography WHERE geo_id = ? AND geo_type IN "
                              "('house', 'senate')", [selected]):
        selected = None
    try:
        return agent.answer(req.messages, selected)
    except agent.AssistantUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except agent.anthropic.RateLimitError as exc:
        raise HTTPException(429, "The assistant is busy. Please try again in a minute.") from exc
    except agent.anthropic.APIConnectionError as exc:
        raise HTTPException(502, "Could not reach the AI service. Check the connection.") from exc
    except agent.anthropic.APIStatusError as exc:
        raise HTTPException(502, f"The AI service returned an error ({exc.status_code}).") from exc


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")