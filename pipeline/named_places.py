"""Neighborhood and village names: which House and Senate district each named place is in.

Census places (towns and CDPs) cover only part of Hawaiʻi; neighborhoods such as Kāhala or Kaimukī
are inside "Urban Honolulu" and have no Census boundary. The U.S. Geological Survey's Geographic
Names Information System (GNIS) is the federal register of official place names, and gives each
populated place one reference point. This module places each point in a district using the
official OPSD 2022 district shapes.

A point is not a boundary: a neighborhood near a district line can extend into the next district.
The assistant says so whenever it uses this lookup (api/agent.py, tool_find_district).

Reads two saved files, nothing is downloaded:
  - pipeline/raw/usgs/DomesticNames_HI_Text.zip  (GNIS, listed in manifest.yaml)
  - pipeline/raw/opsd/legislative_districts_2022.shp.zip  (OPSD, recorded in boundaries.yaml)
"""

import csv
import io
import zipfile
from pathlib import Path

import shapefile  # pyshp
from pyproj import CRS, Transformer

from context import saved_file

HERE = Path(__file__).parent
GNIS_FILE = "usgs/DomesticNames_HI_Text.zip"
GNIS_PUBLISHED = "2026-11-02"  # publication date in the file's metadata
OPSD_ZIP = HERE / "raw" / "opsd" / "legislative_districts_2022.shp.zip"
LAYERS = [("HD", "house22.shp.zip", "House_ID"), ("SD", "senate22.shp.zip", "Sen_ID")]


def _district_shapes(outer: zipfile.ZipFile, nested: str, id_field: str):
    """[(number, bbox, rings)] in the shapefile's own projected coordinates, and the CRS."""
    inner = zipfile.ZipFile(io.BytesIO(outer.read(nested)))
    names = {Path(n).suffix.lower(): n for n in inner.namelist()}
    reader = shapefile.Reader(shp=io.BytesIO(inner.read(names[".shp"])),
                              dbf=io.BytesIO(inner.read(names[".dbf"])),
                              shx=io.BytesIO(inner.read(names[".shx"])))
    shapes = []
    for sr in reader.iterShapeRecords():
        pts, parts = sr.shape.points, list(sr.shape.parts) + [len(sr.shape.points)]
        rings = [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        shapes.append((int(sr.record[id_field]), sr.shape.bbox, rings))
    return shapes, CRS.from_wkt(inner.read(names[".prj"]).decode())


def _inside(x: float, y: float, rings) -> bool:
    """Even-odd rule over every ring, so holes in a district are handled."""
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def _locate(x: float, y: float, shapes) -> int | None:
    for number, (x0, y0, x1, y1), rings in shapes:
        if x0 <= x <= x1 and y0 <= y <= y1 and _inside(x, y, rings):
            return number
    return None


def load_named_places() -> list[tuple]:
    """Rows for the named_place table: (feature_id, name, county, lat, lon, house_id, senate_id)."""
    gnis_path, _ = saved_file(GNIS_FILE)
    if not OPSD_ZIP.exists():
        raise SystemExit(f"{OPSD_ZIP} not found (see pipeline/raw/README.md)")
    with zipfile.ZipFile(gnis_path) as z:
        text_name = next(n for n in z.namelist() if n.endswith(".txt"))
        text = z.read(text_name).decode("utf-8-sig")
    places = [r for r in csv.DictReader(io.StringIO(text), delimiter="|")
              if r["feature_class"] == "Populated Place" and r["state_numeric"] == "15"
              and "(historical)" not in r["feature_name"]
              and float(r["prim_lat_dec"] or 0) != 0]

    outer = zipfile.ZipFile(OPSD_ZIP)
    located: dict[str, dict[str, int | None]] = {}
    for prefix, nested, id_field in LAYERS:
        shapes, crs = _district_shapes(outer, nested, id_field)
        to_map = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        for r in places:
            x, y = to_map.transform(float(r["prim_long_dec"]), float(r["prim_lat_dec"]))
            located.setdefault(r["feature_id"], {})[prefix] = _locate(x, y, shapes)

    rows = []
    for r in places:
        d = located[r["feature_id"]]
        rows.append((r["feature_id"], r["feature_name"], r["county_name"],
                     float(r["prim_lat_dec"]), float(r["prim_long_dec"]),
                     f"HD-{d['HD']}" if d["HD"] else None, f"SD-{d['SD']}" if d["SD"] else None))
    return rows
