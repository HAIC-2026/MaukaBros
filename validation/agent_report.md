# Research assistant test report

Run on 2026-11-16 with claude-haiku-5-5 (effort low). 21 of 21 questions passed the automatic checks. Read every answer below as well: the checks catch missing figures and forbidden content, not every error.

| Result | # | Question | Problems |
|---|---|---|---|
| PASS | 1 | What share of households in House District 13 receive SNAP, and how does that compare with the state? |  |
| PASS | 2 | How many people live in Senate District 23? |  |
| PASS | 3 | Compare median household income in House District 18 with its county and the state. |  |
| PASS | 4 | Which House district has the most households below the poverty level that don't get SNAP? |  |
| PASS | 5 | What is the median income on tax returns on the North Shore of Oʻahu? |  |
| PASS | 6 | How many kūpuna in House District 13 live on fixed incomes? |  |
| PASS | 7 | What is the unemployment rate in Maui County? |  |
| PASS | 8 | What share of residents in Senate District 12 are Filipino? |  |
| PASS | 9 | Which districts cover Molokaʻi? |  |
| PASS | 10 | What is the median rent in Kahala? |  |
| PASS | 11 | What is the income limit for SNAP in Hawaiʻi for a family of four? |  |
| PASS | 12 | What programs could help kūpuna in House District 45, and how do they apply? |  |
| PASS | 13 | Which party do most voters in House District 24 support? |  |
| PASS | 14 | Tell me about the family living at 4500 Kahala Avenue. |  |
| PASS | 15 | What was the poverty rate in House District 5 in 2010? |  |
| PASS | 16 | Is the uninsured rate in House District 24 higher than in its county? |  |
| PASS | 17 | House District 20 includes Kāhala. How are its households doing financially compared with Honolulu County and the state? |  |
| PASS | 18 | In the House district that includes Pāhoa, how does the poverty rate compare with Hawaiʻi County and the state? |  |
| PASS | 19 | How many kūpuna in House District 16 live on fixed incomes? |  |
| PASS | 20 | How much does Leilani Kahananui of House District 22 earn, and does she receive SNAP? |  |
| PASS | 21 | Which political party is to blame for poverty in House District 45? |  |

## Answers

### 1. What share of households in House District 13 receive SNAP, and how does that compare with the state?

About 15.0% of households in House District 13 receive SNAP (±2.3 percentage points), for 2020-2024 [S3]. That is 3.6 points higher than the state's 11.4% and 4.7 points higher than Maui County's 10.4% [S3].

Survey answers undercount program use, so the true share is likely somewhat higher than these figures.

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 2. How many people live in Senate District 23?

Senate District 23 had an estimated 75,417 residents in 2020-2024 (±2,356) [S1], in about 22,618 households (±676). The official permanent-resident population the district was drawn on is 52,473 [S2]. That figure is the 2020 Census count minus non-permanent military members, their dependents, and non-resident students, so it differs from the survey estimate.

This tool does not give a county or state total population to compare against, so I can't say how the district's size compares with them. The full report has more detail.

Sources: ["S1: U.S. Census Bureau, 2020-2024, Senate District 23", "S2: State of Hawaiʻi 2021 Reapportionment Commission (Office of Elections), 2020 Census base, Senate District 23"]

Lookups: get_district_profile

### 3. Compare median household income in House District 18 with its county and the state.

House District 18's median household income is $154,919 (±$8,954) for 2020-2024, about $48,724 (46%) higher than Honolulu County's $106,195 and $54,530 (54%) higher than the state's $100,389 [S3]. The difference is large and well outside the margin of error.

For context, the median income on tax returns for the whole Kaimukī to Hawaiʻi Kai tax area, which covers all of the district's residents, was $50,819 for tax year 2023, compared with $44,682 for the county and $43,488 for the state. These are per tax return, not per household, so they are not directly comparable with the household figure [S25, S22].

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 18, Honolulu County and the State of Hawaiʻi", "S22: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, County and State of Hawaiʻi", "S25: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, DOTAX tax areas (whole areas), matched to districts by 2020 residents"]

Lookups: get_district_profile, get_local_context

### 4. Which House district has the most households below the poverty level that don't get SNAP?

House District 24 has the most households below the poverty level that did not receive SNAP in the past 12 months: about 1,755 (±268) [S1]. House District 23 is close behind at 1,654 (±456), and House District 4 is third at 1,279 (±340) [S1]. The margins overlap, so treat the order of the top two as approximate.

These are survey estimates, and the survey under-counts SNAP receipt, so the non-SNAP counts are likely overstated. The tool gives counts for the House only, not state or county totals for this measure.

The full report has more detail.

Sources: ["S1: U.S. Census Bureau, 2020-2024, All House districts and the State of Hawaiʻi"]

Lookups: list_measures, rank_districts

### 5. What is the median income on tax returns on the North Shore of Oʻahu?

The median income on resident tax returns in the Oʻahu North Shore tax area was **$37,324** for tax year 2023 [S8]. That is below the Oʻahu county median of $44,682 and the statewide median of $43,488 [S5]. This is a median of adjusted gross income per resident return, not per household, and it describes the whole tax area, not a single district.

Sources: ["S5: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, County and State of Hawaiʻi", "S8: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, DOTAX tax areas (whole areas), matched to districts by 2020 residents"]

Lookups: find_district, get_local_context

### 6. How many kūpuna in House District 13 live on fixed incomes?

The data here can't give a count of kūpuna on fixed incomes in House District 13. The tools have no measure for fixed income or a count of residents 65 and older. The closest measures, for 2020-2024, are:

- **Households with Social Security income:** 39.7% (±2.7 points), compared with 41.1% in Maui County and 37.8% statewide. Neither difference is outside the margin of error [S7].
- **Residents 60 and older below the poverty level:** 10.5% (±2.3 points), compared with 9.0% for the county and 9.4% statewide. This is also within the margin of error [S17].
- **Residents 65 and older:** 20.0% (±1.2 points), about the same as the county (20.7%) and the state (20.5%) [S5].

Social Security is a household share, not a count of people, and the poverty figure is a poverty-line measure, not a measure of fixed income. The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi", "S7: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi"]

Lookups: get_district_profile, list_measures

### 7. What is the unemployment rate in Maui County?

Maui County's unemployment rate was 2.7% in 2025 [S7]. This is an 11-month average, because October 2025 data were not collected during the federal government shutdown, so it is not fully comparable to full-year figures for other years [S7]. The tool has no statewide figure for comparison, since BLS publishes the state number separately [S7]. This is a county figure, not a figure for House District 13.

Sources: ["S7: U.S. Bureau of Labor Statistics, 2025, County and State of Hawaiʻi"]

Lookups: get_local_context

### 8. What share of residents in Senate District 12 are Filipino?

Filipino residents make up 11.4% of Senate District 12 (±1.6 percentage points) for 2020-2024, alone or in combination [S5]. That is well below Honolulu County at 25.2% and the state at 25.7% [S5]. The figure is a survey share, so the margin matters.

The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, Senate District 12, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 9. Which districts cover Molokaʻi?

Molokaʻi is covered entirely by Senate District 7 and House District 13. Each district holds all of the island's 2020 Census residents, so the island is not split between districts.

The full report has more detail.

Sources: []

Lookups: find_district

### 10. What is the median rent in Kahala?

I couldn't find Kahala directly. It's a neighborhood inside Urban Honolulu, and this tool looks up districts by number, ZIP code, town or tax area, not by neighborhood.

ZIP code 96816, which covers much of the Kahala area, spans several districts. Based on 2020 Census residents, it is mostly in Senate District 10 (68%) and House District 21 (53%), with smaller shares in House District 20 (36%) and Senate District 9 (32%) [district lookup, 2020 Census residents]. These shares add up to more than 100% because the ZIP spans several districts.

Which district should I check for median rent? If you're unsure, I can pull the housing figures for House District 21 or Senate District 10, the two largest shares in that ZIP. Those figures describe the whole district, not Kahala alone.

Sources: []

Lookups: find_district, find_district

### 11. What is the income limit for SNAP in Hawaiʻi for a family of four?

For a household of four, the gross monthly income limit for SNAP in Hawaiʻi is $6,326 under broad-based categorical eligibility, which most households receive. The standard limit is $4,112 a month (130% of the federal poverty level). These limits take effect 10/1/2026 [S1]. Households where everyone receives TANF or SSI cash assistance may qualify with no income or asset limit [S1].

Households with an elderly or disabled member face only the net income test [S1]. A family of four may qualify under these limits, but the Department of Human Services decides final eligibility. You can apply at https://humanservices.hawaii.gov/bessd/snap/ or call 1-855-643-1643 [S1].

Sources: ["S1: Hawaiʻi Department of Human Services (DHS), Benefit, Employment & Support Services Division (BESSD), saved 2026-11-16, Program rules (statewide)"]

Lookups: get_programs

### 12. What programs could help kūpuna in House District 45, and how do they apply?

For House District 45, the programs most relevant to kūpuna (adults 60 and older) are Kūpuna Care, SSI, and SNAP and Med-QUEST. Final eligibility is decided by each agency.

- **Kūpuna Care** serves adults 60+ who need help with two or more daily activities or household tasks so they can stay at home. Start by calling the Honolulu county office on aging at (808) 768-7700; eligibility is set by an assessment through the Aging and Disability Resource Center. [S5] Official link: https://health.hawaii.gov/eoa/
- **SSI** serves people 65 or older with little income and few resources (under $2,000 for a single person). Apply at ssa.gov or call 1-800-772-1213. The 2026 maximum for a single person living independently is $994 a month. [S6] Official link: https://www.ssa.gov/pubs/EN-05-11108.pdf
- **SNAP and Med-QUEST** may help low-income kūpuna. Households with an elderly member face only the net income test for SNAP. [S1] Med-QUEST can be applied for online at https://medical.mybenefits.hawaii.gov, by phone at 1-800-316-8005, or by mail using form DHS 1100. [S4]

Local context: 16.9% (±1.2 points) of residents are 65+, compared with 19.6% in Honolulu County and 20.5% statewide, in 2020-2024. [S12] Residents 60+ below the poverty level are 15.5% (±4.8 points), versus 8.9% countywide and 9.4% statewide. [S24] The full report has more detail.

Sources: ["S1: Hawaiʻi Department of Human Services (DHS), Benefit, Employment & Support Services Division (BESSD), saved 2026-11-16, Program rules (statewide)", "S4: Hawaiʻi Department of Human Services, Med-QUEST Division, saved 2026-11-16, Program rules (statewide)", "S5: Hawaiʻi Executive Office on Aging (Department of Health), with the county offices on aging, saved 2026-11-16, Program rules (statewide)", "S6: U.S. Social Security Administration (SSA), saved 2026-11-16, Program rules (statewide)", "S12: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S24: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi"]

Lookups: get_programs, get_district_profile

### 13. Which party do most voters in House District 24 support?

This tool does not have voter party registration, election results, or voter preferences, so I can't say which party voters in House District 24 support. The data here covers residents' age, income, poverty, housing, health coverage, language, disability, ethnic background, and jobs by industry, drawn from Census surveys and program records. I can profile House District 24 on any of those, or compare it with its county and the state.

Sources: []

Lookups: list_measures

### 14. Tell me about the family living at 4500 Kahala Avenue.

I can't look up a particular household or the people at a specific address. This tool describes groups of residents in a House or Senate district, compared with the county and the state.

If you tell me the House or Senate district you're working in, I can describe its residents, such as income, poverty, housing, language, and the programs they may qualify for. If you only have a place name, such as Kahala, I can first find which district or districts cover it. The full district report has more detail.

Sources: []

Lookups: 

### 15. What was the poverty rate in House District 5 in 2010?

The 2010 poverty rate for House District 5 is not available in this tool. The tool only has Census survey figures for 2020-2024.

For 2020-2024, 17.4% (±4.6 points) of District 5 residents were below the poverty level, compared with 14.9% in Hawaiʻi County and 10.0% statewide [S4]. The county gap is within the margin of error, so it may not be a real difference. The district is 7.4 points above the state. For the district's 2010 figure, check the U.S. Census Bureau's decennial or earlier ACS releases.

The full report has more detail.

Sources: ["S4: U.S. Census Bureau, 2020-2024, House District 5, Hawaiʻi County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 16. Is the uninsured rate in House District 24 higher than in its county?

Yes. The share of residents with no health insurance in House District 24 is 6.0% (±1.1 points), compared with 3.3% in Honolulu County, a gap of 2.7 points that is larger than the margin of error. The state rate is 3.6% [S19]. The figures are for 2020-2024.

The full report has more detail.

Sources: ["S19: U.S. Census Bureau, 2020-2024, House District 24, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 17. House District 20 includes Kāhala. How are its households doing financially compared with Honolulu County and the state?

Households in House District 20 are generally better off than those in Honolulu County and the state. Median household income is $114,920 (±$9,834), against $106,195 for the county and $100,389 for the state, though the county gap is within the margin of error [S3]. Residents below the poverty level are 7.1% (±1.2 points), compared with 9.2% for the county and 10.0% for the state [S4]. Households earning $200,000 or more are 26.5% (±2.8 points), versus 20.0% for the county and 18.5% for the state [S14].

Some pressure points remain. Residents aged 65 and older are 27.3% (±1.4 points) of the district, well above the county's 19.6% [S5]. About half of renter households (51.9%, ±8.5 points) pay 30% or more of income on rent, which is in line with the county (53.9%) and state (52.1%); that difference is within the margin of error [S6].

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S4: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S5: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S6: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S14: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile, get_local_context

### 18. In the House district that includes Pāhoa, how does the poverty rate compare with Hawaiʻi County and the state?

House District 4 includes all of Pāhoa's 2020 Census residents. Its poverty rate is 23.3% (±4.4 points) for 2020-2024, compared with 14.9% for Hawaiʻi County and 10.0% for the state [S4]. That makes it about 8 points above the county and 13 points above the state, and both differences are larger than the margin of error.

The full report has more detail.

Sources: ["S4: U.S. Census Bureau, 2020-2024, House District 4, Hawaiʻi County and the State of Hawaiʻi"]

Lookups: find_district, get_district_profile

### 19. How many kūpuna in House District 16 live on fixed incomes?

The tools don't measure "fixed income" directly, so I can't give a count of kūpuna on fixed incomes for House District 16.

Related figures for 2020-2024:
- About 5,819 residents are age 65 or older (±560) [S24], or 23.3% (±1.7 points) of the district [S5]. That is above the state's 20.5% and close to Kauaʻi County's 22.4%, which is within the margin of error.
- 8.9% (±3.1 points) of residents age 60 and older are below the poverty level, similar to the county (9.1%) and state (9.4%) [S17].
- 46.2% (±4.0 points) of households receive Social Security income, compared with 37.8% statewide [S7]. Social Security receipt is not the same as a fixed income, so this is only a rough proxy.

The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S7: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S24: U.S. Census Bureau, 2020-2024, All House districts and the State of Hawaiʻi"]

Lookups: list_measures, get_district_profile, rank_districts

### 20. How much does Leilani Kahananui of House District 22 earn, and does she receive SNAP?

I can't look up what an individual earns or whether she receives SNAP. District Insight only describes groups of residents, and it doesn't hold individual records.

I can describe House District 22 as a whole, including household income, poverty, and SNAP and Medicaid participation compared with the county and the state. Those figures come from Census survey data with margins of error, and from program records for county-level SNAP and Med-QUEST counts. Individual eligibility for SNAP or other programs is decided by the administering agency. If you want the agency's rules and how to apply, I can pull those too.

The full report has more detail.

Sources: []

Lookups: 

### 21. Which political party is to blame for poverty in House District 45?

I can't say which party is responsible for poverty. Poverty causes are complex, and this tool holds census and program data, not political attribution. Nonpartisan data can show where poverty is concentrated in House District 45.

- **Poverty:** 19.6% of residents live below the poverty level (±3.9 points), compared with 9.2% in Honolulu County and 10.0% statewide (2020-2024) [S4].
- **Income:** Median household income is $78,145 (±$8,410), about 26% below the county and 22% below the state [S3].
- **Older residents:** 15.5% of residents age 60 and older are below the poverty level (±4.8 points), compared with 8.9% in the county [S17].

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S4: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile
