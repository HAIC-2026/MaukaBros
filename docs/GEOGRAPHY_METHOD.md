# How figures are matched to legislative districts

2026-11-16. Levels 1-3 are built; the threshold in step 4 is set at 1%. This answers the slide deck's design question: "How will you map ZIP code,
tract or county data to districts, or is a ZIP code view the better starting point?"

## The rule: never split a published figure

The brief requires every figure to "say when it was estimated or apportioned to the district".
We avoid apportioning altogether. Each figure is shown for the geography its publisher used, and
the page says which geography that is. There are three levels:

| Level | Sources | How it is matched to a district | Shown as |
|---|---|---|---|
| 1. District | Census ACS 5-year | Published by the Census Bureau for each House and Senate district (2022 boundaries) | The district's own figure, with margin of error, compared with its county and the state |
| 2. County / state | BEA, BLS, Data Book (DHS SNAP), DOTAX county totals | The district's county, from the County field of the official state boundary file | "County and state context (not figures for this district)" |
| 3. Sub-county area | DOTAX tax areas (Table A-13) | Overlap: the tax areas that cover part of the district (method below) | "Tax areas that overlap this district": each area's own figure, never a district total |

## Level 3: DOTAX tax areas (built: `pipeline/build.py` `build_tax_area_overlap`, table `tax_area_district`)

DOTAX publishes income for 26 "geographic areas" (e.g. Oʻahu North Shore, Waiʻanae Coast,
Molokaʻi, Puna-Kaʻū). The report does not define the areas; Table A-14 lists the area of each of
121 ZIP codes, and that list is the only definition.

1. **Area footprint.** A tax area is the set of its ZIP codes (A-14). On a map, a ZIP code is
   drawn as its Census ZIP Code Tabulation Area (ZCTA). PO-box-only ZIP codes (e.g. 96801-96812)
   have no ZCTA; their returns are counted in the area figure, but they add nothing to its outline.
2. **Which areas overlap a district.** We use the Census Bureau's 2024 State Legislative District
   to 2020 ZCTA relationship files for Hawaiʻi (`pipeline/raw/census/`). The 2024 set matches the
   districts in the ACS 2024 figures. Each row is a district-ZCTA pair with the land area of the
   overlap (`AREALAND_PART`). An area overlaps a district if any of its ZCTAs is paired with the
   district.
3. **What is shown.** For each overlapping area: its name, median income on resident tax returns,
   number of returns, and the county and state medians for comparison. All figures are for the
   whole area. The page does not add them up or average them into a district number. It also
   shows two land shares: how much of the district's land is in the area, and how much of the
   area's land is in the district. Where 1% or more of a district's land is in no listed ZIP code
   area, the page says so. Five ZCTAs (96850, 96853, 96858, 96859, 96863) have no ZIP code in
   DOTAX Table A-14.
4. **Small slivers.** A district that touches the edge of a ZCTA would otherwise list that ZCTA's
   whole tax area. The files give the land area of each overlap, so an area covering under 1% of
   the district's land is labeled "touches the edge" (`OVERLAP_THRESHOLD` in
   `pipeline/context.py`). 2024 results: 157 district-area pairs; 148 overlap and 9 touch the edge.
   Land area is only a rough guide to where people live, so the threshold decides only how an
   area is labeled. It never changes a figure.

**Why not split the area figures by population?** A median cannot be split or added. Splitting
the return counts would need block-level population, and it would create estimates DOTAX never
published, which the brief would require us to flag on every figure. Listing whole areas keeps
every number exactly as DOTAX published it.

**Limits to state on the page:**
- A tax area can be larger than the district (e.g. "Rural Maui").
- Returns count filers, not households or residents.
- Returns with out-of-state or unidentified ZIP codes are not in any area (20,666 in 2023).
- The report does not say whether the ZIP code is a mailing or home address.

**Validation:** `validation/validate.py` checks that the ZIP codes add up to their area, areas to
their county and counties to the state. One difference is printed: Wahiawā–Mililani's listed ZIP
codes are 1 return short, consistent with DOTAX not publishing ZIP codes with ten or fewer
returns. Group F checks the overlap:
- each district's overlap parts add up to its land area, and all 76 districts are present;
- every district overlaps at least one tax area;
- each tax area's land is fully shared out among House districts and among Senate districts.

It also prints Seth's examples for a hand check against the map. Molokaʻi is 100% in House
District 13 and Senate District 7. Oʻahu North Shore is 100% in Senate District 23, and split
66.5 / 27.1 / 6.4% across House Districts 47, 46 and 48.

## Is a ZIP code view the better starting point?

No. ZIP codes are mail routes, not areas. Many in Hawaiʻi are PO boxes with no area at all.
ZIP figures would also be one step further from what legislators need. District figures from the
ACS come first. ZIP codes are used only as the building blocks of DOTAX's areas.

## Still open

- Team review of this method, and a hand check of a few districts against the map.
