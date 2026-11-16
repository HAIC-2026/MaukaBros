"""Download the raw ACS data once and save it, so builds do not call the Census API.

    python pipeline/fetch_acs.py

Reads pipeline/indicators.yaml, fetches every needed variable (estimate and margin of error) for
all House and Senate districts, the state and the counties, and writes
pipeline/raw/acs/acs5_<year>.json. pipeline/build.py reads that file only.

Run this again only when you change indicators.yaml or want a newer ACS release.
Needs CENSUS_API_KEY in .env (see .env.example).
"""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).parent
RAW_DIR = HERE / "raw" / "acs"
YEAR = 2024
HAWAII = "15"
CHAMBERS = {
    "house": ("HD", "state legislative district (lower chamber)", 51),
    "senate": ("SD", "state legislative district (upper chamber)", 25),
}
MAX_VARS_PER_CALL = 20  # the Census API allows 50 fields per call; each variable needs 2 (E and M)


def cache_path() -> Path:
    return RAW_DIR / f"acs5_{YEAR}.json"


def moe_var(var: str) -> str:
    return var[:-1] + "M"


def all_variables() -> list[str]:
    indicators = yaml.safe_load((HERE / "indicators.yaml").read_text(encoding="utf-8"))["indicators"]
    return list(dict.fromkeys(v for ind in indicators for v in ind["variables"]))


def fetch_geo(geo: str, for_value: str, in_clause: str | None, variables: list[str],
              key: str) -> list[dict]:
    """geo is the Census geography name (the response column); for_value is e.g. '*' or '15'."""
    merged: dict[str, dict] = {}
    for i in range(0, len(variables), MAX_VARS_PER_CALL):
        batch = variables[i : i + MAX_VARS_PER_CALL]
        fields = ["NAME"] + [v for var in batch for v in (var, moe_var(var))]
        for attempt in range(5):  # the Census API intermittently returns 5xx or times out
            try:
                resp = httpx.get(
                    f"https://api.census.gov/data/{YEAR}/acs/acs5",
                    params={"get": ",".join(fields), "for": f"{geo}:{for_value}", "key": key,
                            **({"in": in_clause} if in_clause else {})},
                    timeout=60,
                )
                resp.raise_for_status()
                break
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, httpx.TimeoutException) or exc.response.status_code >= 500
                if not retryable or attempt == 4:
                    raise
                time.sleep(2**attempt)
        header, *rows = resp.json()
        for row in rows:
            rec = dict(zip(header, row, strict=True))
            merged.setdefault(rec[geo], {}).update(rec)
    return list(merged.values())


def main() -> None:
    key = os.getenv("CENSUS_API_KEY")
    if not key:
        raise SystemExit("Set CENSUS_API_KEY in .env first (see .env.example).")
    variables = all_variables()

    records: dict[str, list[dict]] = {}
    for chamber, (_, geo, expected) in CHAMBERS.items():
        records[chamber] = fetch_geo(geo, "*", f"state:{HAWAII}", variables, key)
        if len(records[chamber]) != expected:
            raise SystemExit(f"Expected {expected} {chamber} districts, got {len(records[chamber])}")
    records["state"] = fetch_geo("state", HAWAII, None, variables, key)
    records["county"] = fetch_geo("county", "*", f"state:{HAWAII}", variables, key)

    out = {
        "dataset": "American Community Survey 5-year estimates",
        "publisher": "U.S. Census Bureau",
        "year": YEAR,
        "period": f"{YEAR - 4}-{YEAR}",
        "api": f"https://api.census.gov/data/{YEAR}/acs/acs5",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "variables": variables,
        "records": records,
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path().write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    counts = ", ".join(f"{k}: {len(v)}" for k, v in records.items())
    print(f"Wrote {cache_path()} ({cache_path().stat().st_size / 1e6:.2f} MB). Records: {counts}")


if __name__ == "__main__":
    main()
