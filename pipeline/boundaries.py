"""Convert the official OPSD 2022 legislative district shapes to web-ready GeoJSON.

    python pipeline/boundaries.py [path to the zip]

Reads a LOCAL copy of the file; it does not download anything. Get the file by hand from
https://planning.hawaii.gov/gis/download-gis-data-expanded/ ("Legislative Districts - 2022",
Download) and save it as pipeline/raw/opsd/legislative_districts_2022.shp.zip
(see pipeline/raw/README.md). Source details and terms: pipeline/boundaries.yaml, sources.yaml.

The shapefiles are in NAD83(HARN) UTM zone 4N; this reprojects them to WGS84 longitude/latitude,
which web maps expect. Output: data/boundaries/house.geojson and data/boundaries/senate.geojson.
Each feature's `geo_id` (HD-<n> / SD-<n>) matches geo_id in the database.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import shapefile  # pyshp
from pyproj import CRS, Transformer

HERE = Path(__file__).parent
DEFAULT_ZIP = HERE / "raw" / "opsd" / "legislative_districts_2022.shp.zip"
OUT_DIR = Path("data/boundaries")
COORD_DECIMALS = 5  # about 1 meter

# (chamber, prefix, nested zip, shapefile stem, id field)
LAYERS = [
    ("house", "HD", "house22.shp.zip", "house22", "House_ID"),
    ("senate", "SD", "senate22.shp.zip", "senate22", "Sen_ID"),
]
EXPECTED = {"house": 51, "senate": 25}

# County recorded for each district in the state file (its "County" attribute) -> the county
# geo_id used in the database (Census county FIPS under state 15). Each district has one county.
COUNTY_IDS = {"HAWAII": "COUNTY-001", "OAHU": "COUNTY-003", "KAUAI": "COUNTY-007",
              "MAUI": "COUNTY-009"}


def reproject(coords, transform):
    """Recursively reproject a GeoJSON coordinate array."""
    if isinstance(coords[0], (int, float)):
        lon, lat = transform.transform(coords[0], coords[1])
        return [round(lon, COORD_DECIMALS), round(lat, COORD_DECIMALS)]
    return [reproject(c, transform) for c in coords]


def convert(outer: zipfile.ZipFile, chamber: str, prefix: str, nested: str, stem: str,
            id_field: str) -> dict:
    inner = zipfile.ZipFile(io.BytesIO(outer.read(nested)))
    names = {Path(n).suffix.lower(): n for n in inner.namelist()}
    reader = shapefile.Reader(
        shp=io.BytesIO(inner.read(names[".shp"])),
        dbf=io.BytesIO(inner.read(names[".dbf"])),
        shx=io.BytesIO(inner.read(names[".shx"])),
    )
    transform = Transformer.from_crs(
        CRS.from_wkt(inner.read(names[".prj"]).decode()), "EPSG:4326", always_xy=True)

    features = []
    for sr in reader.iterShapeRecords():
        number = int(sr.record[id_field])
        geom = sr.shape.__geo_interface__
        county = sr.record["County"].strip().upper()
        if county not in COUNTY_IDS:
            raise SystemExit(f"{chamber} district {number}: unknown county {county!r}")
        features.append({
            "type": "Feature",
            "properties": {
                "geo_id": f"{prefix}-{number}",
                "district_number": number,
                "chamber": chamber,
                "county_geo_id": COUNTY_IDS[county],
            },
            "geometry": {"type": geom["type"],
                         "coordinates": reproject(geom["coordinates"], transform)},
        })

    if len(features) != EXPECTED[chamber]:
        raise SystemExit(f"Expected {EXPECTED[chamber]} {chamber} districts, got {len(features)}")
    numbers = sorted(f["properties"]["district_number"] for f in features)
    if numbers != list(range(1, EXPECTED[chamber] + 1)):
        raise SystemExit(f"{chamber} district numbers are not 1..{EXPECTED[chamber]}")
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Download 'Legislative Districts - 2022' by hand from "
            "https://planning.hawaii.gov/gis/download-gis-data-expanded/ and save it there "
            "(see pipeline/raw/README.md).")
    outer = zipfile.ZipFile(path)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for chamber, prefix, nested, stem, id_field in LAYERS:
        collection = convert(outer, chamber, prefix, nested, stem, id_field)
        out_path = OUT_DIR / f"{chamber}.geojson"
        out_path.write_text(json.dumps(collection, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {out_path}: {len(collection['features'])} districts, "
              f"{out_path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
