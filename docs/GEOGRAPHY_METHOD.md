# How figures are matched to legislative districts

2026-11-16. All three levels are built. This answers the slide deck's design question: "How will
you map ZIP code, tract or county data to districts, or is a ZIP code view the better starting
point?"

## The rule: never split a published figure

The brief requires every figure to "say when it was estimated or apportioned to the district".
We avoid apportioning altogether. Each figure is shown for the geography its publisher used, and
the page says which geography that is. There are three levels:

| Level | Sources | How it is matched to a district | Shown as |
|---|---|---|---|
| 1. District | Census ACS 5-year | Published by the Census Bureau for each House and Senate district (2022 plan, unchanged in 2024) | The district's own figure, with margin of error, compared with its county and the state |
| 2. County / state | BEA, BLS, Data Book (DHS SNAP), DOTAX county totals | The district's county, from the County field of the official state boundary file | "County and state context (not figures for this district)" |
| 3. Sub-county area | DOTAX tax areas (Table A-13) | Which tax areas the district's residents live in (method below) | "Tax areas that overlap this district": each area's own figure, never a district total |

## The building blocks: 2020 Census blocks

Every 2020 Census block lies wholly inside one House district, one Senate district, one ZIP Code
Tabulation Area (ZCTA) and at most one Census place. So adding up block populations tells us how
many residents an area shares with a district, with no estimating. The files (all U.S. Census
Bureau, Hawaiʻi rows only; details in `pipeline/raw/manifest.yaml`):

- **Which district each block is in:** 2024 State Legislative District block equivalency files.
  Hawaiʻi's districts are unchanged since 2022, and these are the districts the ACS 2024 figures
  use.
- **Block populations:** TIGER/Line 2020 tabulation blocks (2020 Census counts).
- **Which ZCTA each block is in:** the 2020 ZCTA-to-block relationship file.
- **Which Census place each block is in:** the 2020 block assignment file, with names from the 2020
  place gazetteer.

The 2020 counts are used only as weights for matching. They are never shown as district figures;
the ACS 2020-2024 estimates are.

## Level 3: DOTAX tax areas (`pipeline/blocks.py`, table `tax_area_district`)

DOTAX publishes income for 26 "geographic areas" (e.g. Oʻahu North Shore, Waiʻanae Coast,
Molokaʻi, Puna-Kaʻū). The report does not define the areas; Table A-14 lists the area of each of
121 ZIP codes, and that list is the only definition.

1. **Area footprint.** A tax area is the set of its ZIP codes, each taken as its ZCTA. PO-box-only
   ZIP codes (e.g. 96801-96812) have no ZCTA; their returns are counted in the area figure, but no
   residents are attached to them.
2. **Which areas a district's residents live in.** For each district and tax area: the 2020
   residents of blocks in both. This gives two shares: the share of the district's residents in the
   area, and the share of the area's residents in the district.
3. **What is shown.** For each overlapping area: its name, median income on resident tax returns,
   number of returns, both resident shares, and the county and state medians for comparison. All
   figures are for the whole area. Nothing is added up or averaged into a district number. Where 1%
   or more of a district's residents live in ZIP code areas DOTAX does not list, the page says so.
   Five ZCTAs (96850, 96853, 96858, 96859, 96863; 3,235 residents) have no ZIP code in Table A-14.
4. **Small slivers.** An area holding under 1% of the district's residents is labeled "touches the
   edge" (`OVERLAP_THRESHOLD` in `pipeline/context.py`). 2024 results: 157 district-area pairs; 130
   overlap and 27 touch the edge. The threshold changes only the label, never a figure.

**Why residents, not land.** An earlier version matched by land area. In Hawaiʻi much land is
uninhabited, so land misleads. For example, the North Shore tax area covers 40% of House District
46's land but only 4.8% of its residents.

**Why not split the area figures?** A median cannot be split or added, and splitting return counts
would create estimates DOTAX never published. Listing whole areas keeps every number as published.

**Limits to state on the page:**
- A tax area can be larger than the district (e.g. "Rural Maui").
- Returns count filers, not households or residents.
- Returns with out-of-state or unidentified ZIP codes are not in any area (20,666 in 2023).
- The report does not say whether the ZIP code is a mailing or home address.
- Resident shares are from 2020; populations have shifted since, notably in Lahaina after the 2023
  wildfire.

## Place and ZIP lookup (`place_district`, `zcta_district`)

The same blocks give the share of each Census place's and each ZIP area's 2020 residents in each
district. The assistant uses these to answer "which district is Kāneʻohe in?" with every district
the place spans, e.g. Kāneʻohe: House 49 (67%), 50 (18%), 48 (14%). Census place names are
published without ʻokina or kahakō (e.g. "Kaneohe"); matching ignores them. Neighborhoods inside
Urban Honolulu (e.g. Kahala) are not Census places and are not found yet.

## Validation (`validation/validate.py`, groups F and G)

- ZIP codes add up to their tax area, areas to their county, counties to the state. One difference
  is printed: Wahiawā–Mililani's listed ZIP codes are 1 return short, consistent with DOTAX not
  publishing ZIP codes with ten or fewer returns.
- Every one of the 14,732 blocks is in a known House and Senate district; all 76 districts have
  blocks.
- **Independent cross-check:** every populated block's district-and-ZCTA pairing appears in the
  Census Bureau's separate 2024 district-to-ZCTA relationship files.
- Each place's and each ZIP area's residents add up to 100% per chamber; each tax area's residents
  are fully shared out among House districts and among Senate districts; every district overlaps
  at least one tax area.
- Seth's examples are printed for a hand check against the map. Molokaʻi: 100% in House District 13
  and Senate District 7. Oʻahu North Shore: 100% in Senate District 23; 87.5% in House District 47,
  7.5% in 46, 5.0% in 48.

## Is a ZIP code view the better starting point?

No. ZIP codes are mail routes, not areas. Many in Hawaiʻi are PO boxes with no area at all.
ZIP figures would also be one step further from what legislators need. District figures from the
ACS come first. ZIP codes are used only to look up a place and as the building blocks of DOTAX's
areas.

## Still open

- Team review of this method, and a hand check of a few districts against the map.
