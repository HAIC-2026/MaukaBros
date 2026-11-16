"""Make Hawaiʻi-only extracts from large national Census block files. No network access.

    python pipeline/extract_census_blocks.py DOWNLOAD_DIR

DOWNLOAD_DIR holds the original files, each downloaded once from www2.census.gov (URLs and
fingerprints below and in pipeline/raw/manifest.yaml). The originals are too large to keep in the
repository (the block-to-ZCTA file is 1 GB), so this script checks each original's SHA-256
fingerprint, keeps only Hawaiʻi's rows (block ids starting with state code 15), and writes them to
pipeline/raw/census/blocks/. Anyone can re-download an original, check its fingerprint and
re-create exactly the same extract.

The two small originals (the 2020 block assignment file and the place gazetteer) are copied whole.
"""

import csv
import hashlib
import io
import shutil
import sys
import zipfile
from pathlib import Path

import shapefile  # pyshp: reads the TIGER attribute table (.dbf)

HERE = Path(__file__).parent
OUT = HERE / "raw" / "census" / "blocks"

ORIGINALS = {
    "sldl24.zip": "0d916eb6f901a891014a881ac951de40148f2ce391a275fe86ff172d47cada13",
    "sldu24.zip": "52e4d2b1ebdf8470d906c8de9b2824fa86f936e8c016ce9b5598fb2b7271b55d",
    "tl_2020_15_tabblock20.zip": "c29683118cd7eada4bd4672e30de6bdd5638a752c1d0f7f795b4dd580c02259e",
    "tab20_zcta520_tabblock20_natl.txt":
        "7f077624d252fc1cc5a2d1100be07cfe038ffc152bfe193561d068b4def6bbbf",
    "BlockAssign_ST15_HI.zip": "99ff6595ad6566804cc4682c9e73b9d854ae127154bffb9b0f2e6e97a7fa8147",
    "2020_Gaz_place_national.zip":
        "6e5745b3e1adf7a1e024a988301d484697e2a0f25b3cf10114eef676f09d5c18",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(name: str, header: list[str], rows) -> int:
    n = 0
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)
            n += 1
    print(f"  {name}: {n:,} rows")
    return n


def bef_rows(zip_path: Path, member: str):
    """2024 Block Equivalency File (national): GEOID,SLDxST. Hawaiʻi rows only."""
    with zipfile.ZipFile(zip_path) as z, z.open(member) as fh:
        text = io.TextIOWrapper(fh, encoding="ascii", newline="")
        reader = csv.reader(text)
        header = next(reader)
        if header[0] != "GEOID":
            raise SystemExit(f"{member}: unexpected header {header}")
        for geoid, district in reader:
            if geoid.startswith("15"):
                yield geoid, district


def main(src: Path) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for name, expected in ORIGINALS.items():
        path = src / name
        if not path.exists():
            raise SystemExit(f"Missing {path}. Download it first (see pipeline/raw/manifest.yaml).")
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(f"{name}: fingerprint {actual} does not match {expected}. "
                             "The Census Bureau may have replaced the file; review before using.")
    OUT.mkdir(parents=True, exist_ok=True)

    print("2024 state legislative district block equivalency files (Hawaiʻi rows):")
    write_csv("hi_block_sldl24.csv", ["block_geoid", "sldl"],
              bef_rows(src / "sldl24.zip", "NationalSLDL24.txt"))
    write_csv("hi_block_sldu24.csv", ["block_geoid", "sldu"],
              bef_rows(src / "sldu24.zip", "NationalSLDU24.txt"))

    print("TIGER/Line 2020 tabulation blocks, Hawaiʻi (attribute table only):")
    with zipfile.ZipFile(src / "tl_2020_15_tabblock20.zip") as z:
        dbf = io.BytesIO(z.read("tl_2020_15_tabblock20.dbf"))
    rdr = shapefile.Reader(dbf=dbf)
    names = [f[0] for f in rdr.fields[1:]]
    keep = ["GEOID20", "POP20", "HOUSING20", "ALAND20", "AWATER20", "INTPTLAT20", "INTPTLON20"]
    missing = [k for k in keep if k not in names]
    if missing:
        raise SystemExit(f"TIGER blocks: missing fields {missing}")
    idx = [names.index(k) for k in keep]
    write_csv("hi_blocks_2020.csv", [k.lower() for k in keep],
              ([rec[i] for i in idx] for rec in rdr.iterRecords()))

    print("2020 ZCTA to 2020 tabulation block relationship file (Hawaiʻi blocks):")
    def zcta_rows():
        with (src / "tab20_zcta520_tabblock20_natl.txt").open(encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter="|")
            for r in reader:
                if r["GEOID_TABBLOCK_20"].startswith("15"):
                    yield (r["GEOID_TABBLOCK_20"], r["GEOID_ZCTA5_20"], r["AREALAND_PART"])
    write_csv("hi_block_zcta520.csv", ["block_geoid", "zcta", "arealand_part"], zcta_rows())

    print("Copied whole:")
    for name in ("BlockAssign_ST15_HI.zip", "2020_Gaz_place_national.zip"):
        shutil.copyfile(src / name, OUT / name)
        print(f"  {name}")

    print("\nExtract fingerprints (paste into pipeline/raw/manifest.yaml):")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name}  {sha256(p)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
