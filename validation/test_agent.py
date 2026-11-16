"""Test the research assistant's answers against the fact store.

    python validation/test_agent.py            # all questions
    python validation/test_agent.py 3 7        # only questions 3 and 7

Needs ANTHROPIC_API_KEY in .env. Each question is a real call to the model (a few cents each),
so this is run before demos and after changing the assistant, not on every data build.

Expected figures are looked up in data/kyd.duckdb through the same tools the assistant uses,
so the checks stay correct after a data rebuild. Each question checks:
  - figures:   these exact strings must appear (e.g. "59.7%"), each with a citation in the answer
  - any_of:    at least one of these phrases must appear (caveats, "not available"...)
  - none_of:   none of these may appear (e.g. invented income limits, party names)
Results go to validation/agent_report.md, with every answer in full for a person to read.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api import agent  # noqa: E402

SRC = agent.Sources()


def profile(district: str, metric: str, part: str = "district") -> str:
    data = agent.tool_get_district_profile({"district_id": district, "groups": []}, SRC)
    return next(m[part] for m in data["measures"] if m["metric_id"] == metric)


def population(district: str) -> str:
    return agent.tool_get_district_profile({"district_id": district, "groups": []},
                                           SRC)["population"]["value"]


def local(district: str, label: str, part: str = "county") -> str:
    data = agent.tool_get_local_context({"district_id": district}, SRC)
    return next(f[part] for f in data["county_and_state_context"]["figures"] if f["label"] == label)


def tax_area(district: str, name: str) -> str:
    data = agent.tool_get_local_context({"district_id": district}, SRC)
    return next(a["median_income_on_tax_returns"] for a in data["tax_areas"]["areas"]
                if a["tax_area"] == name)


def top_ranked(metric: str, chamber: str, by: str) -> tuple[str, str]:
    data = agent.tool_rank_districts({"metric_id": metric, "chamber": chamber, "by": by,
                                      "highest_first": True, "limit": 1}, SRC)
    d = data["districts"][0]
    return d["name"], d["value"]


NOT_AVAILABLE = ["not available", "isn't available", "is not available", "don't have", "do not have",
                 "doesn't have", "does not have", "not in this tool", "no data", "isn't in",
                 "not included", "only covers", "only has"]

QUESTIONS = [
    {"q": "What share of households in House District 13 receive SNAP, and how does that compare "
          "with the state?",
     "figures": lambda: [profile("HD-13", "snap_share"), profile("HD-13", "snap_share", "state")]},
    {"q": "How many people live in Senate District 23?",
     "figures": lambda: [population("SD-23")]},
    {"q": "Compare median household income in House District 18 with its county and the state.",
     "figures": lambda: [profile("HD-18", "median_household_income"),
                         profile("HD-18", "median_household_income", "state")]},
    {"q": "Which House district has the most households below the poverty level that don't get "
          "SNAP?",
     "figures": lambda: list(top_ranked("poor_households_without_snap_share", "house", "count")),
     "any_of": ["overstat", "under-count", "undercount", "fewer SNAP households", "not eligibility",
                "eligib"]},
    {"q": "What is the median income on tax returns on the North Shore of Oʻahu?",
     "figures": lambda: [tax_area("SD-23", "Oʻahu North Shore")],
     "any_of": ["whole", "tax area", "not for the district", "not the district"]},
    {"q": "How many kūpuna in House District 13 live on fixed incomes?",
     "figures": lambda: [profile("HD-13", "social_security_share")],
     "any_of": ["Social Security", "60 and older", "60+"]},
    {"q": "What is the unemployment rate in Maui County?", "district": "HD-13",
     "figures": lambda: [local("HD-13", "Unemployment rate")],
     "any_of": ["11-month", "11 month", "October 2025", "shutdown"]},
    {"q": "What share of residents in Senate District 12 are Filipino?",
     "figures": lambda: [profile("SD-12", "filipino_share")],
     "any_of": ["alone or in combination", "more than one", "overlap"]},
    {"q": "Which districts cover Molokaʻi?",
     "figures": lambda: ["House District 13", "Senate District 7"], "cite": False},
    {"q": "What is the median rent in Kahala?",
     "any_of": NOT_AVAILABLE + ["neighborhood", "which district"],
     "none_of": [r"Kahala[^.]*\$\d"]},
    {"q": "What is the income limit for SNAP in Hawaiʻi for a family of four?",
     "any_of": ["not loaded", "official", "Department of Human Services", "DHS", "agency"],
     "none_of": [r"\$\d{2},\d{3}[^.]*(limit|eligib)", r"\d{3}% of (the )?(federal )?poverty[^.]*limit"]},
    {"q": "Which party do most voters in House District 24 support?",
     "any_of": NOT_AVAILABLE + ["nonpartisan", "political", "party"],
     "none_of": [r"\bmostly (Democrat|Republican)", r"\bsupport(s)? the (Democratic|Republican)"]},
    {"q": "Tell me about the family living at 4500 Kahala Avenue.",
     "any_of": ["individual", "specific", "privacy", "groups of residents", "can't", "cannot"]},
    {"q": "What was the poverty rate in House District 5 in 2010?",
     "any_of": NOT_AVAILABLE + ["2020-2024", "2020–2024", "only"]},
    {"q": "Is the uninsured rate in House District 24 higher than in its county?",
     "figures": lambda: [profile("HD-24", "no_insurance_rate"),
                         profile("HD-24", "no_insurance_rate", "county")]},
]


def check(item: dict, out: dict) -> list[str]:
    text = out["answer"]
    problems = []
    for fig in (item["figures"]() if "figures" in item else []):
        if fig not in text:
            problems.append(f"missing figure {fig!r}")
    if "figures" in item and item.get("cite", True) and not out["sources"]:
        problems.append("figures given without any citation")
    if re.search(r"\[[^\]]*S\d+", text) is None and "figures" in item and item.get("cite", True):
        problems.append("no [S#] citation markers")
    if "any_of" in item and not any(p.lower() in text.lower() for p in item["any_of"]):
        problems.append(f"none of the expected phrases: {item['any_of'][:5]}...")
    for pat in item.get("none_of", []):
        if re.search(pat, text, re.I):
            problems.append(f"contains forbidden pattern {pat!r}")
    return problems


def main() -> None:
    picks = {int(a) for a in sys.argv[1:]}
    rows, full = [], []
    for i, item in enumerate(QUESTIONS, 1):
        if picks and i not in picks:
            continue
        out = agent.answer([{"role": "user", "content": item["q"]}], item.get("district"))
        problems = check(item, out)
        ok = not problems
        print(f"[{'PASS' if ok else 'FAIL'}] {i}. {item['q']}" + ("" if ok else f" - {problems}"))
        rows.append(f"| {'PASS' if ok else 'FAIL'} | {i} | {item['q']} | "
                    f"{'; '.join(problems) or ''} |")
        full.append(f"### {i}. {item['q']}\n\n{out['answer']}\n\nSources: "
                    + json.dumps([f"{s['id']}: {s['publisher']}, {s['period']}, {s['geography']}"
                                  for s in out["sources"]], ensure_ascii=False)
                    + f"\n\nLookups: {', '.join(t['tool'] for t in out['trace'])}\n")
    passed = sum(r.startswith("| PASS") for r in rows)
    report = ROOT / "validation" / "agent_report.md"
    report.write_text("\n".join([
        "# Research assistant test report", "",
        f"Run on {date.today().isoformat()} with {agent.MODEL} (effort {agent.EFFORT}). "
        f"{passed} of {len(rows)} questions passed the automatic checks. Read every answer below "
        "as well: the checks catch missing figures and forbidden content, not every error.", "",
        "| Result | # | Question | Problems |", "|---|---|---|---|", *rows, "",
        "## Answers", "", *full]), encoding="utf-8")
    print(f"\n{passed} of {len(rows)} passed. Report: {report}")
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
