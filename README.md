# District Insight

Sourced profiles of the people who live in each of Hawaiʻi's 51 State House and 25 State Senate
districts, built for legislators, their staff and State agencies.

District Insight is the MaukaBros entry to the 2026 Hawaiʻi Annual Innovation Challenge (HAIC),
use case "Know Your District", championed by DBEDT's Research and Economic Analysis Division.

**Live site:** [https://YOUR-DOMAIN-HERE](https://YOUR-DOMAIN-HERE)

## What it does

- **District profile.** Pick a district from the list or the map and see six headline figures
  (household income, poverty, kūpuna, rent burden, SNAP use, unemployment), each compared with
  the county and the state.
- **Honest numbers.** Every figure shows its source, year and Census table, with its margin of
  error. Differences inside the margin are labeled "may not be a real difference", estimates too
  uncertain to rely on are flagged, and anything a source does not publish says "Not available".
- **Full report.** Topic views for kūpuna, families and keiki, income and jobs, housing, who lives
  here, and program need, plus a source-data section with every figure and the published counts
  behind it.
- **Compare two districts** side by side, including a House district against a Senate district.
- **Interactive map** of all districts, colored by any measure.
- **Smaller areas.** The towns, ZIP codes and DOTAX tax areas each district's residents live in,
  with income and tax-credit figures for those areas.
- **Programs.** SNAP, Med-QUEST, Hawaiʻi EITC, the food/excise tax credit, WIC, Kūpuna Care and
  SSI: who may qualify, income limits, how to apply and what to bring, quoted from official
  documents and linked to the agency.
- **Research assistant.** Ask a question in plain language. Claude answers using only this tool's
  data and cites a source for every number.
- **Print or share.** Any report prints or saves as a PDF with the date and data period, and every
  view has a shareable link.

## Run it

Requires Python 3.10 or later (developed on 3.13).

```
pip install -r requirements.txt
cp .env.example .env          # then add your keys (see below)
python pipeline/build.py      # builds data/kyd.duckdb from the saved source files
python pipeline/boundaries.py # builds the district shapes for the map
python -m uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000. The API documentation is at http://127.0.0.1:8000/docs.

The source files are already saved in `pipeline/raw/`, so building needs no network access,
except for the district boundary file, which is downloaded by hand once (steps in
[pipeline/raw/README.md](pipeline/raw/README.md)).

### Settings (`.env`)

| Setting             | Needed for                                                     | Get your own key                                                                                              |
| ------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | The research assistant. Everything else works without it.      | [Anthropic Console](https://platform.claude.com/settings/keys) (sign in, then **Create Key**). Paid by usage. |
| `CENSUS_API_KEY`    | Only to re-download the Census data (`pipeline/fetch_acs.py`). | [Census Bureau key request](https://api.census.gov/data/key_signup.html) (free; the key arrives by email).    |

Paste each key after the `=` on its line in `.env`. Keys stay on your computer: `.env` is excluded
from git and is never sent to the browser.

The research assistant is paid per use from your own Anthropic account. To limit what it can
spend, set a monthly limit in the Anthropic Console as well as the daily cap below.

The assistant's limits (questions per visitor, daily spending cap and others) are also set here;
`.env.example` lists them with their defaults.

### Rebuilding from the original files

`pipeline/fetch_acs.py` re-downloads the Census survey data. The `extract_*.py` scripts recreate
the small extracts made from large PDFs and national files; they need `pdftotext` (Poppler)
installed. Every saved file is fingerprinted in `pipeline/raw/manifest.yaml`, and the build stops
if a file has changed.

## How it is built

| Part          | What it is                                                                                                                        |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `pipeline/`   | Python scripts that read the saved source files and build a DuckDB database                                                       |
| `api/`        | A FastAPI service: district data, map layers, programs and the research assistant                                                 |
| `web/`        | Plain HTML, CSS and JavaScript (no build step), in the style of the IBM Carbon Design System; the map uses Esri's ArcGIS Maps SDK |
| `validation/` | Automated checks of the data, the assistant and the security controls                                                             |
| `docs/`       | Data sources, the geography method and the program-eligibility method                                                             |

The research assistant uses Claude (Anthropic) with tools that only read the database, so it
cannot use figures from anywhere else.

### API

| Endpoint                          | Returns                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------- |
| `GET /api/districts`              | All 76 districts                                                                      |
| `GET /api/districts/{id}`         | One district's figures, comparisons, local areas and programs (e.g. `HD-47`, `SD-23`) |
| `GET /api/comparisons`            | The state and counties used as comparison areas                                       |
| `GET /api/map/metrics`            | Measures the map can show                                                             |
| `GET /api/map/{metric}/{chamber}` | District shapes with one measure, for `house` or `senate`                             |
| `GET /api/programs`               | The program inventory                                                                 |
| `POST /api/chat`                  | A research assistant answer                                                           |

## Data

All data is public and aggregated; there are no individual records.

| Source                                                          | What                                                                                                            | Geography                  |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------- |
| U.S. Census Bureau, American Community Survey 5-year, 2020-2024 | 63 measures of population, age, income, poverty, housing, health coverage, jobs, language and ethnic background | Districts, counties, state |
| 2021 Reapportionment Commission Final Report                    | Official permanent-resident population each district was drawn on                                               | Districts                  |
| Hawaiʻi Statewide GIS Program (OPSD)                            | 2022 legislative district boundaries                                                                            | Districts                  |
| U.S. Census Bureau, 2020 Census blocks                          | Matching districts to towns, ZIP codes and tax areas, weighted by residents                                     | Blocks                     |
| Hawaiʻi Department of Taxation                                  | Income on tax returns and tax-credit claims, tax year 2023                                                      | Tax areas, counties, state |
| DBEDT Data Book 2025 (from Hawaiʻi DHS)                         | SNAP cases and people served                                                                                    | Counties, state            |
| Hawaiʻi Med-QUEST Enrollment Report 2026                        | Managed-care members                                                                                            | Counties, state            |
| U.S. Bureau of Economic Analysis                                | Per capita personal income, 2024                                                                                | Counties, state            |
| U.S. Bureau of Labor Statistics                                 | Unemployment rate, 2025                                                                                         | Counties                   |
| State and federal program agencies                              | Program rules, income limits and how to apply                                                                   | Statewide                  |

County and state sources describe the county a district is in, never the district itself, and are
labeled that way. Details, periods and caveats: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
How districts are linked to smaller areas: [docs/GEOGRAPHY_METHOD.md](docs/GEOGRAPHY_METHOD.md).

## Accuracy

```
python validation/validate.py        # 67 data checks
python validation/test_security.py   # 35 security checks, no AI calls
python validation/test_agent.py      # 21 assistant questions (uses the Anthropic API)
```

- Our district figures match DBEDT's published ACS district profiles exactly: 1,064 estimates and
  910 margins of error across all 76 districts, with no differences.
- The data checks also confirm that districts add up to the state, that every figure has a source,
  that unpublished values are never stored as numbers, and that the area matching is complete.
- Every program fact and income limit is checked against the saved official document.
- The assistant's answers are checked: any number that does not match the data it looked up is
  shown under the answer as "not found in the data".

What the checks do and do not prove: [validation/PROTOCOL.md](validation/PROTOCOL.md).

## Deploy on Render

[render.yaml](render.yaml) describes the whole service. The data is built during each deploy from
the saved files in `pipeline/raw/` (about a minute, no keys needed), so the database is never
committed.

1. On [Render](https://dashboard.render.com), choose **New > Blueprint**, connect this GitHub
   repository and pick the branch to deploy (normally `main`).
2. Paste your `ANTHROPIC_API_KEY` when asked. Leave it empty to run without the research assistant.
   Render creates `CHAT_SIGNING_KEY` itself.
3. Set a monthly spending limit in the Anthropic Console. `CHAT_DAILY_USD` in `render.yaml`
   caps the assistant at about $5 a day.
4. After the first deploy, open the site and put its address in **Live site** above.

Each push to the deployed branch redeploys. The free plan sleeps after 15 minutes without visits and
takes about a minute to wake; switch `plan` to `starter` for judging so the site answers at once.

After the first deploy, check that one visitor cannot pose as another (the per-visitor question
limit trusts the `X-Forwarded-For` header Render passes on):

```
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code} " -X POST https://YOUR-SITE/api/chat \
  -H "Content-Type: application/json" -H "X-Forwarded-For: 10.0.0.$i" \
  -d '{"messages":[{"role":"user","content":"Population of House District 1?"}]}'; done
```

If all 12 return `200`, the faked header is trusted: tell whoever owns `api/security.py`.
Some `429` responses mean the limit holds.

## Security and privacy

The site holds no personal data and stores no questions. Research-assistant questions are sent to
Anthropic to be answered, and the page says so. Limits on questions and spending, signed
conversation history and a strict Content Security Policy protect the service.
Details: [SECURITY.md](SECURITY.md).

## Known limits

- Survey estimates carry sampling error. In small districts some margins of error are large;
  these figures are flagged (179 of 3,344 district figures).
- Margins of error for combined figures (for example, residents 65 and older) are approximations.
- The Maui County comparison leaves out Kalawao County, which the Census Bureau reports
  separately.
- Program information is informational only. Final eligibility is always decided by the agency,
  and the rules must be re-checked when they change (SNAP each October, Med-QUEST and the federal
  poverty guidelines each January, tax credits each tax year).

## License

MIT. See [LICENSE](LICENSE). Data remains subject to each publisher's terms, recorded in
`pipeline/sources.yaml`.
