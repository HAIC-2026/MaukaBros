# Validation report

Run on 2026-11-16 against ACS 5-year 2020-2024. 67 of 67 checks passed.

| Result | Group | Check | Detail |
|---|---|---|---|
| PASS | A cross-check | house: estimates for 6 indicators in every district equal the ACS subject tables (306 comparisons) |  |
| PASS | A cross-check | house: published margins of error equal the subject tables |  |
| PASS | A cross-check | house: INFO derived margin of error (['pop_65_plus']) vs published: median difference 8%, largest 38%. Treated as approximate. |  |
| PASS | A cross-check | senate: estimates for 6 indicators in every district equal the ACS subject tables (150 comparisons) |  |
| PASS | A cross-check | senate: published margins of error equal the subject tables |  |
| PASS | A cross-check | senate: INFO derived margin of error (['pop_65_plus']) vs published: median difference 7%, largest 1326%. Treated as approximate. |  |
| PASS | B consistency | count indicators: House total and Senate total each within 0.5% of the state (63 indicators) |  |
| PASS | B consistency | every rate numerator is between 0 and its denominator |  |
| PASS | B consistency | no negative values or margins of error | 0 found |
| PASS | B consistency | no 'ok' fact is missing its value | 0 found |
| PASS | B consistency | jobs by industry: the 13 industries add up to employed residents in every geography |  |
| PASS | B consistency | one fact per geography per indicator (82 x 65) | 5330 facts |
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
| PASS | E context | Med-QUEST managed care (April 2026): counties add up to the state (401,393 vs 401,393) |  |
| PASS | E context (info) | Medicaid: residents reporting Medicaid/means-tested coverage (ACS 2020-2024) vs Med-QUEST managed-care members (April 2026): COUNTY-001 55,187 vs 84,921 (65%); COUNTY-003 171,271 vs 243,019 (70%); COUNTY-007 16,402 vs 23,073 (71%); COUNTY-009 30,634 vs 50,380 (61%); STATE-15 273,514 vs 401,393 (68%) |  |
| PASS | E context | DOTAX: ZIP code returns (A-14) add up to each area (A-13), allowing up to 10 returns in unpublished ZIP codes | Wahiawā, Mililani: ZIPs 35,429 vs area 35,430 |
| PASS | E context | DOTAX: area returns add up to each county total |  |
| PASS | E context | DOTAX: counties add up to the Hawaiʻi-addresses total (623,965 vs 623,965), plus unidentified = all returns |  |
| PASS | E context | DOTAX area names use the ʻokina, not an apostrophe | 0 found |
| PASS | F overlap | Census file: each district's overlap parts add up to its land area |  |
| PASS | F overlap | Census files cover all 51 House and 25 Senate districts | 76 found |
| PASS | F overlap | every district overlaps at least one DOTAX tax area |  |
| PASS | F overlap | each tax area's 2020 residents are fully shared out among House districts, and among Senate districts |  |
| PASS | F overlap (info) | Seth's examples, share of each area's 2020 residents by district: Molokaʻi: SD-7 100.0%, HD-13 100.0%; Oʻahu North Shore: SD-23 100.0%, HD-47 87.5%, HD-46 7.5%, HD-48 5.0% (check against the district map) |  |
| PASS | E context | DOTAX credits A-7: tax areas plus Other/Unknown add up to the state total for returns, food/excise, renters' and EITC claims |  |
| PASS | E context | DOTAX credits A-4: counties add up to the state for each credit |  |
| PASS | E context | Reapportionment plan: 76 districts (76); House and Senate each add up to 1,348,054 permanent residents (1,348,054 / 1,348,054) |  |
| PASS | P programs | all 11 program documents are saved and match their fingerprints in the manifest |  |
| PASS | P programs | 7 programs: all 41 quotes appear in their saved documents and all 145 income-table numbers are printed in them |  |
| PASS | H DBEDT | our figures equal DBEDT's published ACS district profiles: 1,064 estimates and 910 margins of error for 14 measures in all 76 districts (0 differences) |  |
| PASS | G reliability (info) | 179 of 3344 district figures are flagged low reliability (CV over 30%); highest: HD-30 ind_agriculture_share CV 900%, HD-40 ind_agriculture_share CV 99%, HD-51 limited_english_share CV 96% |  |
| PASS | G blocks | every one of 14,732 blocks is in a known House and Senate district; all 51 + 25 districts have blocks (51 + 25) |  |
| PASS | G blocks | every populated block's district and ZIP area pairing appears in the Census district-to-ZCTA relationship files |  |
| PASS | G blocks | each place's and each ZIP area's residents add up to 100% per chamber; no district's tax-area shares exceed 100% |  |
| PASS | G blocks (info) | largest differences between 2020 Census and ACS 2020-2024 district population (blocks are only weights; expected to differ): HD-47 31,669 vs 28,120; HD-35 28,297 vs 25,206; HD-41 31,537 vs 34,730 |  |
| PASS | L likely eligible | SNAP, Med-QUEST and the Hawaiʻi EITC each have an estimate or a written reason for none (2 estimated: snap, med_quest; not estimated: hawaii_eitc) | missing [], no reason [] |
| PASS | L likely eligible | each estimate's cut point matches its program's official income table and the HHS Hawaiʻi guideline, within 1 point: snap: 200% FPL (BBCE) = 200.0% to 200.1% of the Hawaiʻi guideline, cut 200%; med_quest: Adults 19-64 (138% FPL) = 138.0% to 138.0% of the Hawaiʻi guideline, cut 138% |  |
| PASS | L likely eligible | snap_likely_eligible: a figure for all 82 geographies, each with source, year and margin of error (or a not-published status, never a number); ACS table C17002 is the one the method names | 82 rows; bad: []; tables {'C17002'} |
| PASS | L likely eligible | snap_likely_eligible: House districts add up to the state within the margin of error of the difference (314,200 vs 314,200, gap +0, allowed ±10,611) |  |
| PASS | L likely eligible | snap_likely_eligible: Senate districts add up to the state within the margin of error of the difference (314,200 vs 314,200, gap +0, allowed ±10,541) |  |
| PASS | L likely eligible | snap_likely_eligible: counties add up to the state within the margin of error of the difference (314,200 vs 314,200, gap +0, allowed ±10,438) |  |
| PASS | L likely eligible | snap_likely_eligible: never larger than its universe (pop_ratio_universe, pop_total) in any geography |  |
| PASS | L likely eligible | medquest_likely_eligible: a figure for all 82 geographies, each with source, year and margin of error (or a not-published status, never a number); ACS table C27016 is the one the method names | 82 rows; bad: []; tables {'C27016'} |
| PASS | L likely eligible | medquest_likely_eligible: House districts add up to the state within the margin of error of the difference (198,763 vs 198,763, gap +0, allowed ±8,202) |  |
| PASS | L likely eligible | medquest_likely_eligible: Senate districts add up to the state within the margin of error of the difference (198,763 vs 198,763, gap +0, allowed ±8,097) |  |
| PASS | L likely eligible | medquest_likely_eligible: counties add up to the state within the margin of error of the difference (198,763 vs 198,763, gap +0, allowed ±7,939) |  |
| PASS | L likely eligible | medquest_likely_eligible: never larger than its universe (pop_insurance_universe, pop_ratio_universe, pop_total) in any geography |  |
| PASS | L likely eligible | API: all 152 district estimates carry source, year, margin of error, county and state figures, the estimate caveat and the agency note |  |
| PASS | L likely eligible (info) | snap_likely_eligible (ACS 2020-2024) vs SNAP people served, average month (FY2025 (July 2024 to June 2025)), records as a share of the estimate: COUNTY-001 61,759 ±3,487 vs 40,369 (65%); COUNTY-003 199,266 ±5,931 vs 92,927 (47%); COUNTY-007 16,082 ±1,542 vs 8,086 (50%); COUNTY-009 37,057 ±2,530 vs 17,133 (46%); STATE-15 314,200 ±7,269 vs 158,516 (50%) |  |
| PASS | L likely eligible (info) | medquest_likely_eligible (ACS 2020-2024) vs Med-QUEST managed-care members (April 2026), records as a share of the estimate: COUNTY-001 41,440 ±2,758 vs 84,921 (205%); COUNTY-003 125,947 ±4,488 vs 243,019 (193%); COUNTY-007 9,590 ±1,179 vs 23,073 (241%); COUNTY-009 21,769 ±1,745 vs 50,380 (231%); STATE-15 198,763 ±5,554 vs 401,393 (202%) |  |
| PASS | L likely eligible (info) | sample: HD-18 medquest 1,624 (about ±378); HD-18 snap 2,791 (about ±547); HD-24 medquest 5,035 (about ±631); HD-24 snap 7,306 (about ±833); SD-12 medquest 10,434 (about ±1,264); SD-12 snap 14,793 (about ±1,475); STATE-15 medquest 198,763 (about ±5,554); STATE-15 snap 314,200 (about ±7,269) |  |

See validation/PROTOCOL.md for what these checks do and do not prove.
