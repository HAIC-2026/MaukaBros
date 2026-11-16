"""Read DBEDT's published ACS 2020-2024 district profiles (Data Profiles DP02-DP05) for the
cross-check in validation/validate.py (group H). DBEDT/READ is the challenge champion, so the check
shows that our figures match what DBEDT itself publishes for each House and Senate district.

Files (downloaded by hand from https://census.hawaii.gov/acs/acs-2024/, listed in
pipeline/raw/manifest.yaml): dbedt/acs2024/acs2024_5yr_house_hi.xlsx and ..._senate_hi.xlsx.
Rows are found by their section heading and printed label, never by position.
"""

import re

from context import saved_file, sheet_rows, text

FILES = {"house": "dbedt/acs2024/acs2024_5yr_house_hi.xlsx",
         "senate": "dbedt/acs2024/acs2024_5yr_senate_hi.xlsx"}

# Our indicator id -> (sheet, section heading, row label, compare margin of error too?).
# Only measures with the same definition as ours. Margins of error are compared only where ours is
# the Census-published one (not derived from summing several cells).
MATCHES = {
    "pop_total": ("DP05", "SEX AND AGE", "Total population", True),
    "pop_65_plus": ("DP05", "SEX AND AGE", "65 years and over", False),
    "pop_under_18": ("DP05", "SEX AND AGE", "Under 18 years", True),
    "pop_nhpi": ("DP05", "Race alone or in combination with one or more other races",
                 "Native Hawaiian and Other Pacific Islander", True),
    "pop_hispanic": ("DP05", "HISPANIC OR LATINO AND RACE", "Hispanic or Latino (of any race)", True),
    "households_total": ("DP02", "HOUSEHOLDS BY TYPE", "Total households", True),
    "households_with_65_plus": ("DP02", "HOUSEHOLDS BY TYPE",
                                "Households with one or more people 65 years and over", True),
    "labor_force": ("DP03", "EMPLOYMENT STATUS", "Civilian labor force", True),
    "unemployed": ("DP03", "EMPLOYMENT STATUS", "Unemployed", True),
    "median_household_income": ("DP03", "INCOME AND BENEFITS (IN 2024 INFLATION-ADJUSTED DOLLARS)",
                                "Median household income (dollars)", True),
    "snap_households": ("DP03", "INCOME AND BENEFITS (IN 2024 INFLATION-ADJUSTED DOLLARS)",
                        "With Food Stamp/SNAP benefits in the past 12 months", True),
    "pop_insurance_universe": ("DP03", "HEALTH INSURANCE COVERAGE",
                               "Civilian noninstitutionalized population", True),
    "pop_no_health_insurance": ("DP03", "HEALTH INSURANCE COVERAGE", "No health insurance coverage",
                                False),
    "median_gross_rent": ("DP04", "GROSS RENT", "Median (dollars)", True),
}
HEADER = re.compile(r"^State (House|Senate) District (\d+) \(2024\); Hawaii$")


def parse(cell) -> float | None:
    """'8,619' -> 8619; '±436' -> 436; Census codes such as (X), N, -, ***** -> None."""
    s = text(cell).replace(",", "").replace("±", "").replace("+", "")
    try:
        return float(s)
    except ValueError:
        return None


def load() -> tuple[dict, list[dict]]:
    """({(geo_id, indicator_id): (estimate, moe)}, [file manifest entries])."""
    values, entries = {}, []
    for chamber, rel in FILES.items():
        path, entry = saved_file(rel)
        entries.append(entry)
        cache = {}
        for ind, (sheet, section, label, _) in MATCHES.items():
            rows = cache.setdefault(sheet, sheet_rows(path, sheet))
            header = rows[0]
            districts = {}
            for j, h in enumerate(header):
                m = HEADER.match(text(h))
                if m:
                    if text(rows[1][j]) != "Estimate" or text(rows[1][j + 1]) != "Margin of Error":
                        raise SystemExit(f"{rel} {sheet}: unexpected column labels at {j}")
                    districts[f"{'HD' if m.group(1) == 'House' else 'SD'}-{int(m.group(2))}"] = j
            expected = 51 if chamber == "house" else 25
            if len(districts) != expected:
                raise SystemExit(f"{rel} {sheet}: expected {expected} districts, found "
                                 f"{len(districts)}")
            current, found = "", None
            for r in rows[2:]:
                lab = text(r[0])
                if lab and r[1] is None:
                    current = lab
                elif current == section and lab == label:
                    found = r
                    break
            if found is None:
                raise SystemExit(f"{rel} {sheet}: no row {label!r} under {section!r}")
            for geo_id, j in districts.items():
                values[(geo_id, ind)] = (parse(found[j]), parse(found[j + 1]))
    return values, entries
