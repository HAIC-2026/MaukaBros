"""Build the fact store from the ACS for all 51 House and 25 Senate districts.

    python pipeline/build.py

Reads pipeline/indicators.yaml, fetches every needed variable from the Census API, and writes
data/kyd.duckdb with the tables in pipeline/schema.sql.
"""

import math
import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).parent
DB_PATH = Path("data/kyd.duckdb")
YEAR = 2024
HAWAII = "15"
CHAMBERS = {
    "house": ("HD", "state legislative district (lower chamber)", 51),
    "senate": ("SD", "state legislative district (upper chamber)", 25),
}

# Census API special values: https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html
SUPPRESSED = {-666666666, -999999999}
NOT_APPLICABLE = -888888888
CONTROLLED = -555555555


def load_indicators() -> list[dict]:
    return yaml.safe_load((HERE / "indicators.yaml").read_text(encoding="utf-8"))["indicators"]


def moe_var(var: str) -> str:
    return var[:-1] + "M"


def fetch_chamber(geo: str, variables: list[str], key: str) -> list[dict]:
    fields = ["NAME"] + [v for var in variables for v in (var, moe_var(var))]
    resp = httpx.get(
        f"https://api.census.gov/data/{YEAR}/acs/acs5",
        params={"get": ",".join(fields), "for": f"{geo}:*", "in": f"state:{HAWAII}",
                "key": key},
        timeout=60,
    )
    resp.raise_for_status()
    header, *rows = resp.json()
    return [dict(zip(header, row, strict=True)) for row in rows]


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


def build(key: str) -> None:
    indicators = load_indicators()
    variables = list(dict.fromkeys(v for ind in indicators for v in ind["variables"]))

    geographies, facts = [], []
    for geo_type, (prefix, geo, expected) in CHAMBERS.items():
        records = fetch_chamber(geo, variables, key)
        if len(records) != expected:
            raise SystemExit(f"Expected {expected} {geo_type} districts, got {len(records)}")
        for rec in records:
            number = int(rec[geo])
            geo_id = f"{prefix}-{number}"
            geographies.append((geo_id, geo_type, f"{geo_type.title()} District {number}", number))
            for ind in indicators:
                value, moe, value_status, moe_status = compute(ind, rec)
                facts.append((geo_id, ind["id"], "acs5", value, moe, value_status, moe_status,
                              "direct"))

    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS fact")  # drop dependents first so the schema can be rebuilt
    con.execute((HERE / "schema.sql").read_text(encoding="utf-8"))
    con.execute(
        "INSERT INTO source VALUES (?, ?, ?, ?, ?, ?)",
        ["acs5", "U.S. Census Bureau", "American Community Survey 5-year estimates",
         "https://www.census.gov/programs-surveys/acs", f"{YEAR - 4}-{YEAR}",
         datetime.now(UTC)],
    )
    con.executemany("INSERT INTO indicator VALUES (?, ?, ?)",
                    [(i["id"], i["label"], i["unit"]) for i in indicators])
    con.executemany("INSERT INTO geography VALUES (?, ?, ?, ?)", geographies)
    con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", facts)

    check(con, len(indicators))
    con.close()


def check(con: duckdb.DuckDBPyConnection, n_indicators: int) -> None:
    n_facts = con.execute("SELECT count(*) FROM fact").fetchone()[0]
    expected = 76 * n_indicators
    if n_facts != expected:
        raise SystemExit(f"Expected {expected} facts, got {n_facts}")

    house, senate = con.execute("""
        SELECT sum(value) FILTER (WHERE g.geo_type = 'house'),
               sum(value) FILTER (WHERE g.geo_type = 'senate')
        FROM fact f JOIN geography g USING (geo_id)
        WHERE indicator_id = 'pop_total'
    """).fetchone()
    if abs(house - senate) > 0.005 * senate:
        raise SystemExit(f"House and Senate population totals differ: {house} vs {senate}")

    print(f"Built {DB_PATH}: {n_facts} facts, 76 districts, {n_indicators} indicators")
    print(f"State population check: House {house:,.0f}, Senate {senate:,.0f}")


if __name__ == "__main__":
    census_key = os.getenv("CENSUS_API_KEY")
    if not census_key:
        raise SystemExit("Set CENSUS_API_KEY in .env first (see .env.example).")
    build(census_key)