// Report views. Each preset is data only: add or edit an entry here to change the report page.
//   metrics:  metric ids (MAP_METRICS in api/main.py) shown as headline cards, in order.
//   sections: extra blocks below the cards. Types:
//     { type: "group", title, group }        comparison table for one metric group
//     { type: "taxAreas", title }            DOTAX tax areas overlapping the district
//     { type: "context", title, ids }        county/state figures (county_context indicator ids)
//     { type: "note", title, text }          plain text block
//   keywords: words in a chat question that point to this view.
//   groups:   metric groups (get_district_profile) that point to this view.
// Keep each view short: five or six cards reads best.

export const PRESETS = [
  {
    id: "overview", label: "Overview",
    blurb: "The headline figures for this district, each compared with its county and the state.",
    metrics: ["median_household_income", "poverty_rate", "share_65_plus", "rent_burden_rate",
              "no_insurance_rate", "snap_share", "unemployment_rate"],
    sections: [],
  },
  {
    id: "kupuna", label: "Kūpuna",
    blurb: "Older residents: how many there are, how many live alone, and how many have low incomes.",
    metrics: ["share_65_plus", "kupuna_poverty_rate", "kupuna_alone_share", "social_security_share",
              "disability_rate"],
    notes: ["The disability figure covers residents of all ages, not only kūpuna."],
    keywords: ["kupuna", "kūpuna", "elder", "senior", "older", "65", "60", "retire", "social security", "fixed income"],
    sections: [],
  },
  {
    id: "families", label: "Families & keiki",
    blurb: "Households with children, single parents, and family income.",
    metrics: ["under_18_share", "households_with_children_share", "single_parent_share",
              "poverty_rate", "income_under_50k_share", "limited_english_share"],
    notes: ["The poverty, income and language figures cover all residents or households, not only families with children."],
    keywords: ["keiki", "child", "children", "kid", "famil", "parent", "youth", "school"],
    sections: [],
  },
  {
    id: "income", label: "Income & jobs",
    blurb: "Household income across the range, unemployment, and the industries residents work in.",
    metrics: ["median_household_income", "income_under_50k_share", "income_200k_plus_share",
              "poverty_rate", "unemployment_rate"],
    keywords: ["income", "earn", "wage", "job", "work", "employ", "industr", "tax", "wealth", "afford"],
    groups: ["Jobs held by residents, by industry"],
    sections: [
      { type: "group", title: "Industries residents work in", group: "Jobs held by residents, by industry" },
      { type: "taxAreas", title: "Income on tax returns, by tax area" },
      { type: "context", title: "County and state context", ids: ["dotax_median_agi", "per_capita_personal_income", "bls_unemployment_rate"] },
    ],
  },
  {
    id: "housing", label: "Housing",
    blurb: "What housing costs compared with what households earn.",
    metrics: ["median_gross_rent", "rent_burden_rate", "owner_cost_burden_rate",
              "median_household_income", "income_under_50k_share"],
    // Not "hous": it would match "House District".
    keywords: ["housing", "rent", "home", "mortgage", "owner", "shelter", "homeless", "cost of living"],
    sections: [],
  },
  {
    id: "people", label: "Who lives here",
    blurb: "Age, ethnic background and language.",
    metrics: ["share_65_plus", "under_18_share", "nhpi_share", "limited_english_share", "disability_rate"],
    keywords: ["ethnic", "race", "hawaiian", "filipino", "japanese", "asian", "pacific", "hispanic",
               "white", "language", "english", "background", "demographic", "who lives"],
    groups: ["Ethnic background"],
    sections: [
      { type: "group", title: "Ethnic background", group: "Ethnic background" },
    ],
  },
  {
    id: "programs", label: "Program need",
    blurb: "Residents with low incomes compared with the poverty line, and how many use SNAP and Medicaid. These are not eligibility counts.",
    metrics: ["under_125pct_poverty_share", "under_200pct_poverty_share", "poor_households_without_snap_share",
              "low_income_uninsured_rate", "snap_share", "medicaid_share"],
    keywords: ["snap", "food stamp", "medicaid", "med-quest", "medquest", "program", "eligib",
               "qualif", "benefit", "assist", "outreach", "uninsured", "insurance", "enroll", "uptake", "poverty", "low-income", "low income"],
    groups: ["Program need and uptake"],
    sections: [
      { type: "context", title: "SNAP program records (county and state)", ids: ["snap_cases_monthly", "snap_people_monthly"] },
      { type: "note", title: "Programs residents may qualify for",
        text: "Coming soon: state, county and federal programs, with how to apply. Final eligibility is always decided by the program's agency." },
    ],
  },
];

export const presetById = id => PRESETS.find(p => p.id === id) || PRESETS[0];

const plain = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[ʻ'‘]/g, "");

// Pick the report view that best matches a chat answer: the question's words first, then the
// assistant's tool calls (groups and ranked metrics), else the overview.
export function presetFor(question, trace = []) {
  const q = plain(question);
  let best = null, bestHits = 0;
  PRESETS.forEach(p => {
    const hits = (p.keywords || []).filter(k =>
      new RegExp("(^|[^a-z0-9])" + plain(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(q)).length;
    if (hits > bestHits) { best = p; bestHits = hits; }
  });
  if (best) return best.id;
  for (const t of trace) {
    const groups = (t.input && t.input.groups) || [];
    const byGroup = PRESETS.find(p => (p.groups || []).some(g => groups.includes(g)));
    if (byGroup) return byGroup.id;
    const metric = t.input && t.input.metric_id;
    const byMetric = metric && PRESETS.slice(1).find(p => p.metrics.includes(metric));
    if (byMetric) return byMetric.id;
  }
  return "overview";
}

// The district an answer is about: the last one the assistant looked up, else the selected one.
export function districtFor(trace = [], selected = null) {
  for (let i = trace.length - 1; i >= 0; i--) {
    const id = trace[i].input && trace[i].input.district_id;
    if (id && /^(HD|SD)-\d{1,2}$/i.test(id)) return id.toUpperCase();
  }
  return selected;
}
