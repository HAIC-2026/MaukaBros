"""County and state context figures from sources other than the ACS.

These sources publish for counties (or islands) and the state only, never for legislative
districts, so their figures are stored separately (tables context_indicator / context_fact) and
shown as context for a district's county, never as a figure for the district itself.

Every loader reads a saved file listed in pipeline/raw/manifest.yaml. Nothing is downloaded here.
A source whose file has not been downloaded yet is skipped, with a message.

Spreadsheet loaders find rows and columns by the labels printed in the file (never by position)
and stop with an error if a label is missing, so a re-laid-out file cannot be misread silently.
"""

import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RAW = HERE / "raw"


class MissingFile(Exception):
    pass


def manifest() -> list[dict]:
    return yaml.safe_load((RAW / "manifest.yaml").read_text(encoding="utf-8"))["files"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def saved_file(rel_path: str) -> tuple[Path, dict]:
    """The saved file and its manifest entry. Refuses a file that does not match the manifest."""
    entry = next((e for e in manifest() if e["path"] == rel_path), None)
    if entry is None:
        raise SystemExit(f"{rel_path} is not listed in pipeline/raw/manifest.yaml")
    path = RAW / rel_path
    if not path.exists():
        raise MissingFile(f"{rel_path} not downloaded yet ({entry['how']})")
    actual = sha256(path)
    if not entry.get("sha256") or not entry.get("downloaded_on"):
        raise SystemExit(f"{rel_path} is present but manifest.yaml has no sha256/downloaded_on. "
                         f"Record the download date and who downloaded it, and sha256: {actual}")
    if actual != entry["sha256"]:
        raise SystemExit(f"{rel_path} does not match manifest.yaml (sha256 {actual}). If it was "
                         "re-downloaded on purpose, update downloaded_on and sha256 there.")
    return path, entry


def sheet_rows(path: Path, sheet: str) -> list[list]:
    import openpyxl  # only needed for the spreadsheet sources

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if sheet not in wb.sheetnames:
        raise SystemExit(f"{path.name}: sheet {sheet!r} not found")
    rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
    wb.close()
    return rows


def text(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def find_row(rows: list[list], first_cell: str, what: str) -> int:
    for i, r in enumerate(rows):
        if r and text(r[0]) == first_cell:
            return i
    raise SystemExit(f"{what}: no row starting with {first_cell!r}")


def column(header: list, label: str, what: str) -> int:
    for j, v in enumerate(header):
        if text(v) == label:
            return j
    raise SystemExit(f"{what}: no column {label!r} in {[text(v) for v in header if v]}")


def number(v, what: str) -> float | None:
    """A published number, or None for the publisher's 'not available' codes like (NA)."""
    if isinstance(v, (int, float)):
        return float(v)
    if text(v) in ("(NA)", "NA", "(D)", "-", "s"):
        return None
    raise SystemExit(f"{what}: unexpected cell value {v!r}")


def data_book_title(rows: list[list]) -> str:
    """Title lines at the top of a Data Book sheet, up to the bracketed note or the header."""
    parts = []
    for r in rows[:4]:
        t = text(r[0])
        if not t or t.startswith("[") or t in ("Year",) or t.startswith("Date"):
            break
        parts.append(t)
    return " ".join(parts)


def data_book_notes(rows: list[list], last_data_row: int) -> tuple[str, str]:
    """(footnotes, source) printed below the data. Each sentence is split over several cells in
    the file, so lines are joined: footnotes start with "[a]"/"[b]", the source with "Source:"."""
    lines = [text(r[0]) for r in rows[last_data_row + 1:] if r and text(r[0])]
    at = next((i for i, ln in enumerate(lines) if ln.startswith("Source")), len(lines))
    return " ".join(lines[:at]), " ".join(lines[at:])


# --- BEA CAINC1: personal income, per capita personal income ----------------------------------
# BEA GeoFIPS -> our geography ids. BEA publishes Maui and Kalawao combined (15901, footnote:
# "Kalawao County, Hawaii is combined with Maui County. Separate estimates for the jurisdictions
# making up the combination areas are not available."), so that row is attached to Maui County
# with a note, and Kalawao (COUNTY-005) is recorded as not published.
BEA_GEOS = {
    "15000": ("STATE-15", None),
    "15001": ("COUNTY-001", None),
    "15003": ("COUNTY-003", None),
    "15007": ("COUNTY-007", None),
    "15901": ("COUNTY-009", "BEA figure for Maui and Kalawao counties combined; BEA does not "
                            "publish them separately."),
}
# CAINC1 LineCode -> (indicator id, label, unit, multiplier, shown). Only per capita income is
# shown (team decision 2026-11-16: few, well-chosen figures); personal income and population are
# read so validation can check per capita = income / population and counties add to the state.
BEA_LINES = {
    "1": ("personal_income", "Personal income", "dollars", 1000, False),  # in thousands
    "2": ("bea_population", "Population (BEA midyear estimate)", "people", 1, False),
    "3": ("per_capita_personal_income", "Personal income per person", "dollars", 1, True),
}
BEA_YEAR = "2024"


def load_bea() -> dict:
    path, entry = saved_file("bea/CAINC1.zip")
    with zipfile.ZipFile(path) as z:
        raw = z.read("CAINC1_HI_1969_2024.csv").decode("latin-1")
    lines = raw.splitlines()
    vintage = next((ln.strip('" ') for ln in lines if ln.startswith('"Last updated')), None)
    data = "\n".join(ln for ln in lines if ln.startswith(("GeoFIPS", ' "')))
    # Data rows start with a space before the quoted FIPS, so skip it or quoted names split.
    rows = list(csv.DictReader(io.StringIO(data), skipinitialspace=True))

    facts, check, seen = [], {}, set()
    shown = {i for i, *_, s in BEA_LINES.values() if s}
    for row in rows:
        fips = row["GeoFIPS"].strip().strip('"')
        line = row["LineCode"].strip()
        if fips not in BEA_GEOS or line not in BEA_LINES:
            continue
        geo_id, note = BEA_GEOS[fips]
        ind_id, _, _, mult, _ = BEA_LINES[line]
        cell = row[BEA_YEAR].strip()
        try:
            value, status = float(cell) * mult, "ok"
        except ValueError:  # BEA marks unpublished cells with codes such as (D) or (NA)
            value, status, note = None, "suppressed", f"BEA code {cell}"
        check[(geo_id, ind_id)] = value
        if ind_id in shown:
            facts.append((geo_id, ind_id, "bea_cainc1", BEA_YEAR, value, status, note))
        seen.add((geo_id, ind_id))
    expected = {(g, i) for g, _ in BEA_GEOS.values() for i, *_ in BEA_LINES.values()}
    if seen != expected:
        raise SystemExit(f"BEA file is missing expected rows: {sorted(expected - seen)}")
    for ind_id in shown:
        facts.append(("COUNTY-005", ind_id, "bea_cainc1", BEA_YEAR, None, "not_published",
                      "Included in the Maui County figure; BEA does not publish Kalawao County "
                      "separately."))

    return {
        "source": ("bea_cainc1", "U.S. Bureau of Economic Analysis",
                   "CAINC1 County personal income summary: personal income, population, per "
                   "capita personal income", entry["url"], BEA_YEAR, entry["downloaded_on"],
                   vintage),
        "indicators": [(i, label, unit, "CAINC1", entry["url"], None, None, None)
                       for i, label, unit, _, s in BEA_LINES.values() if s],
        "facts": facts,
        "check": check,  # every line read, for validation only (not stored)
    }


# --- BLS LAUS: labor force and unemployment by county ------------------------------------------
BLS_COUNTIES = {"001": "COUNTY-001", "003": "COUNTY-003", "007": "COUNTY-007",
                "009": "COUNTY-009"}
BLS_COLUMNS = {  # header label in the file -> (indicator id, label, unit)
    "Labor Force": ("bls_labor_force", "Civilian labor force", "people"),
    "Unemployed": ("bls_unemployed", "Unemployed residents", "people"),
    "Unemployment Rate (%)": ("bls_unemployment_rate", "Unemployment rate", "percent"),
}
# Only the rate is shown (team decision 2026-11-16); the counts are read so validation can check
# rate = unemployed / labor force.
BLS_SHOWN = {"bls_unemployment_rate"}


def load_bls() -> dict:
    path, entry = saved_file("bls/laucnty25.xlsx")
    rows = sheet_rows(path, "laucnty25")
    what = "BLS laucnty25.xlsx"
    title = text(rows[0][0])
    h = find_row(rows, "LAUS Code", what)
    header = rows[h]
    c_state = column(header, "State FIPS Code", what)
    c_county = column(header, "County FIPS Code", what)
    c_year = column(header, "Year", what)
    cols = {lab: column(header, lab, what) for lab in BLS_COLUMNS}
    # The asterisk footnote explains the 11-month average; it must exist and is shown with every
    # value (it is the reason these figures are not comparable with other years).
    footnote = next((text(r[0]) for r in rows[h + 1:] if r and text(r[0]).startswith("*")), None)
    if not title.endswith("*") or not footnote:
        raise SystemExit(f"{what}: expected the title asterisk and its footnote")
    release = next((text(r[0]) for r in rows[-3:] if r and re.match(r"^[A-Z][a-z]+ \d", text(r[0]))),
                   None)

    facts, check, period = [], {}, None
    for r in rows[h + 1:]:
        if not r or text(r[c_state]) != "15":
            continue
        geo_id = BLS_COUNTIES.get(text(r[c_county]))
        if geo_id is None:
            raise SystemExit(f"{what}: unexpected Hawaii county {r[c_county]!r}")
        period = text(r[c_year])
        for lab, (ind_id, *_) in BLS_COLUMNS.items():
            v = number(r[cols[lab]], what)
            check[(geo_id, ind_id)] = v
            if ind_id in BLS_SHOWN:
                facts.append((geo_id, ind_id, "bls_laus", period, v, "ok" if v is not None
                              else "suppressed", None))
    if len(check) != len(BLS_COUNTIES) * len(BLS_COLUMNS):
        raise SystemExit(f"{what}: expected 4 Hawaii counties, got {len(check) // 3}")
    for ind_id in BLS_SHOWN:
        facts.append(("COUNTY-005", ind_id, "bls_laus", period, None, "not_published",
                      "Kalawao County is not listed in this BLS file."))
        facts.append(("STATE-15", ind_id, "bls_laus", period, None, "not_published",
                      "This BLS file has counties only; BLS publishes the statewide figure "
                      "separately."))
    # Keep BLS's own words, minus the sentences about Puerto Rico (not relevant here).
    kept = [x for x in re.split(r"(?<=\.) ", footnote.lstrip("*"))
            if "Puerto Rico's" not in x and "for Puerto Rico" not in x]
    caveat = f"11-month average, not a full year. BLS: \"{' '.join(kept)}\""
    return {
        "source": ("bls_laus", "U.S. Bureau of Labor Statistics",
                   "Local Area Unemployment Statistics (LAUS), labor force data by county",
                   entry["url"], period, entry["downloaded_on"],
                   f"File dated {release}" if release else None),
        "indicators": [(ind_id, label, unit, "laucnty25", entry["url"], title, None, caveat)
                       for ind_id, label, unit in BLS_COLUMNS.values() if ind_id in BLS_SHOWN],
        "facts": facts,
        "check": check,  # every column read, for validation only (not stored)
    }


# --- DBEDT State of Hawaii Data Book 2025 ------------------------------------------------------
DATA_BOOK_PAGE = "https://dbedt.hawaii.gov/economic/databook/db2025/"

# SNAP (the Data Book still calls it the Food Stamp Program), Hawaii DHS figures, by island.
# Column label in the file -> (geo id, note). Oʻahu, Hawaiʻi and Kauaʻi are reported as islands;
# they are attached to the county of the same name with a note saying how DHS reported them.
SNAP_COLUMNS = {
    "Oahu": ("COUNTY-003", "Reported by DHS for the island of Oʻahu."),
    "Hawaii": ("COUNTY-001", "Reported by DHS for Hawaiʻi Island."),
    "Kauai": ("COUNTY-007", "Reported by DHS for Kauaʻi."),
    "Maui County total": ("COUNTY-009", "DHS \"Maui County total\" (Maui, Molokaʻi and Lānaʻi)."),
}
SNAP_TABLES = {  # sheet -> (indicator id, label, unit, state column label)
    "11.03": ("snap_cases_monthly", "SNAP cases (households), average per month", "households",
              "State"),
    "11.04": ("snap_people_monthly", "People served by SNAP, average per month", "people",
              "State [a]"),
}
# Not used (team decision 2026-11-16): 11.05 benefits paid (nothing on the need side to compare
# it with) and 1.06 resident population (a republished Census estimate; the ACS county figure is
# already on the page).
SNAP_YEAR = 2025


def load_data_book() -> dict:
    facts, indicators, entries = [], [], []

    # Tables 11.03-11.05: SNAP participation and benefits (program uptake)
    path, entry = saved_file("dbedt/DB2025_section11.xlsx")
    entries.append(entry)
    for sheet, (ind_id, label, unit, state_col) in SNAP_TABLES.items():
        what = f"Data Book table {sheet}"
        rows = sheet_rows(path, sheet)
        title = data_book_title(rows)
        if "FOOD STAMP" not in title.upper():
            raise SystemExit(f"{what}: unexpected title {title!r}")
        h = find_row(rows, "Year", what)
        header = rows[h]
        i = find_row(rows, str(SNAP_YEAR), what)
        r = rows[i]
        footnotes, source_text = data_book_notes(rows, i)
        bracket = next((text(x[0]) for x in rows[:4] if text(x[0]).startswith("[")), "")
        if "Fiscal year ending June 30" not in bracket:
            raise SystemExit(f"{what}: expected the fiscal-year note, got {bracket!r}")
        period = f"FY{SNAP_YEAR} (July {SNAP_YEAR - 1} to June {SNAP_YEAR})"
        for col, (geo_id, note) in [*SNAP_COLUMNS.items(), (state_col, ("STATE-15", None))]:
            v = number(r[column(header, col, what)], what)
            facts.append((geo_id, ind_id, "dbedt_databook", period, v,
                          "ok" if v is not None else "suppressed", note))
        facts.append(("COUNTY-005", ind_id, "dbedt_databook", period, None, "not_published",
                      "DHS does not report Kalawao County separately in this table."))
        indicators.append((ind_id, label, unit, f"Data Book {sheet}", entry["url"], title,
                           source_text, footnotes or None))

    latest = max(e["downloaded_on"] for e in entries)
    return {
        "source": ("dbedt_databook", "Hawaiʻi Department of Business, Economic Development & "
                   "Tourism (DBEDT), Research & Economic Analysis Division",
                   "The 2025 State of Hawaii Data Book", DATA_BOOK_PAGE, "2025 edition",
                   str(latest), "58th edition"),
        "indicators": indicators,
        "facts": facts,
    }


# --- DOTAX Individual Income Tax Statistics, tax year 2023 -------------------------------------
# Table A-13: resident returns by DOTAX geographic area (with county and state totals).
# Table A-14: the same by ZIP code, and the area each ZIP code belongs to. The report
# (dotax/2023indinc.pdf) does not define the areas; A-14 is the only record of which ZIP codes
# make up each area. Only the number of returns and the median Hawaiʻi AGI are kept.
DOTAX_PAGE = "https://tax.hawaii.gov/stats/a5_1annual/a5_5ind_inc/"
DOTAX_YEAR = "Tax year 2023"
DOTAX_COUNTY_TOTALS = {  # total row label in A-13 -> geography id
    "O'AHU TOTAL": "COUNTY-003",
    "MAUI COUNTY TOTAL": "COUNTY-009",
    "HAWAI'I COUNTY TOTAL": "COUNTY-001",
    "KAUA'I COUNTY TOTAL": "COUNTY-007",
}
DOTAX_STATE = "TOTAL - HAWAI'I ADDRESSES"
DOTAX_UNPLACED = "Other/Unidentified"
DOTAX_ALL = "TOTAL - ALL RES. RETURNS"


def okina(name: str) -> str:
    """DOTAX prints the ʻokina as a straight apostrophe; every apostrophe in its area names is
    an ʻokina (e.g. O'ahu, Wai'anae, Puna-Ka'ū). Shown with the ʻokina; the printed name is kept."""
    return name.replace("'", "ʻ")


def area_id(name: str) -> str:
    return "TAX-" + re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


def dotax_columns(rows: list[list], h: int, what: str, first: str) -> tuple[int, int, int]:
    """(label, returns, median AGI) columns. The header spans three rows: 'Number of Returns'
    on the first, and the AGI 'Median ($)' is the first 'Median ($)' on the second."""
    c_label = column(rows[h], first, what)
    c_returns = column(rows[h], "Number of Returns", what)
    c_agi = column(rows[h], "Hawai'i AGI*", what)
    c_median = column(rows[h + 1], "Median ($)", what)
    if not c_agi < c_median < column(rows[h], "Tax Liability", what):
        raise SystemExit(f"{what}: 'Median ($)' is not under 'Hawai'i AGI*'")
    return c_label, c_returns, c_median


def load_dotax() -> dict:
    path, entry = saved_file("dotax/2023indinc_tables.xlsx")
    pdf_path, pdf_entry = saved_file("dotax/2023indinc.pdf")  # method notes; must be present

    # A-13: areas in county order, each county closed by its total row.
    what = "DOTAX table A-13"
    rows = sheet_rows(path, "A13")
    title = text(rows[1][0])
    if "BY GEOGRAPHIC AREA" not in title or "2023" not in title:
        raise SystemExit(f"{what}: unexpected title {title!r}")
    h = find_row(rows, "GEOGRAPHIC AREA", what)
    c_label, c_returns, c_median = dotax_columns(rows, h, what, "GEOGRAPHIC AREA")
    areas, pending, totals = [], [], {}
    for r in rows[h + 3:]:
        label = text(r[c_label])
        if not label or label.startswith("*"):
            continue
        returns, median = number(r[c_returns], what), number(r[c_median], what)
        if label in DOTAX_COUNTY_TOTALS:
            county = DOTAX_COUNTY_TOTALS[label]
            areas += [(area_id(n), okina(n), n, county, ret, med) for n, ret, med in pending]
            pending = []
            totals[county] = (returns, median)
        elif label in (DOTAX_STATE, DOTAX_UNPLACED, DOTAX_ALL):
            totals[label] = (returns, median)
        else:
            pending.append((label, returns, median))
    missing = set(DOTAX_COUNTY_TOTALS.values()) | {DOTAX_STATE, DOTAX_UNPLACED, DOTAX_ALL}
    if pending or missing - set(totals):
        raise SystemExit(f"{what}: unexpected layout (rows after the last total: {pending}, "
                         f"missing totals: {sorted(missing - set(totals))})")

    # A-14 (four sheets): ZIP code -> area. Rows without a ZIP are island/county headings.
    zips = []
    known = {a[2] for a in areas}
    for sheet in ("A14-1", "A14-2", "A14-3", "A14-4"):
        what = f"DOTAX table A-14 ({sheet})"
        rows = sheet_rows(path, sheet)
        h = find_row(rows, "ZIP CODE", what)
        c_zip, c_returns, c_median = dotax_columns(rows, h, what, "ZIP CODE")
        c_area = column(rows[h], "GEOGRAPHIC AREA", what)
        for r in rows[h + 3:]:
            if not isinstance(r[c_zip], (int, float)):
                continue
            name = text(r[c_area])
            if name not in known:
                raise SystemExit(f"{what}: ZIP {r[c_zip]} has unknown area {name!r}")
            zips.append((f"{int(r[c_zip]):05d}", area_id(name), number(r[c_returns], what),
                         number(r[c_median], what)))

    unplaced = totals[DOTAX_UNPLACED][0]
    caveat = ("Median Hawaiʻi adjusted gross income (AGI) per resident income tax return, not per "
              "household: a joint return covers a married couple, and some people with low "
              "incomes do not file. Counts only returns with a Hawaiʻi ZIP code "
              f"({unplaced:,.0f} returns with out-of-state or unidentified ZIP codes are not "
              "placed in any area). Figures are as filed, before audits.")
    facts = [(g, "dotax_median_agi", "dotax_individual_income", DOTAX_YEAR, med,
              "ok" if med is not None else "suppressed",
              "DOTAX groups Maui and Kalawao counties together (tax district 2)."
              if g == "COUNTY-009" else None)
             for g, (_, med) in totals.items() if g.startswith("COUNTY")]
    facts.append(("STATE-15", "dotax_median_agi", "dotax_individual_income", DOTAX_YEAR,
                  totals[DOTAX_STATE][1], "ok",
                  "Returns with a Hawaiʻi ZIP code (DOTAX \"Total - Hawaiʻi addresses\")."))
    facts.append(("COUNTY-005", "dotax_median_agi", "dotax_individual_income", DOTAX_YEAR, None,
                  "not_published", "DOTAX does not report Kalawao County separately."))
    return {
        "source": ("dotax_individual_income", "Hawaiʻi Department of Taxation (DOTAX)",
                   "Hawaii Individual Income Tax Statistics, Tax Year 2023", DOTAX_PAGE,
                   DOTAX_YEAR, max(str(entry["downloaded_on"]), str(pdf_entry["downloaded_on"])),
                   "Report dated October 2026"),
        "indicators": [("dotax_median_agi", "Median income on resident tax returns",
                        "dollars", "Table A-13", entry["url"], title, None, caveat)],
        "facts": facts,
        "check": totals,  # returns by county and state, for validation only
        "tax_areas": areas,
        "tax_area_zips": zips,
    }


# --- Census 2024 state legislative district to 2020 ZCTA relationship files (Hawaiʻi) ----------
# One row per district-ZCTA pair, with the land area of the overlap. Rows with no ZCTA are the
# part of the district (mostly water and uninhabited land) outside every ZCTA. Used only to list
# which DOTAX tax areas overlap each district (docs/GEOGRAPHY_METHOD.md); no figure is split.
DISTRICT_ZCTA_FILES = {
    "house": ("census/tab20_sldl202420_zcta520_st15.txt", "SLDL2024_20", "HD"),
    "senate": ("census/tab20_sldu202420_zcta520_st15.txt", "SLDU2024_20", "SD"),
}
# A tax area covering less than this share of a district's land is labeled "touches the edge"
# rather than "overlaps". Team decision 2026-11-16. It changes only the label, never a figure.
OVERLAP_THRESHOLD = 0.01


def load_district_zcta() -> list[tuple]:
    """(geo_id, zcta or None, overlap land m², district land m², ZCTA land m² or None)."""
    out = []
    for chamber, (rel, suffix, prefix) in DISTRICT_ZCTA_FILES.items():
        path, _ = saved_file(rel)
        what = f"Census relationship file {path.name}"
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="|"))
        need = [f"GEOID_{suffix}", f"AREALAND_{suffix}", "GEOID_ZCTA5_20", "AREALAND_ZCTA5_20",
                "AREALAND_PART"]
        if not rows or any(c not in rows[0] for c in need):
            raise SystemExit(f"{what}: expected columns {need}")
        for r in rows:
            geoid = r[f"GEOID_{suffix}"]
            if not geoid.startswith("15"):
                raise SystemExit(f"{what}: unexpected district {geoid!r}")
            zcta = r["GEOID_ZCTA5_20"] or None
            out.append((f"{prefix}-{int(geoid[2:])}", zcta, float(r["AREALAND_PART"]),
                        float(r[f"AREALAND_{suffix}"]),
                        float(r["AREALAND_ZCTA5_20"]) if zcta else None))
    return out


LOADERS = {"bea_cainc1": load_bea, "bls_laus": load_bls, "dbedt_databook": load_data_book,
           "dotax_individual_income": load_dotax}


def load_all() -> list[dict]:
    out = []
    for source_id, loader in LOADERS.items():
        try:
            out.append(loader())
        except MissingFile as exc:
            print(f"Skipping {source_id}: {exc}")
    pending = sorted({e["source_id"] for e in manifest() if e.get("status") == "needed"})
    if pending:
        print(f"Not downloaded yet (see pipeline/raw/manifest.yaml): {', '.join(pending)}")
    return out
