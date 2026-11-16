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
| F. Overlap | Census relationship files: each district's overlap parts add up to its land area; all 76 districts present | The Census files were read completely |
| F. Overlap | Every district overlaps at least one DOTAX tax area; each tax area's land is fully shared out among House districts and among Senate districts | No district or tax area is left out of the matching |
| F. Overlap (info) | Prints Seth's examples (Oʻahu North Shore, Molokaʻi) with the share of each area's land by district | For a person to check against the district map; land is not population |
| E. Context | BLS unemployment rate shown equals unemployed / labor force (read from the saved file) in every county | The BLS columns were read correctly |

Every saved source file is listed in `pipeline/raw/manifest.yaml` with its URL, download date and
SHA-256 fingerprint; `pipeline/build.py` refuses a file whose fingerprint does not match.

## What this does NOT prove

- **Independence.** The cross-check compares two tables from the same agency (Census ACS). It
  catches pipeline mistakes, not errors in the ACS itself. Independent confirmation of ACS
  figures against other primary sources (e.g. DBEDT/READ, DOTAX) is not yet done.
- **Boundary equivalence.** The map uses the state OPSD 2022 layer. ACS is tabulated on Census
  TIGER 2024 districts. They are believed to describe the same districts but a geometry overlap
  check has NOT been run. Indicator values do not depend on boundary geometry (they are tabulated
  by district number), so this affects only the drawn shapes.
- **Rates.** Margins of error are not computed for map rates (numerator / denominator).
- **Eligibility.** Not covered here.

## Known limitations (found by running the checks)

- Derived margins of error (sums of several ACS cells) are approximations. For the 65+ indicator
  the median difference from the Census-published margin is about 7-8%. In Senate District 8 the
  published margin is unusually small (±51 on 16,530) against our ±727; the cause has not been
  determined. Ours is the more cautious figure.
- Some small-area estimates have margins of error larger than the estimate (e.g. limited-English
  households in House District 51: 55 ± 87). The agent must state this, not present a precise number.

## Expert spot check (to run with DBEDT/READ or another subject-matter expert)

1. Give the expert `validation/spot_check_sample.csv` (5 House and 3 Senate districts, 6
   indicators each; the sample is seeded so it is reproducible).
2. For each row, the expert looks the value up from the official source named in the row and fills
   `verified_by_expert` (yes / no) and `notes`.
3. Any "no" is a defect: record it, fix it, re-run `validate.py`, and re-sample.
4. Include at least one district in a rural area and one high-income district, as Seth Colby's
   kickoff asked for coverage beyond struggling districts.

## When to re-run

After every `pipeline/build.py`, after any change to `indicators.yaml`, and before each demo or
submission.
