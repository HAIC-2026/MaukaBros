# Data sources: what we have, what we use, what is left

Status as of 2026-11-15. Terms of use for every source are in `pipeline/sources.yaml`; every saved
file, with its download date and fingerprint, is in `pipeline/raw/manifest.yaml`.

## The one rule that shapes everything

Only the Census ACS publishes figures **by legislative district**. Every other source publishes
by county, island, ZIP code, census tract or its own areas. So the app shows:

1. **District figures**: ACS only, with margins of error, compared with the county and the state.
2. **County and state context**: BEA, BLS and Data Book figures, clearly labeled as describing the
   county, never the district.
3. **Later, sub-district or ZIP figures** (DOTAX, Data Book tract/ZIP tables): only after the
   team agrees a written method for assigning those areas to districts (the slide deck's design
   question).

## In use now

| Figure | Geography | Period | File | Caveat shown in the app |
|---|---|---|---|---|
| 63 ACS indicators: profile, jobs by industry (C24050), Medicaid coverage (C27007), Social Security income (B19055), program need (B22003, C17002, C27016), kūpuna poverty (B17020), young families (B11005), homeowner costs (B25091), ethnic background (B02008, B02011, B02012, B02018, B03002) | District, county, state | 2020-2024 | `acs/acs5_2024.json` | Margins of error; jobs held by residents, wherever the job is; coverage and SNAP are what residents report, not program records; need figures are not eligibility counts (`ELIGIBILITY_METHOD.md`) |
| Per capita personal income (BEA CAINC1) | County, state | 2024 | `bea/CAINC1.zip` | Maui figure includes Kalawao |
| Unemployment rate (BLS LAUS) | County | 2025 | `bls/laucnty25.xlsx` | 11-month average: October 2025 not collected (federal shutdown). No state total in this file |
| SNAP cases and people served (Data Book 11.03-11.04; original data: Hawaiʻi DHS) | Island / county, state | FY2025 (July 2024-June 2025) | `dbedt/DB2025_section11.xlsx` | Program records, i.e. actual uptake |
| Median income on resident tax returns (DOTAX A-13) | County, state | Tax year 2023 | `dotax/2023indinc_tables.xlsx` | Per return, not per household; Hawaiʻi ZIP codes only |
| DOTAX tax areas (A-13) and their ZIP codes (A-14) | 26 sub-county areas, listed for each district they overlap | Tax year 2023 | same, plus `census/tab20_sld*202420_zcta520_st15.txt` | Whole-area figures, not the district's; matched by land overlap (`GEOGRAPHY_METHOD.md`) |

BEA personal income and population, and BLS labor force and unemployed, are still read from the
saved files so validation can recompute the figures shown. They are not stored or shown.

## Recommended set (applied 2026-11-16, except the DOTAX area overlap)

Measured against the brief's list of required figures and Seth's advice: primary sources, no
duplicates, few well-chosen figures, always a comparison, finer than district where possible.
He named kūpuna, young families, income and ethnic background, and DOTAX income.

| Decision | What | Why |
|---|---|---|
| **Keep** | ACS district figures | Only source by district; covers the brief's list (age incl. kūpuna, income, poverty, jobs and industries, housing costs) and Seth's (young families via under-18, NHPI) |
| **Keep** | SNAP households and people served (Data Book 11.03, 11.04; DHS records) | The brief asks for "current program uptake where data exists"; this is our one real uptake series |
| Drop | SNAP benefits paid (11.05) | A dollar total with nothing on the need side to compare it with |
| **Keep, trimmed** | BLS unemployment rate | More recent than the ACS 2020-2024 average. Drop the labor force and unemployed counts from the screen |
| **Keep, trimmed** | BEA per capita personal income | One county income comparison. Drop total personal income |
| Drop | 2025 resident population (Data Book 1.06) | Census estimate republished, not the primary source; a second county population beside the ACS one confuses |
| **Add** | DOTAX Table A-13 by tax area: returns, median Hawaiʻi AGI, share with tax liability | Seth: "income data by district is going to be very important", and he said to open the DOTAX reports. Its areas (Oʻahu North Shore, Waiʻanae Coast, Molokaʻi, Puna-Kaʻū...) are finer than many districts, which answers his "more granular" request. Show each area's figure as published and list which areas overlap the district; do not apportion |
| Use as a tool | DOTAX Table A-14 (ZIP list) | Says which ZIP codes make up each tax area; needed to draw the areas, not shown |
| Skip | DOTAX A-15, A-16 | Same income measure split by filing status; extra figures |
| Skip | All 8 Data Book candidates below | Each is county-only, duplicates a district-level ACS figure, or is outside the brief (reasons in the table) |

ACS additions (added 2026-11-16, labels checked in the Census API): households with Social
Security income (B19055), for the brief's example question "How many kūpuna in my district live
on fixed incomes?"; and residents with Medicaid or other means-tested public coverage (C27007), a
district-level picture of health-coverage uptake.

## Downloaded but not used yet

### State of Hawaii Data Book 2025 (all 24 sections)

All 833 tables are listed in [`data_book_2025_tables.csv`](data_book_2025_tables.csv) with their
finest geography (by title) and their source line. **None is published by legislative district.**
Counts by finest geography: county 121, island 62, place 17, Oʻahu neighborhood 5, ZIP code 2,
census tract 1, state or other 625.

Many county tables simply republish the ACS (e.g. 12.02, 12.03, 13.26, 13.29, 21.17) or BEA
(13.12). Seth asked for primary sources and no duplicates, so we take those from the original
publisher instead. Tables that add something we do not have:

| Table | What | Geography | Original source | Why it might matter | Recommendation |
|---|---|---|---|---|---|
| 12.16 | Job count by industry, 2025 | County | DBEDT | Jobs located in the county (our ACS figure is jobs held by residents) | Skip: ACS already gives industries by district |
| 11.13 | Senior Medicare enrollees | County | CMS | Kūpuna program uptake | Skip: Medicare covers nearly all 65+, so there is little gap to show |
| 11.08-11.10 | Social Security beneficiaries and benefits | County | SSA | Kūpuna and disability income | Skip: county only; ACS has a district equivalent |
| 2.24 | Health risk behaviors and conditions (BRFSS) | County | Dept. of Health | Health picture, if the team wants one | Skip: not in the brief |
| 3.13 | Public school enrollment, 2025-26 | County | Dept. of Education | Young families | Skip: ACS under-18 covers this by district |
| 1.14, 1.15 | Oʻahu neighborhood population and characteristics | Oʻahu neighborhoods | City and County of Honolulu | Finer than district on Oʻahu | Skip: Oʻahu only; DOTAX areas cover every island |
| 1.16, 1.18 | Population by census tract / ZIP code area | Tract, ZCTA | ACS (better taken from the Census directly) | Building blocks for a district crosswalk | Skip: take from the Census if needed |
| 9.27 | Federal income tax returns by ZIP code, TY2022 | ZIP | IRS | Income by ZIP (federal); compare with DOTAX (state) | Skip: duplicates DOTAX, which Seth named |

**Decision for the team / READ:** confirm the recommended set above.

### DOTAX Individual Income Tax Statistics, tax year 2023

`dotax/2023indinc_tables.xlsx`. Relevant tables:

- **A-13** by DOTAX geographic area: 26 areas such as "Oʻahu North Shore", "Waiʻanae Coast",
  "Molokaʻi", "Lānaʻi", "Puna-Kaʻū", with county totals. Columns: number of returns, Hawaiʻi AGI,
  median AGI, tax before/after credits, share with tax liability.
- **A-14** by ZIP code (same columns), **A-16** median federal AGI by ZIP and filing status,
  2023 vs 2022.
- Notes in the file: "s" means suppressed "to prevent potential disclosure of confidential
  taxpayer information"; AGI "Contains negative values". 20,666 returns are
  "Other/Unidentified" (not placed in any area).
- The ZIP list includes PO-box-only ZIP codes (e.g. 96801-96812 Downtown), which have no area on
  a map, so a ZIP-to-district assignment must say how they are treated.

Report PDF `dotax/2023indinc.pdf` (dated October 2026), method notes:

- Data: all Forms N-11 and N-15 for tax year 2023 received by March 31, 2025, before audit
  adjustments.
- Suppression: no tabulation of "ten or fewer returns below the state level", or where one return
  is a large share of a cell.
- Area and ZIP tables cover returns with Hawaiʻi ZIP codes. Tax-district totals for Oʻahu include
  "out-of-state or unidentified/misspecified zip codes".
- **It does not define the geographic areas** or say how ZIP codes are grouped into them; Table A-14
  is the only record (it lists the area for every ZIP). It does not say whether the ZIP is the
  mailing or home address.
- Sections 8-9 (taxpayers 65+, with disabilities) are statewide only.

Loaded: county and state medians are shown as context; the 26 areas and 121 ZIP codes are stored
(`tax_area`, `tax_area_zip`) for the district overlap described in
[`GEOGRAPHY_METHOD.md`](GEOGRAPHY_METHOD.md), which needs the Census relationship files.

## Still to get

| What | Why | Status |
|---|---|---|
| Med-QUEST enrollment by county/island | Medicaid uptake: a possible second uptake example. Not named in the brief, the deck or Seth's talk; the brief asks only for uptake "where data exists" and one population and program example | Optional. Candidate PDFs listed in `sources.yaml`, not opened |
| Enrollment by ZIP or district | A district-level uptake gap | Asked of the challenge team (Slack) |
| datatrove.ai | Event sponsor's data | Access and terms asked of the challenge team |
| UHERO | Only if it has something READ does not | No terms page found; not used |

## Comparing uptake with need (not built yet)

SNAP **uptake** now comes from DHS program records (Data Book 11.03-11.04), by county. The ACS
also has a SNAP figure (households that say they received SNAP in the past 12 months, 2020-2024),
by district. They measure different things over different periods, so the app does not subtract
one from the other. A "likely eligible" estimate needs its own written method (income relative
to the SNAP limit, household size), labeled as an upper-bound estimate.
