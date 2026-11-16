# Program need and uptake: method

Draft, 2026-11-16. This covers the brief's requirement for "estimates of populations likely
eligible for existing programs, alongside current program uptake where data exists, to show where
outreach could help most". It also covers the deck's "spot opportunity" feature.

## What we can measure, by district

All figures are from the ACS 5-year 2020-2024 and include a margin of error. Every one of them is
published for every House and Senate district.

| Measure | ACS table | What it stands in for |
|---|---|---|
| Households below the poverty level that did not receive SNAP in the past 12 months, and their share of all households below poverty | B22003 | **The SNAP outreach gap** |
| Residents with income under 125% and under 200% of the poverty level | C17002 | The pool from which income-tested programs draw |
| Residents with income under 138% of the poverty level who have no health insurance | C27016 | **The health-coverage outreach gap** |
| Residents with Medicaid or other means-tested public coverage | C27007 | Health-coverage uptake |
| Residents age 60 and older below the poverty level | B17020 | Kūpuna on low fixed incomes (60+, because of the table's age groups) |
| Households receiving SNAP | B22003 | SNAP uptake, as people report it in the survey |

Uptake from program records:
- By county: SNAP households and people served (DHS, Data Book 11.03-11.04, FY2025);
  Med-QUEST managed-care members (Hawaiʻi Medicaid Enrollment Report 2026, April 2026);
  Hawaiʻi EITC, food/excise and renters' credit claims (DOTAX, tax year 2023).
- By DOTAX tax area (matched to districts by residents): the share of resident tax returns
  claiming the Hawaiʻi EITC and the food/excise credit (DOTAX Table A-7). For example, 22.7% on
  the Waiʻanae Coast against 12.4% statewide.

## Residents likely eligible, by program (added 2026-11-16)

For each program with an income limit in `pipeline/programs.yaml`, we count the residents whose
income is under that limit, using the nearest income-to-poverty cut the ACS publishes by district.
These are **estimates of people who pass the income test**, not eligibility counts. The page shows
each one with its margin of error, source and year, the caveat below, and "Final eligibility is
decided by the agency that runs the program."

### Which ACS cuts we have

We use only data already saved in `pipeline/raw/acs/acs5_2024.json` (no new downloads):

| ACS table | Cuts available (ratio of income to poverty) | Universe |
|---|---|---|
| C17002 | under 0.50, 1.00, 1.25, 1.50, 1.85, 2.00 | Residents for whom poverty status is determined (leaves out people in institutions, military barracks and college dorms, and unrelated children under 15) |
| C27016 | under 1.00, and 1.00 to 1.37 (so under 1.38) | Civilian residents not in institutions, for whom poverty status is determined (no active-duty military) |

### How the program limits map to those cuts

All program limits are stated as a percentage of the HHS poverty guideline for Hawaiʻi. We checked
each against the program's own income table: the monthly limit times 12, divided by the 2026 HHS
Hawaiʻi guideline for the same household size (sizes 1 to 8). `validation/validate.py` repeats this
check on every run (group L).

| Program | Rule (official source) | Limit as % of the Hawaiʻi guideline | ACS cut used | Indicator |
|---|---|---|---|---|
| SNAP | Gross income under 200% FPL under broad-based categorical eligibility; no asset limit; no net income test since Feb. 2025. DHS SNAP page (saved 2026-11-16): "Under BBCE, the gross income limit is 200% FPL and there is an unlimited asset standard." "Most households qualify for BBCE" | 200.0% to 200.1% | Under 200% (C17002) | `snap_likely_eligible` |
| Med-QUEST | Income-based (MAGI) coverage for adults 19-64: 133% plus the 5% disregard = 138%, no asset test. Med-QUEST 2026 MAGI income standards (effective 01/13/2026): "MAX MAGI STANDARD: This is the minimum MAGI income standard plus the 5% disregard", "ASSETS ARE EXEMPT FOR INDIVIDUALS SUBJECT TO MAGI METHODOLOGY" | 138.0% (adult column) | Under 138% (C27016) | `medquest_likely_eligible` |
| Hawaiʻi EITC | 40% of the federal EITC; earned income under federal AGI limits by children and filing status (DOTAX flyer, tax year 2025) | about 104% to 203% (see below) | **None: not estimated** | none |

Both estimates add ACS cells (six for SNAP, two for Med-QUEST). Their margins of error use the
Census Bureau's approximation for a sum, the square root of the sum of the squared margins, and
are shown as "about plus or minus". They are stored like every other figure (`fact` table,
source `acs5`, ACS 2020-2024) for all 51 House districts, 25 Senate districts, the 5 counties and
the state, and appear in `GET /api/districts/{geo_id}` in `facts` and, for districts, in each
program's new `likely_eligible` field (district, county and state figures). No existing field
changed.

### Results (ACS 2020-2024)

| Area | SNAP: income under 200% | Med-QUEST: income under 138% |
|---|---|---|
| State of Hawaiʻi | 314,200 (about ±7,269) | 198,763 (about ±5,554) |
| HD-24 | 7,306 (about ±833) | 5,035 (about ±631) |
| HD-18 (highest-income House district on median household income, $154,919) | 2,791 (about ±547) | 1,624 (about ±378) |
| SD-12 | 14,793 (about ±1,475) | 10,434 (about ±1,264) |

Next to program records (different measures and periods, so for scale only):
- SNAP: DHS served 158,516 people in an average month of FY2025, **50%** of the 314,200 estimate
  (Hawaiʻi County 65%, Honolulu 47%, Kauaʻi 50%, Maui 46%).
- Med-QUEST: 401,393 managed-care members in April 2026, **202%** of the 198,763 estimate (193% to
  241% by county). Enrollment far above the estimate confirms that the 138% cut **runs low** as a
  count of everyone Med-QUEST covers (mainly children and pregnant women above 138%, aged, blind
  and disabled coverage, and the national income scale; see below).

### Which way each estimate likely errs

**One bias applies to both: the national income scale.** The ACS compares income with the Census
Bureau's poverty thresholds, which are the same in every state. HHS sets Hawaiʻi's guidelines about
15% higher (2026: $18,360 for one person, against $15,960 in the 48 contiguous states; both from
the saved HHS file). So 200% of the Hawaiʻi guideline is roughly 230% on the ACS scale, and 138% is
roughly 159%. People in between are left out, so both counts are **too low on income**. A rough
illustration only (not shown on the site): if residents are spread as thickly just above the cut
as just below it, the SNAP count would be about 55,000 to 60,000 higher statewide (about 18%), and
the Med-QUEST count about 35,000 higher (about 18%).

**SNAP: could run high or low.**
- Too few: the national income scale (above); households with an elderly or disabled member face
  only the net income test, and households where everyone receives TANF or SSI have no income
  limit, so some people above 200% qualify.
- Too many: only U.S. citizens and some lawful permanent residents may qualify; most able-bodied
  adults must meet work requirements; every member needs a Social Security number; a member
  disqualified under SNAP may keep the household out of BBCE. The survey cannot apply any of these.
- Either way: the ACS measures income over the past 12 months, SNAP current monthly income; SNAP
  households (people who buy and prepare food together) are not Census families.
- Not a bias here: assets. BBCE has no asset limit.
- Unit: the estimate counts people. Compare it with DHS "people served", not "cases".

**Med-QUEST: likely runs low.**
- Too few: children under 19 qualify up to 313% and pregnant women up to 196%, but the saved ACS
  cells do not split those groups at those limits; other routes (medically needy spend-down;
  aged, blind or disabled coverage) are not counted above 138%; the national income scale.
- Too many: residents 65 and older are counted, but they are covered under MAGI-excepted rules
  with asset limits ($2,000 for one person in 2026); immigration-status rules (not detailed in the
  saved documents); from January 1, 2027, work or school requirements for adults 19-64.
- Either way: 12-month vs current monthly income; MAGI counts income for a tax household, and HHS
  notes that each program decides what income counts and who is in the household.
- Statewide, Med-QUEST members are about twice the estimate, so read it as the core group that
  qualifies on income, not as everyone Med-QUEST can cover.

**Hawaiʻi EITC: not estimated.** The limits are federal AGI in dollars by number of children and
filing status. Against the Hawaiʻi guideline for the matching household size they range from 104%
(single, no children: $19,104 vs $18,360) to 203% (single, one child: $50,434 vs $24,890 for two
people); married couples with three children are at 154%. The credit also needs earned income and
is paid only when a tax return is filed. The ACS tables in this tool do not cross income-to-poverty
with earnings and number of children, so no single cut is defensible and any count would be a
guess. The site says so where the estimate would be, and the uptake figure stays the DOTAX share of
resident tax returns claiming the credit, by tax area (Table A-7).

Programs without an income limit in `programs.yaml` (WIC, Kūpuna Care, SSI) are not estimated.

## What these figures are not

- **They are not eligibility counts**, including the "likely eligible" estimates above. We
  compare income with the federal poverty line only. Each
  program has its own rules (household size, other income tests, assets, residency, student or
  work rules). Final eligibility is always decided by the administering agency, and the page says
  so wherever these figures appear.
- **Survey answers under-count program use.** Statewide, the ACS shows 56,236 households
  receiving SNAP (2020-2024), against 83,041 average monthly cases in DHS records (FY2025): 68%.
  For Medicaid, 273,514 residents report Medicaid or means-tested coverage, against 401,393
  Med-QUEST managed-care members in April 2026: also 68% (61-71% by county). The measures and
  periods differ, but gaps this size mean survey shares receiving SNAP or Medicaid are likely
  **understated**, and the share of poor households "not receiving SNAP" is likely
  **overstated**. Both comparisons are printed by `validation/validate.py` on every run.
- **Periods differ.** The ACS covers 2020-2024; DHS records cover FY2025.

## The example the brief asks for (one population + program)

**Households below the poverty level that do not receive SNAP.** Statewide: 62.0% of households
below poverty, about 31,700 households (±1,500). By district, the largest counts are:

- House: HD-24 1,755 (±268; 83% of the district's households below poverty), HD-23 1,654 (±456),
  HD-4 1,279 (±340).
- Senate: SD-12 3,115 (±482; 73%), SD-10 1,895 (±284), SD-1 1,878 (±432).

**Before using this example in the demo:**
1. Done 2026-11-16: the saved DHS SNAP page gives a 200% gross limit under BBCE, which most
   households receive, so the matching cut is under 200% (`snap_likely_eligible`). Below-poverty
   households without SNAP remain a narrower, households-based view of the same gap.
2. Check whether a district's high share has a known reason that affects eligibility (for
   example, many residents in groups with extra program rules). Say so instead of calling it an
   outreach gap.
3. Show the margin of error and the "likely overstated" note with the figure.

## Validation

Automated checks (`validation/validate.py`):
- Every share is between 0 and 1.
- Each part is no larger than its whole: households below poverty without SNAP ≤ all households
  below poverty; under 125% ≤ under 200% ≤ all residents; uninsured under 138% ≤ all residents
  under 138%; and so on.
- The ACS vs DHS SNAP comparison is reported on every run.
- Likely-eligible estimates (group L):
  - SNAP, Med-QUEST and the Hawaiʻi EITC each have an estimate or a written reason for none.
  - Each estimate's cut point matches its program's official income table and the HHS Hawaiʻi
    guideline within 1 point (SNAP 200.0-200.1%, Med-QUEST 138.0%), and its rule quotes appear in
    the saved documents (group P).
  - A figure for all 82 geographies, each with source, year and margin of error, or a
    not-published status and no number; the ACS table matches the one the method names.
  - **Additivity, with an MOE-based tolerance.** House districts, Senate districts and counties
    should each add up to the state. They are separate survey estimates, so the gap may be as
    large as the 90% margin of error of the difference: the square root of (the sum of each part's
    squared MOE plus the state's squared MOE). In the 2020-2024 data the gap is 0 for both
    estimates (allowed ±10,611 for SNAP and ±8,202 for Med-QUEST, House).
  - Never larger than the universe: SNAP ≤ C17002 universe ≤ population; Med-QUEST ≤ civilian
    noninstitutionalized population (B27001; C27016's own total is not in the saved data, and its
    universe is a subset of B27001's) and ≤ the C17002 universe.
  - Every district's API response carries district, county and state figures with source, year,
    margin of error, the caveat and the agency note.
  - Info: estimates next to DHS SNAP people served and Med-QUEST members, by county.

Still to do:
- A DBEDT/READ or DHS reviewer checks the method and a sample of district figures.
- DHS to confirm the share of SNAP households under BBCE and whether the 200% test is applied to
  the same income the ACS measures.
