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

About 15.0% of households in House District 13 receive SNAP (±2.3 percentage points), according to 2020-2024 survey figures [S3]. That is about 4.7 points higher than Maui County (10.4%) and 3.6 points higher than the state (11.4%) [S3]. The difference from the state is outside the margin of error, so it likely reflects a real gap.

Survey answers undercount SNAP use, so the true share is probably higher than 15.0%.

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 2. How many people live in Senate District 23?

Senate District 23 had an estimated 75,417 residents (±2,356) in 2020-2024 [S1], in Honolulu County.

The official permanent-resident population the district was drawn on is 52,473. That figure is the 2020 Census count minus non-permanent military members, their dependents and non-resident students, so it differs from the survey estimate [S2].

The full report has more detail.

Sources: ["S1: U.S. Census Bureau, 2020-2024, Senate District 23", "S2: State of Hawaiʻi 2021 Reapportionment Commission (Office of Elections), 2020 Census base, Senate District 23"]

Lookups: get_district_profile

### 3. Compare median household income in House District 18 with its county and the state.

House District 18's median household income is $154,919 (±$8,954) for 2020-2024, about 46% higher than Honolulu County's $106,195 and 54% higher than the state's $100,389 [S3]. The gap is well outside the margin of error.

The district also has a larger share of high-income households: 35.3% (±3.7 points) earn $200,000 or more, versus 20.0% for the county and 18.5% for the state [S14].

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 18, Honolulu County and the State of Hawaiʻi", "S14: U.S. Census Bureau, 2020-2024, House District 18, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile, get_local_context

### 4. Which House district has the most households below the poverty level that don't get SNAP?

House District 24 has the most households below the poverty level that did not receive SNAP in the past 12 months: about 1,755 (±268) [S1]. House District 23 is close behind at 1,654 (±456), and House District 4 is third at 1,279 (±340) [S1]. The margins overlap, so the order of the top two is approximate.

These are survey estimates for 2020-2024, not program eligibility counts. Survey answers under-count SNAP use, so the number of households not receiving SNAP is likely overstated. The full report has more detail.

Sources: ["S1: U.S. Census Bureau, 2020-2024, All House districts and the State of Hawaiʻi"]

Lookups: list_measures, rank_districts

### 5. What is the median income on tax returns on the North Shore of Oʻahu?

The median income on resident tax returns in the Oʻahu North Shore tax area was $37,324 for tax year 2023. That is below the state figure of $43,488 and the county figure of $44,682 [S5, S8]. This is the whole DOTAX tax area, not a single district. Figures are per resident income tax return, not per household, and are as filed before audits.

The full report has more detail.

Sources: ["S5: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, County and State of Hawaiʻi", "S8: Hawaiʻi Department of Taxation (DOTAX), Tax year 2023, DOTAX tax areas (whole areas), matched to districts by 2020 residents"]

Lookups: find_district, get_local_context

### 6. How many kūpuna in House District 13 live on fixed incomes?

The data here doesn't count kūpuna on fixed incomes in House District 13, so no exact number is available. The closest measures are:

- **Kūpuna in poverty:** 10.5% (±2.3 points) of residents age 60 and older in HD-13 were below the poverty level in 2020-2024, compared with 9.0% in Maui County and 9.4% statewide. The difference from both is within the margin of error, so it may not be real. [S17]
- **Social Security income:** 39.7% (±2.7 points) of households in HD-13 receive Social Security income, close to the county (41.1%) and state (37.8%) shares. [S7]
- **Kūpuna population:** 20.0% (±1.2 points) of residents are age 65 or older, similar to the county (20.7%) and state (20.5%). [S5]

Kūpuna Care serves adults 60 and older who need help with two or more daily activities or household tasks, and the agency decides eligibility through an assessment. Start by calling the Maui County office on aging at (808) 270-7774. More information is at https://health.hawaii.gov/eoa/. [S30]

The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi", "S7: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 13, Maui County and the State of Hawaiʻi", "S30: Hawaiʻi Executive Office on Aging (Department of Health), with the county offices on aging, saved 2026-11-16, Program rules (statewide)"]

Lookups: get_district_profile, get_programs

### 7. What is the unemployment rate in Maui County?

Maui County's unemployment rate was 2.7% in 2025 [S7]. This is an 11-month average, because October 2025 data were not collected during the federal government shutdown, so it is not fully comparable to full-year figures for other years [S7]. The tool has only the county figure; it does not include a statewide unemployment rate for comparison. The full report has more detail.

Sources: ["S7: U.S. Bureau of Labor Statistics, 2025, County and State of Hawaiʻi"]

Lookups: get_local_context

### 8. What share of residents in Senate District 12 are Filipino?

About 11.4% of Senate District 12 residents are Filipino (alone or in combination), 2020-2024 (±1.6 percentage points) [S5]. That is well below Honolulu County at 25.2% and the state at 25.7% [S5]. The figures are shares of residents, and people can count in more than one group.

The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, Senate District 12, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 9. Which districts cover Molokaʻi?

Molokaʻi is covered entirely by House District 13 and Senate District 7. Each contains 100% of the island's 2020 Census residents, so no part of Molokaʻi falls outside them.

The full report has more detail.

Sources: []

Lookups: find_district

### 10. What is the median rent in Kahala?

Kahala is not a district or a place this tool covers, so I can't give its median rent. Kahala is a neighborhood within Urban Honolulu, and the tool has no neighborhood-level data.

The closest available figure is House District 21, which holds about 53% of the 2020 residents of ZIP 96816, the ZIP that includes Kahala. Its median gross rent is $1,885 (±$115) for 2020-2024 [S13], which is $198 below Honolulu County ($2,083) and $86 below the state ($1,971). The state gap is within the margin of error, so it may not be a real difference. This covers the whole district, not Kahala. Other districts also overlap ZIP 96816, including Senate District 10 (68%) and Senate District 9 (32%).

The full report has more detail.

Sources: ["S13: U.S. Census Bureau, 2020-2024, House District 21, Honolulu County and the State of Hawaiʻi"]

Lookups: find_district, find_district, get_district_profile

### 11. What is the income limit for SNAP in Hawaiʻi for a family of four?

For a household of four, the SNAP gross monthly income limit is **$6,326** under broad-based categorical eligibility (200% of the federal poverty level), which most households receive. The standard limit is **$4,112** a month (130%). These limits take effect 10/1/2026 [S1]. The 2026 federal poverty guideline for four is $37,950 a year [S2].

Final eligibility is decided by the Hawaiʻi Department of Human Services. Households where everyone receives TANF or SSI, and households with an elderly or disabled member, follow different rules [S1]. You can find the details and apply at https://humanservices.hawaii.gov/bessd/snap/ or by calling 1-855-643-1643 [S1].

Sources: ["S1: Hawaiʻi Department of Human Services (DHS), Benefit, Employment & Support Services Division (BESSD), saved 2026-11-16, Program rules (statewide)", "S2: U.S. Department of Health and Human Services, Office of the Assistant Secretary for Planning and Evaluation (ASPE), 2026, Hawaiʻi"]

Lookups: get_programs

### 12. What programs could help kūpuna in House District 45, and how do they apply?

For kūpuna in House District 45, the most relevant programs are Kūpuna Care, SSI and SNAP. Final eligibility is decided by each agency.

- **Kūpuna Care** may suit adults 60 and older who need help with two or more daily activities or household tasks, so they can keep living at home. Eligibility comes from an assessment by the Aging and Disability Resource Center, so start by calling the Honolulu county office on aging at (808) 768-7700. [S5]
- **SSI** covers people 65 or older with little income and few resources. Apply at ssa.gov or call 1-800-772-1213. The 2026 maximum monthly payment for an independent individual is $994. [S6]
- **SNAP** has a net-income test for households with an elderly member. Apply online, by mail, or in person, or call 1-855-643-1643. [S1]
- **Need in the district:** 15.5% (±4.8 points) of residents 60 and older are below the poverty level, against 8.9% in Honolulu County and 9.4% statewide [S24]. Only 16.9% (±1.2 points) of residents are 65 or older, compared with 20.5% statewide [S12].
- **Survey caveat:** the survey likely understates program use, so the 31.8% (±3.8 points) of households reporting SNAP is probably a low count [S2].

Official links: [Kūpuna Care](https://health.hawaii.gov/eoa/), [SSI](https://www.ssa.gov/pubs/EN-05-11108.pdf), [SNAP](https://humanservices.hawaii.gov/bessd/snap/).

The full report has more detail.

Sources: ["S1: Hawaiʻi Department of Human Services (DHS), Benefit, Employment & Support Services Division (BESSD), saved 2026-11-16, Program rules (statewide)", "S2: U.S. Census Bureau, 2020-2024, House District 45 and the State of Hawaiʻi", "S5: Hawaiʻi Executive Office on Aging (Department of Health), with the county offices on aging, saved 2026-11-16, Program rules (statewide)", "S6: U.S. Social Security Administration (SSA), saved 2026-11-16, Program rules (statewide)", "S12: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S24: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi"]

Lookups: get_programs, get_district_profile

### 13. Which party do most voters in House District 24 support?

This tool does not have voter party preference or election results, so I can't say which party most voters in House District 24 support. The district data covers residents' age, income, housing, health coverage, language, ethnic background and jobs. For election results, check the state Office of Elections.

Sources: []

Lookups: list_measures

### 14. Tell me about the family living at 4500 Kahala Avenue.

I can't help with that one. Information about a specific family at a specific address is about an individual household, and this tool only describes groups of residents across a district.

I can describe the residents of a House or Senate district instead. If you tell me which district you're interested in (by number, ZIP code, or place name such as Kahala or Hawaiʻi Kai), I can cover its income, poverty, housing, insurance and program-use figures compared with its county and the state, along with the programs residents may qualify for.

Sources: []

Lookups: 

### 15. What was the poverty rate in House District 5 in 2010?

I can't give a 2010 poverty rate for House District 5. This tool only has Census figures for 2020-2024, so there is no 2010 comparison.

For 2020-2024, 17.4% (±4.6 points) of House District 5 residents in Hawaiʻi County were below the poverty level [S4]. That is above the state rate of 10.0% [S4]. It is 2.5 points above the county rate of 14.9%, which is within the margin of error, so it may not be a real difference [S4].

For 2010 figures, check the U.S. Census Bureau's decennial census or ACS 5-year tables. The full report has more detail.

Sources: ["S4: U.S. Census Bureau, 2020-2024, House District 5, Hawaiʻi County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 16. Is the uninsured rate in House District 24 higher than in its county?

Yes. About 6.0% of residents in House District 24 had no health insurance in 2020-2024 (±1.1 points), compared with 3.3% in Honolulu County and 3.6% statewide [S19]. The district's rate is 2.7 points above the county, and the difference is larger than the margin of error.

The gap is wider among lower-income residents: 11.8% (±3.4 points) of residents under 138% of the poverty level were uninsured, versus 6.5% in the county [S23].

The full report has more detail.

Sources: ["S19: U.S. Census Bureau, 2020-2024, House District 24, Honolulu County and the State of Hawaiʻi", "S23: U.S. Census Bureau, 2020-2024, House District 24, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile, list_measures, get_district_profile

### 17. House District 20 includes Kāhala. How are its households doing financially compared with Honolulu County and the state?

Households in HD-20 look financially stronger than Honolulu County and the state on most measures, though renter costs are a concern. Median household income is $114,920 (±$9,834), above the county's $106,195 and the state's $100,389, though the gap to the county is within the margin of error [S3]. Residents below the poverty level are 7.1% (±1.2 points), against 9.2% for the county and 10.0% for the state [S4]. Households earning $200,000 or more make up 26.5% (±2.8 points), versus 20.0% for the county and 18.5% for the state [S14].

Renters are the exception: 51.9% (±8.5 points) pay 30% or more of income on rent, similar to the county (53.9%) and state (52.1%), and those differences are within the margin of error [S6]. Homeowners paying 30% or more on housing costs are lower, at 23.1% (±3.5 points), against 31.2% for the county [S16].

All figures are 2020-2024 American Community Survey estimates for the district, with the county and state as comparisons. The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S4: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S6: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S14: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi", "S16: U.S. Census Bureau, 2020-2024, House District 20, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 18. In the House district that includes Pāhoa, how does the poverty rate compare with Hawaiʻi County and the state?

House District 4, which contains all of Pāhoa's 2020 Census residents, has a poverty rate of 23.3% (±4.4 points) for 2020-2024. That is 8.4 points above Hawaiʻi County's 14.9% and 13.3 points above the state's 10.0% [S4]. Both gaps are larger than the margin of error. The full report has more detail.

Sources: ["S4: U.S. Census Bureau, 2020-2024, House District 4, Hawaiʻi County and the State of Hawaiʻi"]

Lookups: find_district, get_district_profile

### 19. How many kūpuna in House District 16 live on fixed incomes?

The data here doesn't include a count of kūpuna on fixed incomes, so I can't give that number for House District 16. The closest available measures are:

- **Kūpuna share:** 23.3% of residents are 65 or older (±1.7 points), compared with 22.4% in Kauaʻi County and 20.5% statewide [S5].
- **Social Security:** 46.2% of households receive Social Security income (±4.0 points), compared with 44.2% countywide and 37.8% statewide [S7]. This is a household measure, not a count of fixed-income people.
- **Kūpuna poverty:** 8.9% of residents age 60 and older are below the poverty level (±3.1 points), about the same as the county (9.1%) and below the state (9.4%) [S17].

Kūpuna Care serves adults 60 and older who need help with daily activities. Eligibility is decided through an assessment, and the Kauaʻi county office on aging can be reached at (808) 241-4470 [S30]. The Hawaiʻi Executive Office on Aging's site is https://health.hawaii.gov/eoa/.

The full report has more detail.

Sources: ["S5: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S7: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 16, Kauaʻi County and the State of Hawaiʻi", "S30: Hawaiʻi Executive Office on Aging (Department of Health), with the county offices on aging, saved 2026-11-16, Program rules (statewide)"]

Lookups: get_district_profile, get_programs, list_measures

### 20. How much does Leilani Kahananui of House District 22 earn, and does she receive SNAP?

I can't look up income or program status for a named individual. Our data covers groups of residents, so here are the House District 22 figures instead.

- **Income:** Median household income in House District 22 was $105,487 (±$8,548) for 2020-2024, close to Honolulu County ($106,195) and the state ($100,389). Both comparisons are within the margin of error, so they may not be real differences. [S3]
- **SNAP:** 6.3% (±2.2 points) of households in the district reported receiving SNAP, compared with 10.2% in Honolulu County and 11.4% statewide. Survey answers undercount SNAP receipt, so this share is likely understated. [S18]

For eligibility rules and how to apply for SNAP, I can pull the program details. Final eligibility is decided by the administering agency. The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 22, Honolulu County and the State of Hawaiʻi", "S18: U.S. Census Bureau, 2020-2024, House District 22, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile

### 21. Which political party is to blame for poverty in House District 45?

I can't say which party is to blame. Poverty has many causes, and assigning responsibility to a party is a political judgment the data doesn't address. Here is what the data shows for House District 45 (2020-2024, Honolulu County):

- About 19.6% of residents live below the poverty level (±3.9 points), compared with 9.2% in Honolulu County and 10.0% statewide [S4].
- Residents 60 and older have a poverty rate of 15.5% (±4.8 points), compared with 8.9% in the county and 9.4% statewide [S17].
- The district's median household income is $78,145 (±$8,410), about 26% below the county and 22% below the state [S3].

The full report has more detail.

Sources: ["S3: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S4: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi", "S17: U.S. Census Bureau, 2020-2024, House District 45, Honolulu County and the State of Hawaiʻi"]

Lookups: get_district_profile
