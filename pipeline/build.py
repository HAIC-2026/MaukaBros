"""Build the fact store from the ACS for all 51 House and 25 Senate districts.

    python pipeline/build.py

Reads pipeline/indicators.yaml and the saved Census data in pipeline/raw/acs/ (made once by
pipeline/fetch_acs.py), plus the county/state context files listed in pipeline/raw/manifest.yaml
(pipeline/context.py), and writes data/kyd.duckdb with the tables in pipeline/schema.sql.
Does not call the network.
"""

import json
import math
from datetime import datetime
from pathlib import Path

import duckdb
import yaml
from blocks import build_overlaps, load_blocks
from context import load_district_zcta
from context import load_all as load_context
from fetch_acs import CHAMBERS, HAWAII, cache_path, moe_var

HERE = Path(__file__).parent
DB_PATH = Path("data/kyd.duckdb")

# Census API special values: https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html
SUPPRESSED = {-666666666, -999999999}
NOT_APPLICABLE = -888888888
CONTROLLED = -555555555


def load_indicators() -> list[dict]:
    return yaml.safe_load((HERE / "indicators.yaml").read_text(encoding="utf-8"))["indicators"]


def table_ids(indicator: dict) -> str:
    """ACS table IDs for an indicator, taken from its variable codes (B19013_001E -> B19013)."""
    return ",".join(dict.fromkeys(v.split("_")[0] for v in indicator["variables"]))


def load_raw() -> dict:
    """The saved Census data written by pipeline/fetch_acs.py."""
    path = cache_path()
    if not path.exists():
        raise SystemExit(f"{path} not found. Run: python pipeline/fetch_acs.py")
    return json.loads(path.read_text(encoding="utf-8"))


def decode(estimate: float, moe: float) -> tuple[float | None, float | None, str, str]:
    """Turn raw Census values into (value, moe, value_status, moe_status)."""
    if estimate in SUPPRESSED:
        return None, None, "suppressed", "not_applicable"
    if estimate == NOT_APPLICABLE:
        return None, None, "not_applicable", "not_applicable"
    if moe == CONTROLLED:
        return estimate, 0.0, "ok", "controlled"
    if moe < 0:
        return estimate, None, "ok", "not_computable"
    return estimate, moe, "ok", "ok"


def compute(indicator: dict, record: dict) -> tuple:
    parts = [decode(float(record[v]), float(record[moe_var(v)])) for v in indicator["variables"]]

    if indicator["type"] == "single":
        return parts[0]

    # sum: any unpublished part makes the total unpublished
    if any(p[2] != "ok" for p in parts):
        return None, None, "suppressed", "not_applicable"
    value = sum(p[0] for p in parts)
    if all(p[3] == "controlled" for p in parts):
        return value, 0.0, "ok", "controlled"
    if any(p[1] is None for p in parts):
        return value, None, "ok", "not_computable"
    return value, math.sqrt(sum(p[1] ** 2 for p in parts)), "ok", "derived"


def build() -> None:
    indicators = load_indicators()
    variables = list(dict.fromkeys(v for ind in indicators for v in ind["variables"]))
    raw = load_raw()
    missing = [v for v in variables if v not in raw["variables"]]
    if missing:
        raise SystemExit(f"indicators.yaml uses variables not in the saved data ({missing[:3]}...). "
                         "Run: python pipeline/fetch_acs.py")

    geographies, facts = [], []

    def add(geo_id: str, geo_type: str, name: str, number: int | None, rec: dict) -> None:
        geographies.append((geo_id, geo_type, name, number))
        for ind in indicators:
            value, moe, value_status, moe_status = compute(ind, rec)
            facts.append((geo_id, ind["id"], "acs5", value, moe, value_status, moe_status,
                          "direct"))

    for geo_type, (prefix, geo, expected) in CHAMBERS.items():
        records = raw["records"][geo_type]
        if len(records) != expected:
            raise SystemExit(f"Expected {expected} {geo_type} districts, got {len(records)}")
        for rec in records:
            number = int(rec[geo])
            add(f"{prefix}-{number}", geo_type, f"{geo_type.title()} District {number}", number,
                rec)

    # Comparison geographies. Names come from the Census response.
    for rec in raw["records"]["state"]:
        add(f"STATE-{HAWAII}", "state", rec["NAME"], None, rec)
    for rec in raw["records"]["county"]:
        add(f"COUNTY-{rec['county']}", "county", rec["NAME"], None, rec)

    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    # Drop dependents first so the schema can be rebuilt.
    for table in ("fact", "context_fact", "context_indicator", "tax_area_district",
                  "district_zcta", "tax_area_zip", "tax_area_credit", "tax_area",
                  "place_district", "zcta_district", "place", "block", "district_plan"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute((HERE / "schema.sql").read_text(encoding="utf-8"))
    con.execute(
        "INSERT INTO source VALUES (?, ?, ?, ?, ?, ?, ?)",
        ["acs5", "U.S. Census Bureau", "American Community Survey 5-year estimates",
         "https://www.census.gov/programs-surveys/acs", raw["period"],
         datetime.fromisoformat(raw["retrieved_at"]),  # when the data was fetched, not when built
         None],
    )
    con.executemany("INSERT INTO indicator VALUES (?, ?, ?, ?)",
                    [(i["id"], i["label"], i["unit"], table_ids(i)) for i in indicators])
    con.executemany("INSERT INTO geography VALUES (?, ?, ?, ?)", geographies)
    con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", facts)

    for ctx in load_context():
        sid, pub, dataset, url, year, retrieved, vintage = ctx["source"]
        con.execute("INSERT INTO source VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [sid, pub, dataset, url, year,
                     datetime.fromisoformat(retrieved.replace("Z", "+00:00")), vintage])
        if ctx.get("indicators"):
            con.executemany("INSERT INTO context_indicator VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            ctx["indicators"])
        if ctx.get("facts"):
            con.executemany("INSERT INTO context_fact VALUES (?, ?, ?, ?, ?, ?, ?)", ctx["facts"])
            print(f"Loaded {len(ctx['facts'])} context figures from {sid}")
        if "credit_areas" in ctx:
            con.executemany("INSERT INTO tax_area_credit VALUES (?, ?, ?, ?, ?, ?)",
                            ctx["credit_areas"])
            for label, key in (("State Total", "STATE-TOTAL"), ("Other/Unknown", "OTHER-UNKNOWN")):
                v = ctx["credit_totals"][label]
                con.execute("INSERT INTO tax_area_credit VALUES (?, ?, ?, ?, ?, ?)",
                            [key, label, v["returns"], v["food_excise"], v["renters"], v["eitc"]])
            print(f"Loaded tax-credit claims for {len(ctx['credit_areas'])} DOTAX areas")
        if "district_plan" in ctx:
            con.executemany("INSERT INTO district_plan VALUES (?, ?, ?, ?)", ctx["district_plan"])
            print(f"Loaded permanent-resident population for {len(ctx['district_plan'])} districts")
        if "tax_areas" in ctx:
            con.executemany("INSERT INTO tax_area VALUES (?, ?, ?, ?, ?, ?)", ctx["tax_areas"])
            con.executemany("INSERT INTO tax_area_zip VALUES (?, ?, ?, ?)", ctx["tax_area_zips"])
            print(f"Loaded {len(ctx['tax_areas'])} DOTAX areas and "
                  f"{len(ctx['tax_area_zips'])} ZIP codes")

    # Census district-to-ZCTA land overlaps: kept as an independent cross-check of the blocks.
    con.executemany("INSERT INTO district_zcta VALUES (?, ?, ?, ?, ?)", load_district_zcta())
    # 2020 blocks: population-weighted tax area, place and ZIP matching (pipeline/blocks.py).
    load_blocks(con)
    build_overlaps(con)

    check(con, len(indicators))
    con.close()


def check(con: duckdb.DuckDBPyConnection, n_indicators: int) -> None:
    n_facts, n_geos = con.execute(
        "SELECT (SELECT count(*) FROM fact), (SELECT count(*) FROM geography)").fetchone()
    expected = n_geos * n_indicators
    if n_facts != expected:
        raise SystemExit(f"Expected {expected} facts, got {n_facts}")

    house, senate, state = con.execute("""
        SELECT sum(value) FILTER (WHERE g.geo_type = 'house'),
               sum(value) FILTER (WHERE g.geo_type = 'senate'),
               sum(value) FILTER (WHERE g.geo_type = 'state')
        FROM fact f JOIN geography g USING (geo_id)
        WHERE indicator_id = 'pop_total'
    """).fetchone()
    if abs(house - senate) > 0.005 * senate:
        raise SystemExit(f"House and Senate population totals differ: {house} vs {senate}")
    if abs(house - state) > 0.005 * state:
        raise SystemExit(f"District and state population totals differ: {house} vs {state}")
    counties = con.execute(
        "SELECT sum(value) FROM fact JOIN geography USING (geo_id) "
        "WHERE indicator_id = 'pop_total' AND geo_type = 'county'").fetchone()[0]
    if abs(counties - state) > 0.005 * state:
        raise SystemExit(f"County and state population totals differ: {counties} vs {state}")

    print(f"Built {DB_PATH}: {n_facts} facts, {n_geos} geographies, {n_indicators} indicators")
    print(f"Population check: House {house:,.0f}, Senate {senate:,.0f}, "
          f"counties {counties:,.0f}, state {state:,.0f}")


if __name__ == "__main__":
    build()