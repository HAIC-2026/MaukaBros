# Validation protocol

Answers the brief's requirement: "identify testing protocols and procedures to ensure mapping and
eligibility results are accurate." This covers the **data and mapping**. Program eligibility is
validated separately by whoever owns the program inventory.

## How to run

```
python pipeline/fetch_acs.py    # only when refreshing the Census data (needs CENSUS_API_KEY in .env)
python pipeline/build.py        # build the fact store from the saved data in pipeline/raw/
python pipeline/boundaries.py   # build map shapes from pipeline/raw/opsd/
python validation/validate.py   # run all checks (still needs CENSUS_API_KEY: it re-fetches live)
```

Output: `validation/report.md` (pass/fail table) and `validation/spot_check_sample.csv`.
The script exits non-zero if any check fails, so it can run before every release.

## What is checked

| Group | Check | What a pass shows |
|---|---|---|
| A. Cross-check | Estimates for 6 indicators in all 76 districts equal the same statistic fetched from a different ACS table (subject tables S0101, S1701, S1901) | The pipeline pulled the right variables and did not mis-sum cells |
| A. Cross-check | Published margins of error equal the subject tables | Margins are carried through unchanged |
| A. Cross-check (info) | Margins we derive by summing cells (kūpuna, 65+) are compared with the published margin | Reports how approximate they are; not pass/fail |
| B. Consistency | Count indicators add up: House total and Senate total each within 0.5% of the state | District tabulations cover the state with no gaps or double counting |
| B. Consistency | Every rate is between 0 and 1; no negative values or margins | No impossible results reach the agent or the map |
| B. Consistency | One fact per district per indicator | Nothing dropped silently |
| B. Consistency | Program need (added 2026-11-16): each part is no larger than its whole (e.g. poor households without SNAP ≤ poor households; under 125% ≤ under 200% of poverty ≤ all residents; uninsured under 138% ≤ all under 138%); ethnic groups ≤ total population, Filipino and Japanese ≤ Asian | Need figures are internally consistent (method: `docs/ELIGIBILITY_METHOD.md`) |
| E. Context (info) | SNAP households: ACS survey vs DHS average monthly cases, by county and state | Records how much the survey under-counts SNAP (2024: 68% statewide), the reason "not receiving SNAP" is labeled likely overstated |
| B. Consistency | Jobs by industry: the 13 industries (C24050) add up to employed residents in every geography | Industry shares are complete and not double counted |
| C. Provenance | Every fact has publisher, dataset, period, URL; every indicator names its ACS table | Every figure can be cited to its source (brief: business rules) |
| C. Provenance | Unavailable values are stored as missing, never as a number | The agent cannot present a suppressed value as real |
| D. Mapping | Boundary district ids match database ids one for one (51 + 25) | The map joins each shape to the correct district's data |
| E. Context | County/state-only figures (BEA) are never attached to a district | A county figure cannot be presented as a district figure |
| E. Context | Every context figure has a source URL and download date; numbers only when published | Context figures are citable; unpublished values (Kalawao in BEA) stay missing |
| E. Context | BEA personal income and population (read from the saved file, not shown): the four counties add up to the state | The BEA file was read correctly (Maui figure includes Kalawao) |
| E. Context | BEA per capita income shown equals personal income / population in the same file | The right BEA line was stored |
| E. Context | Data Book SNAP cases and people: counties add up to the state (0.1% allowed: the table notes rounding) | The right row and columns were read from each Data Book table |
| E. Context | DOTAX: ZIP codes (A-14) add up to their area (A-13), areas to their county, counties to the Hawaiʻi-addresses total, and that plus "Other/Unidentified" to all returns. An area may exceed its listed ZIP codes by up to 10 returns, because DOTAX does not publish counts of ten or fewer below the state level; any such gap is printed (2023: Wahiawā, Mililani, 1 return) | The area and ZIP tables were read completely and every ZIP code is in the right area |
| E. Context | DOTAX area names use the ʻokina (DOTAX prints an apostrophe) | Correct Hawaiian spelling (brief: business rules) |
| E. Context | DOTAX tax credits: Table A-7 tax areas plus "Other/Unknown" add up to the state total (returns, food/excise, renters', EITC); Table A-4 counties add up to the state for each credit | Both credit tables were read completely and every A-7 area matched an income-report area |
| E. Context | Med-QUEST: the six islands add up to the report's managed-care total in every month (when the extract is made); counties add up to the state | The report's island table was read correctly |
| E. Context (info) | Medicaid: ACS residents with Medicaid/means-tested coverage vs Med-QUEST managed-care members, by county and state | Records how much the survey under-counts Medicaid (68% statewide), the reason survey Medicaid shares are labeled likely understated |
| E. Context | Reapportionment plan: 76 districts; House and Senate each add up to the report's 1,348,054 permanent residents (also checked when the extract is made) | The report's district tables were read correctly |
| P. Programs | Every program document (11) is a saved file matching its fingerprint in the manifest | Program facts come from the official documents as saved, not from memory or live pages |
| P. Programs | Every quote in `pipeline/programs.yaml` (41, including the likely-eligible rule quotes) appears in its saved document, and every income-table number (145, including the contiguous-states guideline used in the method) is printed in it. Tested by tampering: a made-up quote and two wrong numbers were all caught | Eligibility rules, income limits and contacts are exactly what the agencies published |
| H. DBEDT | Our figures equal DBEDT/READ's published ACS 2020-2024 district profiles (DP02-DP05): 14 measures with identical definitions (population, age, households, labor force, unemployment, income, SNAP, insurance, rent, NHPI, Hispanic) in all 76 districts; 1,064 estimates and 910 published margins of error, 0 differences | Independent confirmation by the challenge champion's own publication that the right ACS values were stored for every district |
| F. Overlap | Census relationship files: each district's overlap parts add up to its land area; all 76 districts present | The Census files were read completely |
| F. Overlap | Every district overlaps at least one DOTAX tax area; each tax area's 2020 residents are fully shared out among House districts and among Senate districts | No district or tax area is left out of the matching |
| F. Overlap (info) | Prints Seth's examples (Oʻahu North Shore, Molokaʻi) with the share of each area's residents by district | For a person to check against the district map |
| G. Blocks | All 14,732 blocks are in a known House and Senate district; all 76 districts have blocks | The block files were read completely |
| G. Blocks | Every populated block's district-and-ZCTA pairing appears in the Census district-to-ZCTA relationship files | Two separate Census products agree (independent check of the matching) |
| G. Blocks | Each place's and each ZIP area's residents add up to 100% per chamber; no district's tax-area shares exceed 100% | Place and ZIP lookups are complete and not double counted |
| G. Blocks (info) | Largest differences between 2020 Census and ACS 2020-2024 district populations | Records how far the 2020 weights are from current estimates |
| G. Reliability (info) | Number of district figures flagged low reliability (coefficient of variation = (MOE / 1.645) / estimate, over 30%) | Records how many figures carry the caution (2024: 179 of 3,344) |
| E. Context | BLS unemployment rate shown equals unemployed / labor force (read from the saved file) in every county | The BLS columns were read correctly |
| L. Likely eligible | SNAP, Med-QUEST and the Hawaiʻi EITC each have an estimate or a written reason for none; each estimate's cut point matches its program's official income table and the HHS Hawaiʻi guideline within 1 point | The estimate applies the rule the agency published, not a remembered one |
| L. Likely eligible | Each estimate has a figure for all 82 geographies with source, year and margin of error (or a not-published status, never a number), from the ACS table the method names; every district's API response carries district, county and state figures, the caveat and the agency note | Every estimate shown can be cited and carries its uncertainty |
| L. Likely eligible | House districts, Senate districts and counties each add up to the state within the 90% margin of error of the difference, sqrt(sum of the parts' squared MOEs + the state's squared MOE) | District estimates cover the state with no gaps or double counting, allowing for survey error |
| L. Likely eligible | Each estimate is never larger than its universe (and the larger universes that contain it) in any geography | No impossible counts |
| L. Likely eligible (info) | Estimates next to DHS SNAP people served and Med-QUEST members, by county and state | Records the scale (2024: SNAP records 50% of the estimate; Med-QUEST members 202%, which is why the Med-QUEST estimate is labeled as running low) |

Every saved source file is listed in `pipeline/raw/manifest.yaml` with its URL, download date and
SHA-256 fingerprint; `pipeline/build.py` refuses a file whose fingerprint does not match.

## What this does NOT prove

- **Independence.** Group A compares two tables from the same agency (Census ACS), and group H
  compares with DBEDT's republication of the ACS. Both catch pipeline mistakes, not errors in the
  ACS itself.
- **Boundary equivalence.** The map uses the state OPSD 2022 layer. ACS is tabulated on Census
  TIGER 2024 districts. They are believed to describe the same districts but a geometry overlap
  check has NOT been run. Indicator values do not depend on boundary geometry (they are tabulated
  by district number), so this affects only the drawn shapes.
- **Rates.** Margins of error are not computed for map rates (numerator / denominator).
- **Eligibility.** Need-side figures are checked for consistency (group B); their method is in
  `docs/ELIGIBILITY_METHOD.md`. Group L checks that the likely-eligible estimates use the
  published income limit and add up, not that the people counted would actually be found
  eligible: rules other than income (immigration, work, assets for some groups, household
  definition) cannot be applied to survey data.

## Known limitations (found by running the checks)

- Derived margins of error (sums of several ACS cells) are approximations. For the 65+ indicator
  the median difference from the Census-published margin is about 7-8%. In Senate District 8 the
  published margin is unusually small (±51 on 16,530) against our ±727; the cause has not been
  determined. Ours is the more cautious figure.
- Some small-area estimates have margins of error larger than the estimate (e.g. limited-English
  households in House District 51: 55 ± 87). The agent must state this, not present a precise number.

## Research assistant answers (`validation/test_agent.py`)

The assistant (`api/agent.py`) can only read figures through tools that query this fact store, and
each figure it gives must carry a numbered source. `validation/test_agent.py` sends 15 questions
to the real model and checks the answers:

| Kind of question | Check | What a pass shows |
|---|---|---|
| Figures (1-9, 15): SNAP, population, income, ranking, tax area, kūpuna, unemployment, ethnicity, place lookup, uninsured | The exact figures (looked up from the database when the test runs) appear, with [S#] citations | Numbers are copied from our data, not recalled or recomputed |
| Caveats (4-8) | The required caveat appears: SNAP gap likely overstated, tax area is the whole area, BLS 11-month average, overlapping ethnic groups | Limits are stated, not dropped |
| Out of scope (10, 14): a neighborhood we cannot locate, a year we do not have | Says the data is not available; gives no invented figure | "Say when data is unavailable" (brief) |
| Program rules (11) | Points to the agency; states no income limit from memory | No unsupported eligibility claims |
| Partisan (12) and individual (13) questions | Declines; no party claims; nothing about a household | Nonpartisan, populations not individuals (brief) |

The automatic checks catch missing figures and forbidden content, not every error, so a person
also reads every answer in `validation/agent_report.md`. Run it before each demo and after any
change to the assistant's instructions or tools. Each run costs about 15 model calls.

## Expert spot check (to run with DBEDT/READ or another subject-matter expert)

1. Give the expert `validation/spot_check_sample.csv` (5 House and 3 Senate districts, 6
   indicators each; the sample is seeded so it is reproducible).
2. For each row, the expert looks the value up from the official source named in the row and fills
   `verified_by_expert` (yes / no) and `notes`.
3. Any "no" is a defect: record it, fix it, re-run `validate.py`, and re-sample.
4. Include at least one district in a rural area and one high-income district, as Seth Colby's
   kickoff asked for coverage beyond struggling districts.

The six sampled indicators are already compared by machine in all 76 districts against a second
publication: population, 65 and older, median household income, median gross rent and no health
insurance against DBEDT's published ACS district profiles (group H), and residents below poverty
against Census subject table S1701 (group A). The expert check adds what a script cannot: a person
at DBEDT/READ confirming the figures and their citations, as the brief's Success Scenario asks.

Status (2026-11-16): not done yet; to be requested from DBEDT/READ in Slack #c_dbedt_agent.
`verified_by_expert` stays empty until an expert fills it. Do not fill it in on their behalf.

## When to re-run

After every `pipeline/build.py`, after any change to `indicators.yaml`, and before each demo or
submission.
