# Know Your District: build checklist

Status as of 2026-11-15. Source for each item: the HAIC use case brief (section named in brackets) or
Seth Colby's kickoff video ("Seth").

- `[x]` done   `[~]` partly done or not yet verified   `[ ]` not started
- **(other group)** = owned by another team; this app only needs a place to show it

## 1. Core product (the "agent")

- [~] **Chat agent that answers plain-language questions** [Basic Flow 1, 5; Desired platform]: built (`api/agent.py`, `POST /api/chat`, chat panel on the page). Claude Opus 5.5 via the Anthropic API, refusal fallbacks on. **Not yet run against the real model: needs `ANTHROPIC_API_KEY` in `.env`**
  - [~] Team to confirm the model/API choice (brief: teams choose; favor components the State could evaluate)
  - [x] Answers use only data from the API: five tools read only `data/kyd.duckdb` (find_district, list_measures, get_district_profile, get_local_context, rank_districts); the instructions forbid figures from memory [Responsible AI]
  - [x] Every figure cites a numbered source (publisher, dataset, period, geography, table links), shown under the answer; margins of error and "may not be a real difference" come from the tools [Business Rules]
  - [~] Says "unavailable" instead of guessing: instructed, and tested by questions 10-14 in `validation/test_agent.py` (not run yet) [Business Rules]
  - [~] Never identifies or infers anything about individual residents: instructed; test question 13 [Business Rules]
  - [~] Stays nonpartisan: instructed; test question 12 [Business Rules]
  - [~] Test set: 15 questions with expected figures looked up from the database (`validation/test_agent.py`, report `validation/agent_report.md`). **Run it once a key is set (about 15 model calls)** [Model Validation]
  - [ ] Questions are sent to Anthropic's API. They contain no resident data, but note it in the privacy statement
- [~] Find a district by place name: ZIP codes, 163 Census places (towns/CDPs) and DOTAX tax areas, each with the share of residents per district, through the assistant's find_district. No neighborhood (e.g. Kahala) or address lookup yet [Basic Flow 1; Seth]
- [x] Choose a district by chamber and number (House 51, Senate 25)

## 2. District profile (data on screen)

- [x] Population with margin of error
- [x] Age including kūpuna, poverty, income, housing cost, SNAP, health insurance, disability, unemployment, language [Calculations]
- [x] District compared with its county and the state, with the margin-of-error flag [Calculations; Seth]
- [x] Every figure shows source, year, table link and geography [Business Rules]
- [x] "Not available" shown when the source suppresses a value [Business Rules]
- [x] Derived margins of error labeled "about" [Business Rules]
- [x] Employment by industry [Calculations]: ACS C24050, 13 industries as shares of employed residents, compared with county and state, and selectable on the map. These are jobs held by residents, not jobs located in the district.
- [ ] Other indicators DBEDT/READ prioritizes [Calculations]. Ask the champion (Slack #c_dbedt_agent) which.
- [ ] Team decision on the headline statistics (`KEY_METRICS` in `web/index.html`). Seth: fewer, well-chosen figures rank higher.
- [ ] Compare two districts side by side [Seth]
- [ ] Detail finer than the district (e.g. North Shore vs Waialua) [Seth]
- [~] Check a high-income district (e.g. Kahala) reads sensibly, not only struggling ones [Seth]

## 3. Programs and outreach (other group)

- [x] Program inventory (`pipeline/programs.yaml`): SNAP, Med-QUEST, Hawaiʻi EITC, food/excise tax credit, WIC, Kūpuna Care, SSI, plus the 2026 HHS poverty guidelines for Hawaiʻi. Eligibility, income limits, how to apply, documents to bring, contacts. Every fact quoted from an official document saved by hand in `pipeline/raw/programs/`; validation group P checks all 35 quotes and 144 numbers against the files
- [x] Programs section on each district page, with the district's related figures and county program records; assistant tool `get_programs`
- [x] Each program links to its official page [Business Rules]
- [x] "Final eligibility is decided by the agency" note shown with every program and in the assistant's rules [Business Rules]
- [ ] Keep program information current: re-save the documents when rules change (SNAP each October, Med-QUEST each January, HHS guidelines each January, tax credits each tax year), update `checked_on`, run `python pipeline/programs.py` [Assumptions; winning criteria]
- [~] Estimate of residents likely eligible for a program [Calculations]: need-side figures by district built; method in `docs/ELIGIBILITY_METHOD.md`. Still needs program income rules from official sources (program group) to pick the cut point
- [x] Program uptake counts where published, to show the outreach gap [Calculations]: SNAP by county (DHS), SNAP and Medicaid by district (ACS, self-reported)
- [~] At least one population + program example where outreach could raise uptake [Success Scenario]: households below poverty not receiving SNAP (statewide 62%, ~31,700; largest HD-24, SD-12). Labeled likely overstated (ACS counts 68% of DHS SNAP cases). Confirm the SNAP income rule before the demo

## 4. Map

- [x] ArcGIS map of House and Senate districts, colored by a chosen measure
- [x] Selected district outlined and zoomed to
- [x] Legend, island zoom buttons, hover label
- [~] **Click a district, hover, and the island buttons: not tested** (screenshots only). Please try in a browser.
- [x] Official state boundaries (OPSD 2022) recorded with terms in `pipeline/boundaries.yaml`
- [ ] Geometry overlap check: OPSD 2022 vs Census TIGER 2024 (believed identical, not verified)
- [ ] Confirm ArcGIS use is allowed without an Esri key/licence for the submission (see section 6)

## 5. Export

- [~] Print / save as PDF button. Works through the browser; layout not reviewed.
  - [ ] Review the printed page: sources visible, no cut-off tables, ʻokina correct
  - [ ] Include date generated and data period on the printout

## 6. Data sources

- [x] ACS 5-year 2020-2024 by legislative district, county and state
- [x] BEA county personal income [Data Set]: CAINC1 2024, saved file, shown as "County and state context" (Maui figure includes Kalawao, labeled). Refresh after BEA's 2026-12-02 release.
- [x] BLS county unemployment [Data Set]: 2025 labor force, unemployed, rate by county, shown as county context with BLS's 11-month-average footnote (October 2025 not collected)
- [~] DBEDT/READ Data Book 2025 [Data Set; Seth: primary source]: all 24 sections saved; Table 1.06 (2025 population) and 11.03-11.05 (SNAP uptake by island) in use. Catalogue of all 833 tables in `docs/data_book_2025_tables.csv`; candidates in `docs/DATA_SOURCES.md`. **Ask READ which others they want**
- [~] DOTAX income [Seth]: A-13 and A-14 loaded. County and state median income on tax returns shown as context; 26 tax areas and 121 ZIP codes stored. District overlap built from 2020 Census blocks, by residents (1% threshold): each district page lists the tax areas its residents live in, with whole-area figures [Assumptions; Seth: finer than district]. **Hand-check a few districts against the map**
- [x] Census 2020 blocks loaded (2024 district equivalency, block populations, block-to-ZCTA, places): population-weighted tax-area, place and ZIP matching; independent cross-check against the Census district-to-ZCTA files passes
- [x] Low-reliability flag (CV over 30%) on the page and in the assistant's data: 179 of 3,344 district figures
- [x] DOTAX tax credits 2023: Hawaiʻi EITC, food/excise and renters' credit claims by county (A-4) and share of returns claiming them by tax area (A-7), shown with the tax areas
- [x] Official permanent-resident population per district (2021 Reapportionment Commission report, Tables 9-10), shown under the district name; both chambers add to the report's 1,348,054
- [x] Cross-check against DBEDT's published ACS district profiles: 1,064 estimates and 910 margins of error, 14 measures, all 76 districts, 0 differences (validation group H)
- [x] Med-QUEST managed-care enrollment by county and state, April 2026 (Hawaiʻi Medicaid Enrollment Report 2026, downloaded by hand; latest month at least six months old). Survey Medicaid coverage is 68% of these records, so it is labeled as likely understated
- [x] Recommended data set applied (`docs/DATA_SOURCES.md`): kept ACS, SNAP 11.03-11.04, BLS rate, BEA per capita; added DOTAX; dropped Data Book 1.06 and 11.05; skipped the other Data Book candidates
- [x] ACS additions: Medicaid/means-tested coverage (C27007) and Social Security income (B19055), by district, on the page and the map
- [x] ACS additions (2026-11-16, definitions checked in the Census API): program need (B22003 poor households without SNAP, C17002 under 125%/200% of poverty, C27016 uninsured under 138%), kūpuna poverty (B17020, age 60+), young families (B11005), homeowner cost burden (B25091), ethnic background (B02008, B02011, B02018 Filipino and Japanese, B03002 Hispanic and two or more races). 63 indicators, all published for every district
- [~] Program uptake for the outreach gap [Calculations]: SNAP by island/county (DHS via Data Book 11.03-11.05) in use. Med-QUEST is optional (not named in the brief, deck or Seth's talk): candidate PDFs listed in `sources.yaml`
- [~] **Answer the deck's design question in writing** (slide 5): `docs/GEOGRAPHY_METHOD.md` (three levels, all built; DOTAX areas listed by overlap, never split). Team to review
- [ ] Sub-district detail: DBEDT Data Book Tables 1.14-1.16, 1.18 (Oʻahu neighborhoods, census tract, ZIP) or ACS by tract; needs a method for assigning areas to districts
- [ ] UHERO: no terms page found; not used. Seth says most is repackaged READ data
- [ ] datatrove.ai: page unreadable, no terms found; not used until the challenge team supplies terms [Special Requirements]
- [x] Terms of use recorded for every source in use or planned: Census API, Census TIGER (reference), OPSD, Esri SDK, BEA, BLS, Hawaiʻi.gov (DBEDT, DOTAX), UHERO and datatrove.ai (none found), in `pipeline/sources.yaml` [Special Requirements]
- [x] Every saved file listed in `pipeline/raw/manifest.yaml` with URL, date and SHA-256; the build refuses a changed file
- [x] Census API required notice shown in the page footer
- [x] Pipeline no longer downloads anything while building: Census data is saved once (`pipeline/fetch_acs.py` -> `pipeline/raw/acs/`), the state boundary file is read from a local copy
- [ ] **Download the OPSD boundary file by hand** and save it as `pipeline/raw/opsd/legislative_districts_2022.shp.zip` (steps in `pipeline/raw/README.md`), then fill in `downloaded_on` / `downloaded_by` in `pipeline/boundaries.yaml`
- [ ] Confirm with the challenge team that using the manually downloaded OPSD file is fine (the Hawaii.gov terms restrict automated access)
- [ ] **Request the free HAIC ArcGIS Location Platform voucher and Hub identity** at https://esri-haic-histategis.hub.arcgis.com/ (challenge team's Slack answer), then load the SDK with our own API key. Read Esri's product-specific terms (not read yet).
- [ ] Confirm a state-run challenge entry counts as non-commercial under the Hawaii.gov terms
- [ ] Ask the challenge team: is storing and showing DBEDT/DOTAX figures fine under the Hawaiʻi.gov Terms of Use (commercial-use and automated-access clauses)?
- [ ] Keep program information current: decide the refresh process and owner [Assumptions]

## 7. Accuracy and validation [Model Validation; Seth: accuracy is the main judging axis]

- [x] `validation/validate.py`: 51 checks pass (cross-check against ACS subject tables, internal consistency incl. industries, provenance, mapping, county/state context incl. BEA, BLS, SNAP and DOTAX ZIP/area/county totals, and the tax-area overlap)
- [x] Written protocol, `validation/PROTOCOL.md`
- [ ] Subject-matter expert (DBEDT/READ) fills in `validation/spot_check_sample.csv`
- [ ] Run `validate.py` again after every data rebuild and before each demo
- [~] Test the agent's answers against the same figures: `validation/test_agent.py` written, not run yet (needs `ANTHROPIC_API_KEY`)
- [ ] Test program eligibility results **(other group)**
- [ ] Confirm what the margin-of-error flag means for small districts in the demo script

## 8. Accessibility and plain language [Business Rules: WCAG 2.1 AA]

- [~] Built with labels, keyboard district list as an alternative to the map, text that scales. **Not audited.**
- [ ] Automated audit (e.g. axe or Lighthouse) and fix the findings
- [ ] Colour contrast check of text, flags and map colours
- [ ] Keyboard-only walk-through of the whole page
- [ ] Screen reader check
- [ ] Plain-language review of every label and message
- [ ] ʻOkina and kahakō correct everywhere, including the agent's answers

## 9. Known limits to state openly

- Margins of error on summed indicators (e.g. 65+) are approximations; one Senate district differs a lot from the published figure
- Maui County comparison leaves out Kalawao County (the Census Bureau reports it separately)
- Each district's county comes from the state boundary file's County field, not from the geometry
- Rates inherit ACS sampling error; small districts can have a margin larger than the estimate

## 10. Project housekeeping

- [ ] Commit the current work (many uncommitted changes on `api-and-preview`) and open a pull request
- [x] Add `.env.example` (`build.py` points to it)
- [ ] Write the README: what it is, how to run each step, data sources, limits
- [ ] Remove the older `web/map.html` page, now covered by the main page
- [ ] Agree the interface with Shade if they build the real front end (the API stays the same)
- [ ] Decide how the demo runs (local, or hosted) and test it on a clean machine
- [ ] Prepare the demo script: one rural, one urban, one high-income district
