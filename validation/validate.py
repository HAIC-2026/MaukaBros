"""Validation checks for the District Insight fact store.

    python validation/validate.py

Runs four groups of checks against data/kyd.duckdb and writes validation/report.md and
validation/spot_check_sample.csv. Exits non-zero if any check fails. See PROTOCOL.md for what
each check does and does not prove.

  A. Cross-check   Re-fetch selected statistics through a DIFFERENT ACS table (subject tables)
                   and require the pipeline's value and margin of error to match.
  B. Consistency   Internal rules: counts add up, rates are between 0 and 1, no negative values.
  C. Provenance    Every fact has a source, year and URL.
  D. Mapping       Boundary district ids match the database ids one for one.
  E. Context       County/state figures from other sources (BEA...): add up, only attached to
                   counties and the state, and each traceable to a saved file.
  L. Likely eligible  Program estimates (docs/ELIGIBILITY_METHOD.md): cut points match the official
                   income tables, parts add up to the state within their margins of error, counts
                   never exceed their universe, every figure has source, year and margin of error.
"""

import csv
import json
import os
import random
import time
from datetime import date
from pathlib import Path

import sys

import duckdb
import httpx
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")  # names with ʻokina and kahakō on a Windows console
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import context  # noqa: E402  (reads saved files only)
DB_PATH = ROOT / "data" / "kyd.duckdb"
YEAR = 2024
HAWAII = "15"
CHAMBERS = {"house": ("HD", "state legislative district (lower chamber)"),
            "senate": ("SD", "state legislative district (upper chamber)")}

# Cross-check pairs: our indicator id -> (subject-table estimate variable, note).
# Variable codes taken from https://api.census.gov/data/2024/acs/acs5/subject/variables.json
CROSS = {
    "pop_total": "S0101_C01_001E",
    "pop_65_plus": "S0101_C01_030E",
    "pop_under_18": "S0101_C01_022E",
    "pop_poverty_universe": "S1701_C01_001E",
    "pop_below_poverty": "S1701_C02_001E",
    "median_household_income": "S1901_C01_012E",
}
# Pairs where a rate is numerator / denominator and must be between 0 and 1.
RATES = [
    ("pop_below_poverty", "pop_poverty_universe"),
    ("pop_65_plus", "pop_total"),
    ("rent_burdened_households", "renter_households"),
    ("snap_households", "households_total"),
    ("pop_no_health_insurance", "pop_insurance_universe"),
    ("pop_medicaid", "pop_medicaid_universe"),
    ("households_below_poverty_no_snap", "households_below_poverty"),
    ("households_below_poverty", "households_total"),
    ("pop_under_125pct_poverty", "pop_under_200pct_poverty"),
    ("pop_under_200pct_poverty", "pop_ratio_universe"),
    ("pop_under_138pct_uninsured", "pop_under_138pct_poverty"),
    ("pop_60_plus_below_poverty", "pop_60_plus_poverty_universe"),
    ("households_with_children", "households_children_universe"),
    ("households_single_parent", "households_with_children"),
    ("owner_cost_burdened_households", "owner_households_cost_computed"),
    ("pop_asian", "pop_total"),
    ("pop_filipino", "pop_asian"),
    ("pop_japanese", "pop_asian"),
    ("pop_white", "pop_total"),
    ("pop_hispanic", "pop_total"),
    ("pop_two_or_more_races", "pop_total"),
    ("households_social_security", "households_ss_universe"),
    ("pop_with_disability", "pop_disability_universe"),
    ("households_limited_english", "households_language_universe"),
    ("households_65_plus_living_alone", "households_with_65_plus"),
    ("unemployed", "labor_force"),
    ("rent_burdened_households", "renter_households"),
]
INDUSTRY_PARTS = ["ind_agriculture", "ind_construction", "ind_manufacturing", "ind_wholesale",
                  "ind_retail", "ind_transport_utilities", "ind_information",
                  "ind_finance_real_estate", "ind_professional", "ind_education_health",
                  "ind_arts_accommodation_food", "ind_other_services",
                  "ind_public_administration"]
SPOT_INDICATORS = ["pop_total", "pop_65_plus", "median_household_income", "pop_below_poverty",
                   "median_gross_rent", "pop_no_health_insurance"]

results: list[tuple[str, str, bool, str]] = []  # (group, check, passed, detail)


def record(group: str, check: str, passed: bool, detail: str = "") -> None:
    results.append((group, check, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {group}: {check}" + (f" - {detail}" if detail else ""))


def fetch_subject(geo: str, variables: list[str], key: str) -> dict[str, dict]:
    fields = ["NAME"] + [v for var in variables for v in (var, var[:-1] + "M")]
    for attempt in range(5):
        try:
            resp = httpx.get(f"https://api.census.gov/data/{YEAR}/acs/acs5/subject",
                             params={"get": ",".join(fields), "for": f"{geo}:*",
                                     "in": f"state:{HAWAII}", "key": key}, timeout=60)
            resp.raise_for_status()
            break
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt == 4 or (isinstance(exc, httpx.HTTPStatusError)
                                and exc.response.status_code < 500):
                raise
            time.sleep(2**attempt)
    header, *rows = resp.json()
    return {r[header.index(geo)]: dict(zip(header, r, strict=True)) for r in rows}


def check_cross(con, key: str) -> None:
    variables = list(CROSS.values())
    for chamber, (prefix, geo) in CHAMBERS.items():
        census = fetch_subject(geo, variables, key)
        value_bad, moe_bad, derived_dev, compared = [], [], [], 0
        for ind, var in CROSS.items():
            for number, rec in census.items():
                geo_id = f"{prefix}-{int(number)}"
                row = con.execute(
                    "SELECT value, moe, moe_status FROM fact WHERE geo_id=? AND indicator_id=?",
                    [geo_id, ind]).fetchone()
                if row is None:
                    value_bad.append(f"{geo_id} {ind}: missing in database")
                    continue
                theirs, their_moe = float(rec[var]), float(rec[var[:-1] + "M"])
                compared += 1
                if row[0] is None or abs(row[0] - theirs) > 0.5:
                    value_bad.append(f"{geo_id} {ind}: ours {row[0]} vs subject table {theirs}")
                if row[1] is None or their_moe < 0:
                    continue
                if row[2] == "derived":  # we computed this margin from several cells
                    if their_moe > 0:
                        derived_dev.append((abs(row[1] - their_moe) / their_moe, ind))
                elif abs(row[1] - their_moe) > 0.5:
                    moe_bad.append(f"{geo_id} {ind} MOE: ours {row[1]} vs {their_moe}")
        record("A cross-check", f"{chamber}: estimates for {len(CROSS)} indicators in every "
               f"district equal the ACS subject tables ({compared} comparisons)",
               not value_bad, "; ".join(value_bad[:5]))
        record("A cross-check", f"{chamber}: published margins of error equal the subject "
               "tables", not moe_bad, "; ".join(moe_bad[:5]))
        if derived_dev:
            devs = sorted(d for d, _ in derived_dev)
            median, worst = devs[len(devs) // 2], devs[-1]
            # Informational, not pass/fail: summed-cell margins are an approximation (Census
            # guidance), so they are not expected to equal the published figure.
            record("A cross-check", f"{chamber}: INFO derived margin of error "
                   f"({sorted({i for _, i in derived_dev})}) vs published: median difference "
                   f"{median:.0%}, largest {worst:.0%}. Treated as approximate.", True)


def check_consistency(con) -> None:
    # Districts partition the state, so additive counts should sum to the state total.
    rows = con.execute("""
        SELECT i.indicator_id, i.unit,
               sum(f.value) FILTER (WHERE g.geo_type='house') AS house,
               sum(f.value) FILTER (WHERE g.geo_type='senate') AS senate,
               max(f.value) FILTER (WHERE g.geo_type='state') AS state
        FROM fact f JOIN geography g USING (geo_id) JOIN indicator i USING (indicator_id)
        WHERE i.unit IN ('people','households') GROUP BY 1,2 ORDER BY 1""").fetchall()
    bad = [f"{r[0]} (house {r[2]:,.0f}, senate {r[3]:,.0f}, state {r[4]:,.0f})"
           for r in rows if abs(r[2] - r[4]) > 0.005 * r[4] or abs(r[3] - r[4]) > 0.005 * r[4]]
    record("B consistency", f"count indicators: House total and Senate total each within 0.5% "
           f"of the state ({len(rows)} indicators)", not bad, "; ".join(bad[:5]))

    bad = []
    for num, den in dict.fromkeys(RATES):
        for geo_id, n, d in con.execute("""
            SELECT a.geo_id, a.value, b.value FROM fact a JOIN fact b USING (geo_id)
            WHERE a.indicator_id=? AND b.indicator_id=? AND a.value_status='ok'
              AND b.value_status='ok'""", [num, den]).fetchall():
            if d and not (0 <= n / d <= 1):
                bad.append(f"{geo_id} {num}/{den} = {n / d:.2f}")
    record("B consistency", "every rate numerator is between 0 and its denominator",
           not bad, "; ".join(bad[:5]))

    n = con.execute("SELECT count(*) FROM fact WHERE value_status='ok' AND (value < 0 "
                    "OR moe < 0)").fetchone()[0]
    record("B consistency", "no negative values or margins of error", n == 0, f"{n} found")

    n = con.execute("SELECT count(*) FROM fact WHERE value_status='ok' AND value IS NULL"
                    ).fetchone()[0]
    record("B consistency", "no 'ok' fact is missing its value", n == 0, f"{n} found")

    # C24050: the 13 industries partition employed residents, so they must add up exactly.
    bad = []
    for geo_id, total, parts in con.execute(f"""
        SELECT geo_id, max(value) FILTER (WHERE indicator_id='employed_total'),
               sum(value) FILTER (WHERE indicator_id IN ({",".join("?" * len(INDUSTRY_PARTS))}))
        FROM fact GROUP BY geo_id""", INDUSTRY_PARTS).fetchall():
        if total is None or parts is None or abs(total - parts) > 0.5:
            bad.append(f"{geo_id}: total {total} vs industries {parts}")
    record("B consistency", "jobs by industry: the 13 industries add up to employed residents in "
           "every geography", not bad, "; ".join(bad[:5]))

    n_ind = con.execute("SELECT count(*) FROM indicator").fetchone()[0]
    n_geo = con.execute("SELECT count(*) FROM geography").fetchone()[0]
    n_fact = con.execute("SELECT count(*) FROM fact").fetchone()[0]
    record("B consistency", f"one fact per geography per indicator ({n_geo} x {n_ind})",
           n_fact == n_geo * n_ind, f"{n_fact} facts")


def check_provenance(con) -> None:
    n = con.execute("""
        SELECT count(*) FROM fact f LEFT JOIN source s USING (source_id)
        WHERE s.source_id IS NULL OR s.year IS NULL OR s.url IS NULL OR s.publisher IS NULL
           OR s.dataset IS NULL""").fetchone()[0]
    record("C provenance", "every fact has a source with publisher, dataset, year and URL",
           n == 0, f"{n} facts missing")
    n = con.execute("SELECT count(*) FROM indicator WHERE table_ids IS NULL OR table_ids=''"
                    ).fetchone()[0]
    record("C provenance", "every indicator names its ACS table", n == 0, f"{n} missing")
    n = con.execute("""SELECT count(*) FROM fact WHERE value_status<>'ok'
                       AND (value IS NOT NULL)""").fetchone()[0]
    record("C provenance", "unavailable values are stored as missing, never as a number",
           n == 0, f"{n} found")


def check_mapping(con) -> None:
    for chamber, (prefix, _) in CHAMBERS.items():
        path = ROOT / "data" / "boundaries" / f"{chamber}.geojson"
        if not path.exists():
            record("D mapping", f"{chamber} boundaries exist", False,
                   "run python pipeline/boundaries.py")
            continue
        shapes = {f["properties"]["geo_id"] for f in json.loads(path.read_text("utf-8"))["features"]}
        db = {r[0] for r in con.execute("SELECT geo_id FROM geography WHERE geo_type=?",
                                        [chamber]).fetchall()}
        record("D mapping", f"{chamber}: boundary district ids match database ids one for one "
               f"({len(shapes)} shapes, {len(db)} districts)", shapes == db,
               f"only in shapes: {sorted(shapes - db)[:5]}; only in db: {sorted(db - shapes)[:5]}")

        counties = {r[0] for r in con.execute(
            "SELECT geo_id FROM geography WHERE geo_type='county'").fetchall()}
        features = json.loads(path.read_text("utf-8"))["features"]
        bad = [f["properties"]["geo_id"] for f in features
               if f["properties"].get("county_geo_id") not in counties]
        record("D mapping", f"{chamber}: every district has a county that exists in the database "
               "(used for the county comparison)", not bad, f"{bad[:5]}")

    # Neighborhood lookup (pipeline/named_places.py): USGS GNIS points in the OPSD shapes.
    n_all, n_out = con.execute("SELECT count(*), count(*) FILTER (WHERE house_id IS NULL OR "
                               "senate_id IS NULL) FROM named_place").fetchone()
    record("D mapping", f"neighborhood names: all {n_all} USGS GNIS populated places fall inside a "
           "House and a Senate district", n_all > 0 and n_out == 0, f"{n_out} outside")
    # Independent check: the GNIS point + OPSD shape method against the Census block assignment
    # (a separate product). Where a GNIS name is also a Census place in the same county, the
    # point's districts must be districts where that place has 2020 residents. Names repeated on
    # other islands (Waimea, Kailua) are told apart by county.
    gnis_county = {"Hawaii": "COUNTY-001", "Honolulu": "COUNTY-003", "Kalawao": "COUNTY-005",
                   "Kauai": "COUNTY-007", "Maui": "COUNTY-009"}
    place_rows = con.execute("""
        SELECT p.name, any_value(b.county_geo_id), list(DISTINCT b.house_id),
               list(DISTINCT b.senate_id)
        FROM place p JOIN block b USING (place_fp) WHERE b.pop20 > 0 GROUP BY p.place_fp, p.name
        """).fetchall()
    census_places = {(plain(n), c): set(h) | set(s) for n, c, h, s in place_rows}
    compared, bad = 0, []
    for name, county, house, senate in con.execute(
            "SELECT name, county, house_id, senate_id FROM named_place").fetchall():
        districts = census_places.get((plain(name), gnis_county.get(county)))
        if districts is None:
            continue
        compared += 1
        if house not in districts or senate not in districts:
            bad.append(f"{name}: {house}/{senate}")
    record("D mapping", f"neighborhood names: the {compared} that are also Census places land in "
           "districts where that place has residents (GNIS points in OPSD shapes vs Census blocks)",
           compared > 100 and not bad, "; ".join(bad[:8]))
    kahala = con.execute("SELECT house_id FROM named_place WHERE name = 'Kāhala'").fetchone()
    record("D mapping", "Kāhala (Seth's high-income example) is found in House District 20",
           kahala == ("HD-20",), str(kahala))


def plain(s: str) -> str:
    """Lowercase, without ʻokina, apostrophes or kahakō (same rule as api/agent.py)."""
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower().replace("ʻ", "").replace("'", "").replace("‘", ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def check_context(con) -> None:
    n = con.execute("""SELECT count(*) FROM context_fact c JOIN geography g USING (geo_id)
                       WHERE g.geo_type NOT IN ('county', 'state')""").fetchone()[0]
    record("E context", "county/state-only sources are never attached to a district", n == 0,
           f"{n} found")
    n = con.execute("""SELECT count(*) FROM context_fact c LEFT JOIN source s USING (source_id)
                       WHERE s.retrieved_at IS NULL OR s.url IS NULL""").fetchone()[0]
    record("E context", "every context figure has a source URL and download date", n == 0,
           f"{n} missing")
    n = con.execute("""SELECT count(*) FROM context_fact
                       WHERE (value_status = 'ok') <> (value IS NOT NULL)""").fetchone()[0]
    record("E context", "context figures are a number only when published", n == 0, f"{n} found")
    # Only shown figures are stored, so BEA and BLS figures are re-checked against the other
    # columns of the same saved file (read again here, never downloaded).
    stored = {(g, i): v for g, i, v in con.execute(
        "SELECT geo_id, indicator_id, value FROM context_fact WHERE value IS NOT NULL").fetchall()}
    bea = context.load_bea()["check"]
    counties = [g for g, _ in context.BEA_GEOS.values() if g.startswith("COUNTY")]
    for ind in ("personal_income", "bea_population"):
        total, state = sum(bea[(g, ind)] for g in counties), bea[("STATE-15", ind)]
        # BEA publishes income in thousands of dollars, so allow rounding of a few thousand.
        record("E context", f"BEA {ind}: counties add up to the state ({total:,.0f} vs "
               f"{state:,.0f})", abs(total - state) <= 5000)
    bad = [f"{g}: {stored.get((g, 'per_capita_personal_income'))} vs "
           f"{bea[(g, 'personal_income')] / bea[(g, 'bea_population')]:,.0f}"
           for g in ["STATE-15", *counties]
           if abs(stored.get((g, "per_capita_personal_income"), 0)
                  - bea[(g, "personal_income")] / bea[(g, "bea_population")]) > 1]
    record("E context", "BEA per capita income shown equals personal income / population",
           not bad, "; ".join(bad))

    # Counties add up to the state where the source publishes both (Data Book note: SNAP
    # people "might not add to State total due to rounding", so allow 0.1%).
    for ind in ("snap_cases_monthly", "snap_people_monthly"):
        row = con.execute("""
            SELECT sum(value) FILTER (WHERE geo_id LIKE 'COUNTY-%'),
                   max(value) FILTER (WHERE geo_id = 'STATE-15')
            FROM context_fact WHERE indicator_id = ?""", [ind]).fetchone()
        if row[1] is not None:
            record("E context", f"{ind}: counties add up to the state ({row[0]:,.0f} vs "
                   f"{row[1]:,.0f})", abs(row[0] - row[1]) <= 0.001 * row[1])

    # BLS: the published rate equals unemployed / labor force (rate is rounded to 0.1).
    bls = context.load_bls()["check"]
    bad = []
    for geo_id in context.BLS_COUNTIES.values():
        rate = stored.get((geo_id, "bls_unemployment_rate"))
        unemp, lf = bls[(geo_id, "bls_unemployed")], bls[(geo_id, "bls_labor_force")]
        if rate is None or abs(100 * unemp / lf - rate) > 0.051:
            bad.append(f"{geo_id}: {rate} vs {100 * unemp / lf:.2f}")
    record("E context", "BLS unemployment rate equals unemployed / labor force in every county",
           not bad, "; ".join(bad))

    # Survey vs program records for SNAP: different measures and periods, so not pass/fail, but
    # the size of the gap is why "households not receiving SNAP" is labeled as likely overstated.
    rows = con.execute("""
        SELECT f.geo_id, f.value, c.value FROM fact f JOIN context_fact c
          ON c.geo_id = f.geo_id AND c.indicator_id = 'snap_cases_monthly'
        WHERE f.indicator_id = 'snap_households' AND c.value IS NOT NULL ORDER BY 1""").fetchall()
    record("E context (info)", "SNAP households, ACS survey 2020-2024 vs DHS average monthly "
           "cases FY2025: " + "; ".join(f"{g} {a:,.0f} vs {d:,.0f} ({a / d:.0%})"
                                        for g, a, d in rows), True)

    # Med-QUEST: counties add up to the state exactly; survey vs records (info), as for SNAP.
    row = con.execute("""
        SELECT sum(value) FILTER (WHERE geo_id LIKE 'COUNTY-%'),
               max(value) FILTER (WHERE geo_id = 'STATE-15'), any_value(period)
        FROM context_fact WHERE indicator_id = 'medquest_managed_care'""").fetchone()
    if row[1] is not None:
        record("E context", f"Med-QUEST managed care ({row[2]}): counties add up to the state "
               f"({row[0]:,.0f} vs {row[1]:,.0f})", row[0] == row[1])
        rows = con.execute("""
            SELECT f.geo_id, f.value, c.value FROM fact f JOIN context_fact c
              ON c.geo_id = f.geo_id AND c.indicator_id = 'medquest_managed_care'
            WHERE f.indicator_id = 'pop_medicaid' AND c.value IS NOT NULL ORDER BY 1""").fetchall()
        record("E context (info)", "Medicaid: residents reporting Medicaid/means-tested coverage "
               "(ACS 2020-2024) vs Med-QUEST managed-care members (" + row[2] + "): "
               + "; ".join(f"{g} {a:,.0f} vs {d:,.0f} ({a / d:.0%})" for g, a, d in rows), True)

    # DOTAX: ZIP codes add up to their area, areas to their county, counties to the state.
    if con.execute("SELECT count(*) FROM tax_area").fetchone()[0]:
        dotax = context.load_dotax()["check"]
        # DOTAX does not publish ZIP codes with ten or fewer returns (report, section 2), so an
        # area may exceed the sum of its listed ZIP codes by up to 10. Any gap is reported.
        gaps = [(a, zr, ar) for a, zr, ar in con.execute("""
            SELECT a.name, sum(z.returns), any_value(a.returns) FROM tax_area a
            LEFT JOIN tax_area_zip z USING (area_id) GROUP BY a.name ORDER BY 1""").fetchall()
                if zr is None or zr != ar]
        bad = [g for g in gaps if g[1] is None or not 0 < g[2] - g[1] <= 10]
        record("E context", "DOTAX: ZIP code returns (A-14) add up to each area (A-13), allowing "
               "up to 10 returns in unpublished ZIP codes", not bad,
               "; ".join(f"{a}: ZIPs {zr:,.0f} vs area {ar:,.0f}" for a, zr, ar in gaps))
        bad = [f"{g}: {s:,.0f} vs {dotax[g][0]:,.0f}" for g, s in con.execute(
            "SELECT county_geo_id, sum(returns) FROM tax_area GROUP BY 1").fetchall()
               if s != dotax[g][0]]
        record("E context", "DOTAX: area returns add up to each county total", not bad,
               "; ".join(bad))
        counties = sum(v[0] for g, v in dotax.items() if g.startswith("COUNTY"))
        state, unplaced, everything = (dotax[context.DOTAX_STATE][0],
                                       dotax[context.DOTAX_UNPLACED][0],
                                       dotax[context.DOTAX_ALL][0])
        record("E context", f"DOTAX: counties add up to the Hawaiʻi-addresses total "
               f"({counties:,.0f} vs {state:,.0f}), plus unidentified = all returns",
               counties == state and state + unplaced == everything)
        n = con.execute("SELECT count(*) FROM tax_area WHERE name LIKE '%''%'").fetchone()[0]
        record("E context", "DOTAX area names use the ʻokina, not an apostrophe", n == 0,
               f"{n} found")

    # F. Tax area overlap (docs/GEOGRAPHY_METHOD.md): the Census relationship files were read
    # completely, and every district and every tax area is matched.
    if con.execute("SELECT count(*) FROM tax_area_district").fetchone()[0]:
        bad = [f"{g}: {s:.4f}" for g, s in con.execute("""
            SELECT geo_id, sum(land_part) / any_value(district_land) FROM district_zcta
            GROUP BY 1""").fetchall() if abs(s - 1) > 0.001]
        record("F overlap", "Census file: each district's overlap parts add up to its land area",
               not bad, "; ".join(bad))
        n = con.execute("""SELECT count(DISTINCT geo_id) FROM district_zcta""").fetchone()[0]
        record("F overlap", "Census files cover all 51 House and 25 Senate districts", n == 76,
               f"{n} found")
        bad = [g for (g,) in con.execute("""
            SELECT geo_id FROM geography WHERE geo_type IN ('house', 'senate')
            EXCEPT SELECT geo_id FROM tax_area_district WHERE relation = 'overlaps'""").fetchall()]
        record("F overlap", "every district overlaps at least one DOTAX tax area", not bad,
               ", ".join(bad))
        bad = [f"{a} ({c})" for a, c, s in con.execute("""
            SELECT a.name, g.geo_type, sum(t.area_share) FROM tax_area a
            JOIN tax_area_district t USING (area_id) JOIN geography g USING (geo_id)
            GROUP BY 1, 2""").fetchall() if abs(s - 1) > 0.001]
        n = con.execute("SELECT count(*) FROM tax_area").fetchone()[0]
        m = con.execute("""SELECT count(DISTINCT area_id || g.geo_type) FROM tax_area_district
                           JOIN geography g USING (geo_id)""").fetchone()[0]
        record("F overlap", "each tax area's 2020 residents are fully shared out among House "
               "districts, and among Senate districts", not bad and m == 2 * n, "; ".join(bad))
        rows = con.execute("""SELECT a.name, string_agg(t.geo_id || ' ' ||
                round(100 * t.area_share, 1) || '%', ', ' ORDER BY t.area_share DESC)
            FROM tax_area a JOIN tax_area_district t USING (area_id)
            WHERE a.name IN ('Oʻahu North Shore', 'Molokaʻi') AND t.area_share > 0
            GROUP BY 1 ORDER BY 1""").fetchall()
        record("F overlap (info)", "Seth's examples, share of each area's 2020 residents by "
               "district: " + "; ".join(f"{a}: {d}" for a, d in rows)
               + " (check against the district map)", True)

    # DOTAX tax credits: A-7 areas plus "Other/Unknown" add up to the state total (columns with no
    # suppressed cell); A-4 counties add up to the state.
    if con.execute("SELECT count(*) FROM tax_area_credit").fetchone()[0]:
        bad = []
        for col in ("returns", "food_excise", "renters", "eitc"):
            parts, nulls, state = con.execute(f"""
                SELECT sum({col}) FILTER (WHERE area_id <> 'STATE-TOTAL'),
                       count(*) FILTER (WHERE {col} IS NULL),
                       max({col}) FILTER (WHERE area_id = 'STATE-TOTAL')
                FROM tax_area_credit""").fetchone()
            if nulls == 0 and parts != state:
                bad.append(f"{col}: {parts:,.0f} vs {state:,.0f}")
        record("E context", "DOTAX credits A-7: tax areas plus Other/Unknown add up to the state "
               "total for returns, food/excise, renters' and EITC claims", not bad, "; ".join(bad))
        bad = []
        for ind in ("dotax_eitc_claims", "dotax_food_excise_claims", "dotax_renters_claims"):
            s, st = con.execute("""
                SELECT sum(value) FILTER (WHERE geo_id LIKE 'COUNTY-%'),
                       max(value) FILTER (WHERE geo_id = 'STATE-15')
                FROM context_fact WHERE indicator_id = ?""", [ind]).fetchone()
            if s != st:
                bad.append(f"{ind}: {s:,.0f} vs {st:,.0f}")
        record("E context", "DOTAX credits A-4: counties add up to the state for each credit",
               not bad, "; ".join(bad))

    # 2021 Reapportionment Plan: every district once; each chamber adds to the report's total.
    if con.execute("SELECT count(*) FROM district_plan").fetchone()[0]:
        rows = dict(con.execute("""SELECT left(geo_id, 2), sum(permanent_residents)
                                   FROM district_plan GROUP BY 1""").fetchall())
        n = con.execute("SELECT count(*) FROM district_plan").fetchone()[0]
        record("E context", f"Reapportionment plan: 76 districts ({n}); House and Senate each add "
               f"up to 1,348,054 permanent residents ({rows.get('HD', 0):,} / {rows.get('SD', 0):,})",
               n == 76 and rows.get("HD") == rows.get("SD") == 1348054)

    # P. Program inventory (pipeline/programs.yaml): every document is a fingerprinted saved file,
    # every quote appears in it, and every income-table number is printed in it.
    import programs as prog
    data = prog.load()
    files = {data["poverty_guidelines"]["source_file"]} | {
        f.get("file", p["file"]) for p in data["programs"] for f in p["facts"]} | {
        p["file"] for p in data["programs"]} | {
        p["income_limits"].get("file", p["file"]) for p in data["programs"] if p.get("income_limits")}
    bad = []
    for rel in sorted(files):
        try:
            context.saved_file(rel)
        except (context.MissingFile, SystemExit) as exc:
            bad.append(f"{rel}: {exc}")
    record("P programs", f"all {len(files)} program documents are saved and match their "
           "fingerprints in the manifest", not bad, "; ".join(bad))
    n_q, n_n, probs = prog.check()
    record("P programs", f"{len(data['programs'])} programs: all {n_q} quotes appear in their saved "
           f"documents and all {n_n} income-table numbers are printed in them", not probs,
           "; ".join(probs[:10]))

    # H. Cross-check against DBEDT's published ACS district profiles (pipeline/dbedt_profiles.py):
    # every compared estimate (and published margin of error) must equal DBEDT's.
    try:
        import dbedt_profiles
        published, _ = dbedt_profiles.load()
    except context.MissingFile:
        published = None
    if published:
        ours = {(g, i): (v, m, ms) for g, i, v, m, ms in con.execute(
            "SELECT geo_id, indicator_id, value, moe, moe_status FROM fact").fetchall()}
        n_est = n_moe = 0
        bad = []
        for (g, ind), (est, moe) in published.items():
            v, m, ms = ours[(g, ind)]
            n_est += 1
            if est is None or v is None or abs(est - v) > 0.5:
                bad.append(f"{g} {ind}: DBEDT {est} vs ours {v}")
            if dbedt_profiles.MATCHES[ind][3] and ms == "ok":
                n_moe += 1
                if moe is None or m is None or abs(moe - m) > 0.5:
                    bad.append(f"{g} {ind} MOE: DBEDT {moe} vs ours {m}")
        record("H DBEDT", f"our figures equal DBEDT's published ACS district profiles: "
               f"{n_est:,} estimates and {n_moe:,} margins of error for "
               f"{len(dbedt_profiles.MATCHES)} measures in all 76 districts "
               f"({len(bad)} differences)", not bad, "; ".join(bad[:10]))

    # Low-reliability flag (api/main.py: CV = (MOE / 1.645) / estimate > 30%): how many district
    # figures it marks, for the record.
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from api import main as kyd  # noqa: E402
    flagged = total = 0
    worst = []
    for g, t in con.execute("""SELECT geo_id, geo_type FROM geography
                               WHERE geo_type IN ('house', 'senate')""").fetchall():
        for c in kyd.build_comparisons(g, t):
            if c["district"]["value"] is None:
                continue
            total += 1
            if c["district"]["low_reliability"]:
                flagged += 1
                worst.append((c["district"]["cv"] or 9, g, c["metric_id"]))
    worst.sort(reverse=True)
    record("G reliability (info)", f"{flagged} of {total} district figures are flagged low "
           "reliability (CV over 30%); highest: "
           + ", ".join(f"{g} {m} CV {cv:.0%}" for cv, g, m in worst[:3]), True)

    # G. Census blocks (pipeline/blocks.py): complete, consistent with the other Census files.
    if con.execute("SELECT count(*) FROM block").fetchone()[0]:
        n_h, n_s, pop_h, pop_s, n_blocks = con.execute("""
            SELECT count(DISTINCT house_id), count(DISTINCT senate_id),
                   (SELECT sum(pop20) FROM block), (SELECT sum(pop20) FROM block), count(*)
            FROM block""").fetchone()
        known = {g for (g,) in con.execute(
            "SELECT geo_id FROM geography WHERE geo_type IN ('house', 'senate')").fetchall()}
        used = {g for (g,) in con.execute(
            "SELECT house_id FROM block UNION SELECT senate_id FROM block").fetchall()}
        record("G blocks", f"every one of {n_blocks:,} blocks is in a known House and Senate "
               f"district; all 51 + 25 districts have blocks ({n_h} + {n_s})",
               used == known and n_h == 51 and n_s == 25, ", ".join(sorted(used ^ known)))
        # Independent check: the block files and the Census district-to-ZCTA relationship files
        # are separate products. Every populated (district, ZCTA) pair from blocks must appear
        # in the relationship files.
        missing = con.execute("""
            SELECT DISTINCT d.geo_id, b.zcta FROM block b
            CROSS JOIN LATERAL (VALUES (b.house_id), (b.senate_id)) AS d(geo_id)
            WHERE b.zcta IS NOT NULL AND b.pop20 > 0
            EXCEPT SELECT geo_id, zcta FROM district_zcta WHERE zcta IS NOT NULL""").fetchall()
        record("G blocks", "every populated block's district and ZIP area pairing appears in the "
               "Census district-to-ZCTA relationship files", not missing,
               ", ".join(f"{g}/{z}" for g, z in missing[:10]))
        bad = [f"{k} {c}: {s:.4f}" for k, c, s in con.execute("""
            SELECT place_fp, left(geo_id, 2), sum(place_share) FROM place_district GROUP BY 1, 2
            UNION ALL
            SELECT zcta, left(geo_id, 2), sum(zcta_share) FROM zcta_district GROUP BY 1, 2
            UNION ALL
            SELECT geo_id, 'tax areas', sum(district_share) FROM tax_area_district GROUP BY 1
            HAVING sum(district_share) > 1.0001""").fetchall() if abs(s - 1) > 0.0001
               and c != "tax areas" or c == "tax areas"]
        record("G blocks", "each place's and each ZIP area's residents add up to 100% per chamber; "
               "no district's tax-area shares exceed 100%", not bad, "; ".join(bad[:10]))
        rows = con.execute("""
            SELECT b.house_id, sum(b.pop20), any_value(f.value) FROM block b
            JOIN fact f ON f.geo_id = b.house_id AND f.indicator_id = 'pop_total'
            GROUP BY 1 ORDER BY abs(sum(b.pop20) - any_value(f.value)) / any_value(f.value) DESC
            LIMIT 3""").fetchall()
        record("G blocks (info)", "largest differences between 2020 Census and ACS 2020-2024 "
               "district population (blocks are only weights; expected to differ): "
               + "; ".join(f"{g} {a:,} vs {b:,.0f}" for g, a, b in rows), True)


def check_likely_eligible(con) -> None:
    """L. Residents likely eligible (programs.yaml `likely_eligible`, docs/ELIGIBILITY_METHOD.md).

    Additivity tolerance: districts partition the state, so House districts (and Senate districts,
    and counties) should add up to the state figure. The parts are separate survey estimates, so
    the gap is allowed to be as large as the 90% margin of error of the difference, using the
    Census approximation for sums: sqrt(sum of each part's MOE squared + the state's MOE squared).
    """
    import programs as prog
    sys.path.insert(0, str(ROOT))
    from api import main as kyd  # noqa: E402

    data = prog.load()
    specs = [(p, p["likely_eligible"]) for p in data["programs"] if p.get("likely_eligible")]
    est = [(p, le) for p, le in specs if le.get("estimated")]
    n_geo = con.execute("SELECT count(*) FROM geography").fetchone()[0]

    have = {p["id"] for p, _ in specs}
    missing = [pid for pid in ("snap", "med_quest", "hawaii_eitc") if pid not in have]
    no_reason = [p["id"] for p, le in specs if not le.get("estimated") and not le.get("reason")]
    record("L likely eligible", f"SNAP, Med-QUEST and the Hawaiʻi EITC each have an estimate or a "
           f"written reason for none ({len(est)} estimated: {', '.join(p['id'] for p, _ in est)}; "
           f"not estimated: {', '.join(p['id'] for p, le in specs if not le.get('estimated'))})",
           not missing and not no_reason, f"missing {missing}, no reason {no_reason}")

    summaries, probs = prog.check_cut_points()
    record("L likely eligible", "each estimate's cut point matches its program's official income "
           "table and the HHS Hawaiʻi guideline, within 1 point: " + "; ".join(summaries),
           not probs, "; ".join(probs))

    for p, le in est:
        ind = le["indicator"]
        rows = con.execute("""
            SELECT f.geo_id, g.geo_type, f.value, f.moe, f.value_status, f.moe_status,
                   s.year, s.url, s.publisher, i.table_ids
            FROM fact f JOIN geography g USING (geo_id) JOIN source s USING (source_id)
            JOIN indicator i USING (indicator_id) WHERE f.indicator_id = ?""", [ind]).fetchall()
        bad = [r[0] for r in rows if not r[6] or not r[7] or not r[8]
               or (r[4] == "ok" and (r[2] is None or r[3] is None or r[5] not in ("ok", "derived")))
               or (r[4] != "ok" and r[2] is not None)]
        tables = {r[9] for r in rows}
        table_ok = len(tables) == 1 and all(t in le["acs_cut"] for t in next(iter(tables)).split(","))
        record("L likely eligible", f"{ind}: a figure for all {n_geo} geographies, each with source, "
               f"year and margin of error (or a not-published status, never a number); ACS table "
               f"{', '.join(sorted(tables))} is the one the method names", len(rows) == n_geo
               and not bad and table_ok, f"{len(rows)} rows; bad: {bad[:5]}; tables {tables}")

        by = {r[0]: r for r in rows}
        state = by["STATE-15"]
        for geo_type, name in (("house", "House districts"), ("senate", "Senate districts"),
                               ("county", "counties")):
            parts = [r for r in rows if r[1] == geo_type]
            unpublished = [r[0] for r in parts if r[2] is None or r[3] is None]
            total = sum(r[2] or 0 for r in parts)
            tol = (sum(r[3] ** 2 for r in parts if r[3] is not None) + state[3] ** 2) ** 0.5
            record("L likely eligible", f"{ind}: {name} add up to the state within the margin of "
                   f"error of the difference ({total:,.0f} vs {state[2]:,.0f}, gap "
                   f"{total - state[2]:+,.0f}, allowed ±{tol:,.0f})",
                   not unpublished and abs(total - state[2]) <= tol,
                   f"unpublished parts: {unpublished[:5]}" if unpublished else "")

        over = []
        for uni in le["contained_in"]:
            for g, v, u in con.execute("""
                SELECT a.geo_id, a.value, b.value FROM fact a JOIN fact b USING (geo_id)
                WHERE a.indicator_id = ? AND b.indicator_id = ? AND a.value_status = 'ok'
                  AND b.value_status = 'ok'""", [ind, uni]).fetchall():
                if v > u:
                    over.append(f"{g}: {v:,.0f} > {uni} {u:,.0f}")
        record("L likely eligible", f"{ind}: never larger than its universe "
               f"({', '.join(le['contained_in'])}) in any geography", not over, "; ".join(over[:5]))

    # Every district's API response: each estimate has district, county and state entries with
    # source and year, and a margin of error wherever a value is shown.
    bad, n = [], 0
    for g, t in con.execute("""SELECT geo_id, geo_type FROM geography
                               WHERE geo_type IN ('house', 'senate')""").fetchall():
        for item in kyd.build_programs(kyd.build_comparisons(g, t), [], g):
            le = item.get("likely_eligible")
            if not le:
                continue
            if not le.get("estimated"):
                if not le.get("reason") or not le.get("final_eligibility"):
                    bad.append(f"{g} {item['id']}: no reason")
                continue
            n += 1
            src = le.get("source") or {}
            if not (src.get("year") and src.get("publisher") and src.get("tables")
                    and le.get("final_eligibility") and le.get("caveat")):
                bad.append(f"{g} {item['id']}: missing source, caveat or agency note")
            for key in ("district", "county", "state"):
                e = le.get(key)
                if e is None or (e["value"] is not None and e["moe"] is None) or (
                        e["value"] is None and e["value_status"] == "ok"):
                    bad.append(f"{g} {item['id']} {key}: {e}")
    record("L likely eligible", f"API: all {n} district estimates carry source, year, margin of "
           "error, county and state figures, the estimate caveat and the agency note", not bad,
           "; ".join(bad[:5]))

    # Info: estimates next to program records (different measures and periods; not pass/fail).
    pairs = [("snap_likely_eligible", "snap_people_monthly", "SNAP people served, average month"),
             ("medquest_likely_eligible", "medquest_managed_care", "Med-QUEST managed-care members")]
    for ind, ctx, label in pairs:
        rows = con.execute("""
            SELECT f.geo_id, f.value, f.moe, c.value, c.period FROM fact f JOIN context_fact c
              ON c.geo_id = f.geo_id AND c.indicator_id = ?
            WHERE f.indicator_id = ? AND c.value IS NOT NULL ORDER BY 1""", [ctx, ind]).fetchall()
        if rows:
            record("L likely eligible (info)", f"{ind} (ACS 2020-2024) vs {label} ({rows[0][4]}), "
                   "records as a share of the estimate: " + "; ".join(
                       f"{g} {v:,.0f} ±{m:,.0f} vs {c:,.0f} ({c / v:.0%})" for g, v, m, c, _ in rows),
                   True)
    sample = con.execute("""
        SELECT f.geo_id, f.indicator_id, f.value, f.moe FROM fact f
        WHERE f.indicator_id IN ('snap_likely_eligible', 'medquest_likely_eligible')
          AND f.geo_id IN ('STATE-15', 'HD-24', 'HD-18', 'SD-12') ORDER BY 1, 2""").fetchall()
    record("L likely eligible (info)", "sample: " + "; ".join(
        f"{g} {i.split('_')[0]} {v:,.0f} (about ±{m:,.0f})" for g, i, v, m in sample), True)


def write_spot_sample(con) -> Path:
    """A reproducible sample for subject-matter experts (e.g. DBEDT/READ) to verify by hand."""
    rng = random.Random(2026)
    districts = ([f"HD-{n}" for n in rng.sample(range(1, 52), 5)]
                 + [f"SD-{n}" for n in rng.sample(range(1, 26), 3)])
    path = ROOT / "validation" / "spot_check_sample.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["geo_id", "district", "indicator", "value", "margin_of_error", "status",
                    "acs_table", "period", "source", "verified_by_expert", "notes"])
        for geo_id in districts:
            for ind in SPOT_INDICATORS:
                r = con.execute("""
                    SELECT g.name, i.label, f.value, f.moe, f.value_status, i.table_ids,
                           s.year, s.publisher || ', ' || s.dataset
                    FROM fact f JOIN geography g USING (geo_id) JOIN indicator i USING (indicator_id)
                    JOIN source s USING (source_id) WHERE f.geo_id=? AND f.indicator_id=?""",
                                [geo_id, ind]).fetchone()
                w.writerow([geo_id, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], "", ""])
    return path


def write_report() -> Path:
    passed = sum(1 for r in results if r[2])
    lines = [f"# Validation report", "",
             f"Run on {date.today().isoformat()} against ACS 5-year {YEAR - 4}-{YEAR}. "
             f"{passed} of {len(results)} checks passed.", "",
             "| Result | Group | Check | Detail |", "|---|---|---|---|"]
    for group, check, ok, detail in results:
        lines.append(f"| {'PASS' if ok else 'FAIL'} | {group} | {check} | {detail} |")
    lines += ["", "See validation/PROTOCOL.md for what these checks do and do not prove."]
    path = ROOT / "validation" / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    key = os.getenv("CENSUS_API_KEY")
    if not key:
        raise SystemExit("Set CENSUS_API_KEY in .env first.")
    if not DB_PATH.exists():
        raise SystemExit("Run python pipeline/build.py first.")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    check_cross(con, key)
    check_consistency(con)
    check_provenance(con)
    check_mapping(con)
    check_context(con)
    check_likely_eligible(con)
    sample = write_spot_sample(con)
    report = write_report()
    con.close()
    failed = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed. "
          f"Report: {report}  Spot-check sample: {sample}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
