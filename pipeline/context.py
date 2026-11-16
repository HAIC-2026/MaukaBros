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


# --- DOTAX Tax Credits Claimed by Hawaiʻi Taxpayers, tax year 2023 -----------------------------
# Table A-4: number of credits claimed on individual returns, by tax district (county).
# Table A-7: resident returns (Form N-11) claiming selected credits, by the same DOTAX geographic
# areas as the income report (Table A-13), so they attach to the tax areas already matched to
# districts. These are program-use figures: refundable credits people qualify for but must claim.
CREDITS_PAGE = "https://tax.hawaii.gov/stats/a5_1annual/a5_4credits/"
CREDIT_ROWS = {  # A-4 row label -> (indicator id, label)
    "Earned Income Tax Credit": ("dotax_eitc_claims", "Hawaiʻi earned income tax credit claims"),
    "Refundable Food/Excise Tax Credit": ("dotax_food_excise_claims",
                                          "Refundable food/excise tax credit claims"),
    "Tax Credit for Low-Income Household Renters": ("dotax_renters_claims",
                                                    "Low-income household renters' credit claims"),
}
A4_DISTRICTS = {"STATE": "STATE-15", "OAHU*": "COUNTY-003", "MAUI": "COUNTY-009",
                "HAWAII": "COUNTY-001", "KAUAI": "COUNTY-007"}
A7_COLUMNS = {"Number of Returns": "returns", "Refundable Food/Excise Tax Credit": "food_excise",
              "Tax Credit for Low-Income Household Renters": "renters",
              "Earned Income Tax Credit": "eitc"}
A7_ALIASES = {"puna to kau": "puna-kau"}  # A-7 spelling -> A-13 spelling (both plain)


def plain_name(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", text(s).lower().replace("ʻ", "").replace("'", ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return A7_ALIASES.get(s, s)


def load_dotax_credits(area_ids: dict[str, str]) -> dict:
    """area_ids: plain A-13 area name -> tax_area id (from load_dotax)."""
    path, entry = saved_file("dotax/2023credit_tables.xlsx")
    pdf_path, pdf_entry = saved_file("dotax/2023credit.pdf")

    what = "DOTAX credits table A-4"
    rows = sheet_rows(path, "A-4")
    title = " ".join(text(r[0]) for r in rows[:3] if r and r[0])
    if "BY TYPE OF CREDIT AND TAX DISTRICT - 2023" not in title.upper():
        raise SystemExit(f"{what}: unexpected title {title!r}")
    h = next(i for i, r in enumerate(rows) if r and any(text(v) == "STATE" for v in r))
    cols = {lab: column(rows[h], lab, what) for lab in A4_DISTRICTS}
    facts, indicators = [], []
    for label, (ind_id, ind_label) in CREDIT_ROWS.items():
        r = rows[next(i for i, r in enumerate(rows) if r and text(r[0]) == label)]
        for col_label, geo_id in A4_DISTRICTS.items():
            v = number(r[cols[col_label]], what) if text(r[cols[col_label]]) != "d" else None
            note = ("Includes credits claimed by nonresidents with an out-of-state address "
                    "(DOTAX note)." if geo_id == "COUNTY-003" else
                    "DOTAX tax district 2: Maui and Kalawao counties." if geo_id == "COUNTY-009"
                    else None)
            facts.append((geo_id, ind_id, "dotax_tax_credits", "Tax year 2023", v,
                          "ok" if v is not None else "suppressed", note))
        facts.append(("COUNTY-005", ind_id, "dotax_tax_credits", "Tax year 2023", None,
                      "not_published", "DOTAX does not report Kalawao County separately."))
        indicators.append((ind_id, ind_label, "claims", "Table A-4", entry["url"],
                           f"{title}", None,
                           "Number of claims on individual income tax returns (residents and "
                           "nonresidents), not people or households. A credit must be claimed on a "
                           "tax return to be received."))

    what = "DOTAX credits table A-7"
    rows = sheet_rows(path, "A-7")
    title = " ".join(text(r[0]) for r in rows[:3] if r and r[0])
    if "BY GEOGRAPHICAL AREAS - 2023" not in title.upper():
        raise SystemExit(f"{what}: unexpected title {title!r}")
    h = next(i for i, r in enumerate(rows) if r and any(text(v) == "Number of Returns" for v in r))
    cols = {key: column(rows[h], lab, what) for lab, key in A7_COLUMNS.items()}
    areas, totals, seen = [], {}, set()
    for r in rows[h + 1:]:
        label = text(r[0]) if r else ""
        if not label or label.startswith("Notes") or all(v is None for v in r[1:5]):
            continue
        vals = {k: (number(r[c], what) if text(r[c]) != "d" else None) for k, c in cols.items()}
        if label in ("State Total", "Other/Unknown"):
            totals[label] = vals
            continue
        area_id = area_ids.get(plain_name(label))
        if area_id is None:
            raise SystemExit(f"{what}: area {label!r} does not match any income-report area")
        seen.add(area_id)
        areas.append((area_id, label, vals["returns"], vals["food_excise"], vals["renters"],
                      vals["eitc"]))
    if seen != set(area_ids.values()) or set(totals) != {"State Total", "Other/Unknown"}:
        raise SystemExit(f"{what}: areas missing: {sorted(set(area_ids.values()) - seen)}")
    return {
        "source": ("dotax_tax_credits", "Hawaiʻi Department of Taxation (DOTAX)",
                   "Tax Credits Claimed by Hawaiʻi Taxpayers, Tax Year 2023", CREDITS_PAGE,
                   "Tax year 2023",
                   max(str(entry["downloaded_on"]), str(pdf_entry["downloaded_on"])), None),
        "indicators": indicators,
        "facts": facts,
        "credit_areas": areas,
        "credit_totals": totals,
    }


# --- Census 2024 state legislative district to 2020 ZCTA relationship files (Hawaiʻi) ----------
# One row per district-ZCTA pair, with the land area of the overlap. Rows with no ZCTA are the
# part of the district (mostly water and uninhabited land) outside every ZCTA. Used only to list
# which DOTAX tax areas overlap each district (docs/GEOGRAPHY_METHOD.md); no figure is split.
DISTRICT_ZCTA_FILES = {
    "house": ("census/tab20_sldl202420_zcta520_st15.txt", "SLDL2024_20", "HD"),
    "senate": ("census/tab20_sldu202420_zcta520_st15.txt", "SLDU2024_20", "SD"),
}
# A tax area holding less than this share of a district's 2020 residents is labeled "touches the
# edge" rather than "overlaps" (pipeline/blocks.py). Team decision 2026-11-16. It changes only the
# label, never a figure.
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




MEDQUEST_PAGE = "https://medquest.hawaii.gov/"
MEDQUEST_ISLANDS = {"Oahu": "COUNTY-003", "Hawaii": "COUNTY-001", "Kauai": "COUNTY-007"}
MAUI_COUNTY_ISLANDS = ("Maui", "Molokai", "Lanai")


def load_medquest() -> dict:
    """Med-QUEST (Medicaid) managed-care enrollment by island, Hawaiʻi Medicaid Enrollment Report
    2026 (extract by pipeline/extract_medquest.py). Uses the latest month that ended at least six
    months before the report date: the report says counts change for up to six months."""
    import datetime as dt

    path, entry = saved_file("dhs/medquest_managed_care_by_island_2026.csv")
    pdf_path, pdf_entry = saved_file("dhs/Website Enrollment Report 2026 20261106.pdf")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    report = dt.datetime.strptime(rows[0]["report_date"], "%m/%d/%Y").date()
    k = report.year * 12 + report.month - 1 - 6                 # six months before the report date
    six_months_back = dt.date(k // 12, k % 12 + 1, 1)

    def month_end(m: str) -> dt.date:
        first = dt.datetime.strptime(m, "%b-%y").date()
        nxt = first.year * 12 + first.month                       # first day of the next month
        return dt.date(nxt // 12, nxt % 12 + 1, 1) - dt.timedelta(days=1)

    cutoff = six_months_back.replace(day=min(report.day, 28))
    settled = [m for m in dict.fromkeys(r["month"] for r in rows) if month_end(m) <= cutoff]
    if not settled:
        raise SystemExit("Med-QUEST report: no month is six months old yet")
    month = settled[-1]
    v = {r["area"]: int(r["managed_care_enrollment"]) for r in rows if r["month"] == month}
    label = dt.datetime.strptime(month, "%b-%y").strftime("%B %Y")
    facts = [(geo, "medquest_managed_care", "dhs_medquest", label, float(v[isl]), "ok",
              f"Reported by Med-QUEST for the island of {isl.replace('Oahu', 'Oʻahu').replace('Hawaii', 'Hawaiʻi').replace('Kauai', 'Kauaʻi')}.")
             for isl, geo in MEDQUEST_ISLANDS.items()]
    facts.append(("COUNTY-009", "medquest_managed_care", "dhs_medquest", label,
                  float(sum(v[i] for i in MAUI_COUNTY_ISLANDS)), "ok",
                  "Sum of the Med-QUEST figures for Maui, Molokaʻi and Lānaʻi (calculated)."))
    facts.append(("STATE-15", "medquest_managed_care", "dhs_medquest", label, float(v["TOTAL"]),
                  "ok", "Report total, Medicaid managed care."))
    facts.append(("COUNTY-005", "medquest_managed_care", "dhs_medquest", label, None,
                  "not_published", "Med-QUEST does not report Kalawao County separately."))
    return {
        "source": ("dhs_medquest", "Hawaiʻi Department of Human Services, Med-QUEST Division",
                   "Hawaiʻi Medicaid Enrollment Report (2026), Managed Care By Island",
                   MEDQUEST_PAGE, label, str(pdf_entry["downloaded_on"]),
                   f"Report dated {report:%B} {report.day}, {report.year}"),
        "indicators": [("medquest_managed_care", "Med-QUEST (Medicaid) managed-care members",
                        "people", "Managed Care By Island", pdf_entry["url"],
                        "Hawaii Medicaid Enrollment Report (2026)", None,
                        "Program records: people with a Med-QUEST health plan for at least part of "
                        "the month. Excludes about 9,000 Medicaid-only members (fee-for-service and "
                        "Medicare Savings). The report says counts change for up to six months, so "
                        "the latest month at least six months old is used.")],
        "facts": facts,
    }


def load_reapportionment() -> dict:
    """Each district's permanent-resident population from the 2021 Reapportionment Commission
    Final Report, Tables 9-10 (extract made by pipeline/extract_reapportionment.py)."""
    path, entry = saved_file("elections/reapportionment_2021_district_population.csv")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = [(f"{'HD' if r['chamber'] == 'house' else 'SD'}-{int(r['district'])}",
                 int(r["permanent_resident_population"]), int(r["statewide_target"]),
                 int(r["report_pdf_page"])) for r in csv.DictReader(fh)]
    return {"source": ("reapportionment_2021", "State of Hawaiʻi 2021 Reapportionment Commission "
                       "(Office of Elections)", "2021 Reapportionment Commission Final Report and "
                       "Reapportionment Plan (February 25, 2022), Tables 9 and 10",
                       entry["url"], "2020 Census base", str(entry["downloaded_on"]), None),
            "district_plan": rows}


LOADERS = {"bea_cainc1": load_bea, "bls_laus": load_bls, "dbedt_databook": load_data_book,
           "dotax_individual_income": load_dotax, "dhs_medquest": load_medquest}


def load_all() -> list[dict]:
    out = []
    for source_id, loader in LOADERS.items():
        try:
            out.append(loader())
        except MissingFile as exc:
            print(f"Skipping {source_id}: {exc}")
            continue
        if source_id == "dotax_individual_income":
            ids = {plain_name(published): area_id
                   for area_id, _, published, *_ in out[-1]["tax_areas"]}
            try:
                out.append(load_dotax_credits(ids))
            except MissingFile as exc:
                print(f"Skipping dotax_tax_credits: {exc}")
    try:
        out.append(load_reapportionment())
    except MissingFile as exc:
        print(f"Skipping reapportionment_2021: {exc}")
    pending = sorted({e["source_id"] for e in manifest() if e.get("status") == "needed"})
    if pending:
        print(f"Not downloaded yet (see pipeline/raw/manifest.yaml): {', '.join(pending)}")
    return out
