# Demo script (about 6 minutes)

Three districts, chosen to show range: one rural, one urban, one high-income. Seth Colby asked us
to show the tool reads sensibly beyond struggling districts. Figures are from the 2026-11-16 build
(ACS 2020-2024). If the data is rebuilt, check them again on the site before presenting.

Site: https://maukabros.onrender.com

## Before the demo

- [ ] `python validation/validate.py`: all checks pass (70 on 2026-11-16)
- [ ] `python validation/test_agent.py`: 21 of 21 (Opus 5.5, medium effort, 2026-11-16)
- [ ] Open the site 5 minutes early. On the `starter` plan it never sleeps; on `free` the first
      load takes about a minute.
- [ ] Ask one test question. If the assistant says it is unavailable, the daily cap
      (`CHAT_DAILY_USD`, $5) may be spent: use the report pages instead (step 5 still works).
- [ ] Browser zoom 125% for the projector. Close other tabs.

## 1. The problem and the headline (1 minute)

Open the site with no district selected.

> "Legislators ask: who lives in my district, and what help is available? Today that answer is
> spread over five or more sources and almost none are published by district."

Point to **Outreach opportunity · SNAP**:

> "31,739 households in Hawaiʻi are below the poverty level and did not receive SNAP in the past
> year: 62% of households below poverty. Their income is well under SNAP's limit, which is 200%
> of poverty for most households. That is the outreach gap the brief asks us to find."

Read the yellow note aloud in one sentence: the survey under-counts SNAP use, so this gap is
likely overstated, and DHS decides eligibility. **Saying this ourselves is the point:** we flag
uncertainty instead of overstating it.

Click **Color the map by this measure** to show the map.

## 2. Rural: House District 4, Puna (1.5 minutes)

Click **House District 4** in the outreach list (Pāhoa is entirely in HD-4).

- Median household income **$57,007 (±$10,922)**: the county is $78,639 and the state $100,389.
- Poverty **23.3% (±4.4 points)**, against 14.9% in Hawaiʻi County.
- Kūpuna poverty (60+) **20.7% (±3.9 points)**, more than twice the state's 9.4%.

**Margin-of-error moment.** HD-4's income margin is ±$10,922, so the true median could be anywhere
from about $46,000 to $68,000. Even so, the gap to the county is larger than the margin, so the
page does not flag it. Rows where a difference falls inside the margin say "may not be a real
difference" (for example, uninsured vs the county here).

Scroll to **Programs**: each program links to the official page and says the agency decides.

## 3. Urban: House District 24, Waikīkī (1.5 minutes)

Use the research assistant. Type:

> Which House district has the most households below the poverty level that don't get SNAP?

It answers **House District 24** with a citation and margin of error. Then show the district:

- **82.8% (±5.8 points)** of its households below poverty do not receive SNAP, against 62.0% statewide.
- Only **6.0%** of households receive SNAP, yet poverty is **12.9%**, above the county's 9.2%.
- **24.0%** of residents are 65 or older.

> "This is where outreach could raise enrollment most: high need, low uptake."

## 4. High-income: House District 20, Kāhala (1 minute)

Ask the assistant:

> What is the median rent in Kahala?

It finds Kāhala in **House District 20** through the official USGS place-name point, writes Kāhala
with its kahakō, and says the figure covers the whole district. Then:

- Median household income **$114,920 (±$9,834)**: higher than the state, but the difference with
  Honolulu County ($106,195) is **within the margin of error**, and the page says so.
- **26.5%** of households earn $200,000 or more; **27.3%** of residents are kūpuna, so the need
  here is ageing in place more than income.

> "A sensible tool should not make every district look like it is struggling, and should not
> claim differences the data cannot support."

## 5. Trust: sources, export, validation (1 minute)

- Any figure: source, year, ACS table link and geography sit under it.
- **Open full report**, then **Print or save as PDF**: the printout has the date generated and
  the data period.
- Validation, in one breath:
  - 70 automated data checks.
  - All 1,064 estimates and 910 margins of error match DBEDT's published district profiles.
  - District mapping is cross-checked against Census block files and against USGS place points
    (134 places agree).
  - The assistant passes 21 of 21 test questions, including refusing to profile an individual
    and refusing to take a political side.
  - Details: `validation/PROTOCOL.md`.

## If asked: what does the margin-of-error flag mean?

- Census figures are survey estimates. The margin of error gives a 90% range: the true value is
  very likely within plus or minus that amount.
- When a district and its county differ by less than the combined margin, the page says "may not
  be a real difference". It does not hide the figure.
- When a figure's margin is large relative to the figure itself (coefficient of variation over 30%), it is
  flagged as low reliability: 179 of 3,344 district figures, mostly small groups in small
  districts.
- Margins for figures we combine (for example, 65 and older) are approximations and are labeled
  "about".
