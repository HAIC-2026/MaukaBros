"""REST API for district profiles, served from the fact store.

    python -m uvicorn api.main:app --reload

Then open http://127.0.0.1:8000 for the preview page, or http://127.0.0.1:8000/docs for the API docs.
"""

from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "kyd.duckdb"

app = FastAPI(title="Know Your District API")


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
        ORDER BY geo_type, district_number
    """)


@app.get("/api/districts/{geo_id}")
def get_district(geo_id: str) -> dict:
    geo_id = geo_id.upper()
    district = query("SELECT geo_id, geo_type, name FROM geography WHERE geo_id = ?", [geo_id])
    if not district:
        raise HTTPException(404, f"Unknown district: {geo_id}")

    rows = query("""
        SELECT f.indicator_id, i.label, i.unit, f.value, f.moe,
               f.value_status, f.moe_status, f.method,
               s.publisher, s.dataset, s.year, s.url
        FROM fact f
        JOIN indicator i USING (indicator_id)
        JOIN source s USING (source_id)
        WHERE f.geo_id = ?
        ORDER BY i.indicator_id
    """, [geo_id])

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
                "year": r["year"],
                "url": r["url"],
            },
        }
        for r in rows
    ]
    return {**district[0], "facts": facts}


# Serve the preview page. Mounted last so /api routes take priority.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")