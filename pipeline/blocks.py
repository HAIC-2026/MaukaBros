"""2020 Census blocks: population-weighted matching of other areas to districts.

Every 2020 Census block lies wholly in one House district, one Senate district (2024 plans, the
Census Bureau's block equivalency files), one ZIP code tabulation area and at most one Census place.
Adding up block populations therefore says how many 2020 residents an area shares with a district,
without splitting any published figure. Used for:

  - tax_area_district: which DOTAX tax areas overlap a district, by residents (docs/GEOGRAPHY_METHOD.md)
  - place_district:    which districts a Census place (town or CDP) is in, for place-name lookup
  - zcta_district:     which districts a ZIP code area is in, for ZIP lookup

Reads only the saved extracts in pipeline/raw/census/blocks/ (see pipeline/extract_census_blocks.py).
"""

import csv
import io
import zipfile

from context import OVERLAP_THRESHOLD, saved_file

BLOCKS = "census/blocks/"


def _csv(rel: str) -> list[dict]:
    path, _ = saved_file(BLOCKS + rel)
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_blocks(con) -> None:
    blocks = {r["geoid20"]: r for r in _csv("hi_blocks_2020.csv")}
    sldl = {r["block_geoid"]: r["sldl"] for r in _csv("hi_block_sldl24.csv")}
    sldu = {r["block_geoid"]: r["sldu"] for r in _csv("hi_block_sldu24.csv")}
    zcta = {r["block_geoid"]: r["zcta"] for r in _csv("hi_block_zcta520.csv")}

    path, _ = saved_file(BLOCKS + "BlockAssign_ST15_HI.zip")
    with zipfile.ZipFile(path) as z:
        text = z.read("BlockAssign_ST15_HI_INCPLACE_CDP.txt").decode("ascii")
    place = {r["BLOCKID"]: r["PLACEFP"] for r in csv.DictReader(io.StringIO(text), delimiter="|")}

    if not (set(blocks) == set(sldl) == set(sldu) == set(zcta)):
        raise SystemExit("Census block files do not list the same blocks")
    rows = []
    for g, b in blocks.items():
        rows.append((g, f"COUNTY-{g[2:5]}", f"HD-{int(sldl[g])}", f"SD-{int(sldu[g])}",
                     zcta[g] or None, place.get(g) or None, int(b["pop20"]), int(b["housing20"]),
                     int(b["aland20"])))
    con.executemany("INSERT INTO block VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    path, _ = saved_file(BLOCKS + "2020_Gaz_place_national.zip")
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    places = []
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        if r["USPS"] == "HI":
            name = r["NAME"]
            short = name.removesuffix(" CDP").removesuffix(" urban county")
            places.append((r["GEOID"][2:], short, name))
    con.executemany("INSERT INTO place VALUES (?, ?, ?)", places)
    print(f"Loaded {len(rows):,} Census blocks and {len(places)} Census places")


def build_overlaps(con) -> None:
    """Population-weighted matching. Shares are of 2020 Census residents."""
    con.execute("""
        INSERT INTO place_district
        SELECT b.place_fp, d.geo_id, sum(b.pop20),
               sum(b.pop20) / any_value(t.pop)
        FROM block b
        CROSS JOIN LATERAL (VALUES (b.house_id), (b.senate_id)) AS d(geo_id)
        JOIN (SELECT place_fp, sum(pop20) AS pop FROM block WHERE place_fp IS NOT NULL
              GROUP BY 1) t USING (place_fp)
        WHERE b.place_fp IS NOT NULL AND t.pop > 0
        GROUP BY b.place_fp, d.geo_id HAVING sum(b.pop20) > 0
    """)
    con.execute("""
        INSERT INTO zcta_district
        SELECT b.zcta, d.geo_id, sum(b.pop20),
               sum(b.pop20) / any_value(t.pop)
        FROM block b
        CROSS JOIN LATERAL (VALUES (b.house_id), (b.senate_id)) AS d(geo_id)
        JOIN (SELECT zcta, sum(pop20) AS pop FROM block WHERE zcta IS NOT NULL GROUP BY 1) t
          USING (zcta)
        WHERE b.zcta IS NOT NULL AND t.pop > 0
        GROUP BY b.zcta, d.geo_id HAVING sum(b.pop20) > 0
    """)
    con.execute(f"""
        INSERT INTO tax_area_district
        WITH bd AS (
            SELECT b.*, d.geo_id FROM block b
            CROSS JOIN LATERAL (VALUES (b.house_id), (b.senate_id)) AS d(geo_id)),
        district_tot AS (SELECT geo_id, sum(pop20) AS pop, sum(aland20) AS land FROM bd GROUP BY 1),
        area_tot AS (
            SELECT z.area_id, sum(b.pop20) AS pop, sum(b.aland20) AS land
            FROM block b JOIN tax_area_zip z ON z.zip = b.zcta GROUP BY 1),
        ov AS (
            SELECT bd.geo_id, z.area_id, sum(bd.pop20) AS pop, sum(bd.aland20) AS land
            FROM bd JOIN tax_area_zip z ON z.zip = bd.zcta GROUP BY 1, 2)
        SELECT ov.geo_id, ov.area_id, ov.pop, ov.pop / dt.pop, ov.pop / nullif(atot.pop, 0),
               ov.land, ov.land / dt.land,
               CASE WHEN ov.pop / dt.pop >= {OVERLAP_THRESHOLD} THEN 'overlaps'
                    ELSE 'touches the edge' END
        FROM ov JOIN district_tot dt USING (geo_id) JOIN area_tot atot USING (area_id)
        WHERE ov.land > 0 OR ov.pop > 0
    """)
    n = con.execute("""SELECT count(*), count(*) FILTER (WHERE relation = 'overlaps')
                       FROM tax_area_district""").fetchone()
    unmatched = con.execute("""
        SELECT count(DISTINCT zcta), coalesce(sum(pop20), 0) FROM block
        WHERE zcta IS NOT NULL AND zcta NOT IN (SELECT zip FROM tax_area_zip)""").fetchone()
    print(f"Tax area overlap (by 2020 residents): {n[0]} district-area pairs ({n[1]} overlap, "
          f"{n[0] - n[1]} touch the edge). {unmatched[0]} ZCTAs ({unmatched[1]:,} residents) "
          "have no ZIP code in DOTAX Table A-14.")
