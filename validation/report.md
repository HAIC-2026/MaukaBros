# Validation report

Run on 2026-11-16 against ACS 5-year 2020-2024. 38 of 38 checks passed.

| Result | Group | Check | Detail |
|---|---|---|---|
| PASS | A cross-check | house: estimates for 6 indicators in every district equal the ACS subject tables (306 comparisons) |  |
| PASS | A cross-check | house: published margins of error equal the subject tables |  |
| PASS | A cross-check | house: INFO derived margin of error (['pop_65_plus']) vs published: median difference 8%, largest 38%. Treated as approximate. |  |
| PASS | A cross-check | senate: estimates for 6 indicators in every district equal the ACS subject tables (150 comparisons) |  |
| PASS | A cross-check | senate: published margins of error equal the subject tables |  |
| PASS | A cross-check | senate: INFO derived margin of error (['pop_65_plus']) vs published: median difference 7%, largest 1326%. Treated as approximate. |  |
| PASS | B consistency | count indicators: House total and Senate total each within 0.5% of the state (61 indicators) |  |
| PASS | B consistency | every rate numerator is between 0 and its denominator |  |
| PASS | B consistency | no negative values or margins of error | 0 found |
| PASS | B consistency | no 'ok' fact is missing its value | 0 found |
| PASS | B consistency | jobs by industry: the 13 industries add up to employed residents in every geography |  |
| PASS | B consistency | one fact per geography per indicator (82 x 63) | 5166 facts |
| PASS | C provenance | every fact has a source with publisher, dataset, year and URL | 0 facts missing |
| PASS | C provenance | every indicator names its ACS table | 0 missing |
| PASS | C provenance | unavailable values are stored as missing, never as a number | 0 found |
| PASS | D mapping | house: boundary district ids match database ids one for one (51 shapes, 51 districts) | only in shapes: []; only in db: [] |
| PASS | D mapping | house: every district has a county that exists in the database (used for the county comparison) | [] |
| PASS | D mapping | senate: boundary district ids match database ids one for one (25 shapes, 25 districts) | only in shapes: []; only in db: [] |
| PASS | D mapping | senate: every district has a county that exists in the database (used for the county comparison) | [] |
| PASS | E context | county/state-only sources are never attached to a district | 0 found |
| PASS | E context | every context figure has a source URL and download date | 0 missing |
| PASS | E context | context figures are a number only when published | 0 found |
| PASS | E context | BEA personal_income: counties add up to the state (102,703,773,000 vs 102,703,773,000) |  |
| PASS | E context | BEA bea_population: counties add up to the state (1,446,146 vs 1,446,146) |  |
| PASS | E context | BEA per capita income shown equals personal income / population |  |
| PASS | E context | snap_cases_monthly: counties add up to the state (83,041 vs 83,041) |  |
| PASS | E context | snap_people_monthly: counties add up to the state (158,515 vs 158,516) |  |
| PASS | E context | BLS unemployment rate equals unemployed / labor force in every county |  |
| PASS | E context (info) | SNAP households, ACS survey 2020-2024 vs DHS average monthly cases FY2025: COUNTY-001 13,197 vs 21,475 (61%); COUNTY-003 34,575 vs 48,384 (71%); COUNTY-007 2,680 vs 4,266 (63%); COUNTY-009 5,781 vs 8,916 (65%); STATE-15 56,236 vs 83,041 (68%) |  |
| PASS | E context | DOTAX: ZIP code returns (A-14) add up to each area (A-13), allowing up to 10 returns in unpublished ZIP codes | Wahiawā, Mililani: ZIPs 35,429 vs area 35,430 |
| PASS | E context | DOTAX: area returns add up to each county total |  |
| PASS | E context | DOTAX: counties add up to the Hawaiʻi-addresses total (623,965 vs 623,965), plus unidentified = all returns |  |
| PASS | E context | DOTAX area names use the ʻokina, not an apostrophe | 0 found |
| PASS | F overlap | Census file: each district's overlap parts add up to its land area |  |
| PASS | F overlap | Census files cover all 51 House and 25 Senate districts | 76 found |
| PASS | F overlap | every district overlaps at least one DOTAX tax area |  |
| PASS | F overlap | each tax area's land is fully shared out among House districts, and among Senate districts |  |
| PASS | F overlap (info) | Seth's examples, share of each area's land by district: Molokaʻi: HD-13 100.0%, SD-7 100.0%; Oʻahu North Shore: SD-23 100.0%, HD-47 66.5%, HD-46 27.1%, HD-48 6.4% (check against the district map) |  |

See validation/PROTOCOL.md for what these checks do and do not prove.
