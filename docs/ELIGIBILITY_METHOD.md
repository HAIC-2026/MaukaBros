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

## What these figures are not

- **They are not eligibility counts.** We compare income with the federal poverty line only. Each
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
1. Have the program group confirm, from DHS's official SNAP pages, which income limit applies in
   Hawaiʻi. Then choose the matching cut point: below 100%, under 125% or under 200% of poverty.
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

Still to do:
- A DBEDT/READ or DHS reviewer checks the method and a sample of district figures.
- Once program rules are in the program inventory, test that each recommendation's income cut
  point matches the rule and its cited source.
