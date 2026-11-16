# Saved source files

The pipeline reads these local files. It does not download anything while building, and no
script scans a website. Do not edit them by hand; replace them from the source and record the date.

**`manifest.yaml` lists every file** with its URL, how it was downloaded, the date, who
downloaded it and its SHA-256 fingerprint. `pipeline/build.py` refuses a file that does not match
its fingerprint, and skips (with a message) any file marked `status: needed`.

## Folders

| Folder | Source | How it got here | Read by the pipeline |
|---|---|---|---|
| `acs/` | U.S. Census Bureau ACS | `pipeline/fetch_acs.py` (Census API) | yes |
| `bea/` | U.S. Bureau of Economic Analysis | one download | yes (CAINC1) |
| `bls/` | U.S. Bureau of Labor Statistics | by hand in a browser | yes (laucnty25) |
| `dbedt/` | DBEDT, State of Hawaii Data Book 2025, all 24 sections | by hand in a browser | section 11 only (tables 11.03, 11.04) |
| `dotax/` | Hawaiʻi Department of Taxation, Individual Income Tax Statistics 2023 (tables and report) | by hand in a browser | yes (tables A-13, A-14; the PDF is for reference) |
| `programs/` | Official program pages and documents (SNAP, Med-QUEST, DOTAX credits, WIC, aging office, HHS poverty guidelines, SSA SSI), saved by hand; web pages saved with the browser's Print to PDF | by hand in a browser | facts quoted in `pipeline/programs.yaml`, checked by validation group P |
| `dhs/` | Med-QUEST Hawaiʻi Medicaid Enrollment Reports 2025 and 2026, and the extract of the 2026 island table | by hand in a browser | the extract (`pipeline/extract_medquest.py`) |
| `elections/` | 2021 Reapportionment Commission Final Report (400 MB, **not in Git**: re-download it by hand to re-run `pipeline/extract_reapportionment.py`) and the committed extract of Tables 9-10 | by hand in a browser | the extract only |
| `census/` | Census 2024 legislative district to ZCTA relationship files, Hawaiʻi | one download each | yes (cross-check of the block matching) |
| `census/blocks/` | Census 2020 blocks: district equivalency, populations, block-to-ZCTA, places. Hawaiʻi extracts of national files, made by `pipeline/extract_census_blocks.py`; each records its original's URL and fingerprint | one download each | yes (`pipeline/blocks.py`) |
| `opsd/` | State district boundaries | by hand in a browser | yes (`pipeline/boundaries.py`) |

What each Data Book table contains: `docs/data_book_2025_tables.csv`. What is used and why:
`docs/DATA_SOURCES.md`.

## Adding or replacing a file

hawaii.gov files must be downloaded by a person in a browser (the Hawaiʻi.gov Terms of Use
prohibit automated access). BLS blocks automated downloads too. Other federal files (BEA, Census
relationship files) may be downloaded once with a single request; the file is then stored here
and never fetched again by the pipeline.

1. Open the page in `manifest.yaml` (`how`) and save the file at its `path`.
2. In `manifest.yaml`, set `status: present`, `downloaded_on` (date) and `downloaded_by`.
3. Run `python pipeline/build.py`. If the fingerprint is missing or different it stops and prints
   the file's `sha256`; paste it into the manifest and run it again.
4. Run `python validation/validate.py`.

All listed files are present.

## bls/laucnty25.xlsx: county labor force (downloaded by hand)

- Title: "Labor Force Data by County, 2025 11-Month and Annual Averages*". File dated May 19, 2026.
- BLS footnote: every county outside Puerto Rico has an 11-month average that excludes October
  2025 (not collected during the federal shutdown); "not fully comparable to annual averages for
  other years". The app shows this with every BLS figure.
- No state total in this file, and no Kalawao County row.

## dbedt/: State of Hawaii Data Book 2025 (downloaded by hand)

- Tables 11.03-11.04: SNAP ("Food Stamp Program") average monthly cases and people served by
  island, fiscal year ending June 30, 2025. Original data: Hawaiʻi DHS. (1.06 and 11.05 were
  dropped on 2026-11-16; see `docs/DATA_SOURCES.md`.)
- The loader finds rows and columns by their printed labels and stops if one is missing, so a
  re-laid-out edition cannot be misread silently.

## bea/CAINC1.zip: BEA county personal income (downloaded once)

- Source: U.S. Bureau of Economic Analysis, CAINC1, https://apps.bea.gov/regional/zip/CAINC1.zip
  (one request, 2026-11-16 03:15 UTC). The file says "Last updated: February 5, 2026".
- Read by `pipeline/context.py` (Hawaiʻi rows only). Shown as county/state context, never as a
  district figure. BEA combines Maui and Kalawao; the Maui figure is labeled as such.
- Refresh after BEA's next county release (December 2, 2026): download the zip again, update
  `downloaded_on` and `sha256` in the manifest, change `BEA_YEAR` and the CSV name in
  `pipeline/context.py`.

## acs/acs5_2024.json: Census ACS data (made by a script)

- Source: U.S. Census Bureau Data API, ACS 5-year estimates, 2020-2024 (see `pipeline/sources.yaml` for terms).
- How to make or refresh it: `python pipeline/fetch_acs.py` (needs `CENSUS_API_KEY` in `.env`).
- Refreshed 2026-11-15 to add table C24050 (jobs by industry), and twice on 2026-11-16 to add
  C27007 and B19055, then the program-need, kūpuna-poverty, young-family, homeowner-cost and
  ethnicity tables (see `pipeline/indicators.yaml`). Each time, every earlier value was compared
  and none had changed (18,121 values at the last refresh).
- When to refresh: when you change `pipeline/indicators.yaml`, or when the Census Bureau releases a new ACS year
  (then also change `YEAR` in `pipeline/fetch_acs.py`).
- The file records when it was fetched (`retrieved_at`). The database and every citation use that date.
- After refreshing, run `python pipeline/build.py` and then `python validation/validate.py`.

## opsd/legislative_districts_2022.shp.zip: state district boundaries (download by hand)

- Source: Hawaiʻi Statewide GIS Program, Office of Planning and Sustainable Development (OPSD).
- How to get it: open https://planning.hawaii.gov/gis/download-gis-data-expanded/ in a browser, find
  "Legislative Districts - 2022 (State House & Senate, U.S. Congress)" under
  "003 - Administrative and Political Boundaries", click **Download**, and save the file here as
  `legislative_districts_2022.shp.zip`.
- Then run `python pipeline/boundaries.py` to convert it to GeoJSON for the map.
- Record in `pipeline/boundaries.yaml`: `downloaded_on` (the date) and who downloaded it.
- It is a manual download on purpose: the state's Terms of Use restrict automated access
  (see `pipeline/sources.yaml`). Boundaries change only after a reapportionment, so this is rare.
