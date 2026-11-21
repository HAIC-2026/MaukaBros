"""Test how the research assistant's tools read the ways people name places and districts.

    python validation/test_lookup.py

Free: runs the tools directly against data/kyd.duckdb, with no model calls. Each case is a
phrasing people actually type (short forms, number words, missing ʻokina, typos, island names,
names shared by several islands) and what find_district, get_district_places, rank_districts and
get_district_profile must return for it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from api import agent  # noqa: E402


def find(q: str) -> dict:
    return agent.tool_find_district({"query": q}, agent.Sources())


def ids(r: dict) -> list:
    return [m.get("district_id") for m in r["matches"] if "district_id" in m]


def names(r: dict) -> list:
    return [m.get("census_place") or m.get("neighborhood") or m.get("tax_area")
            or m.get("island_or_county") or m.get("zip_code") for m in r["matches"]]


def counties(r: dict, name: str) -> list:
    return [m.get("county") for m in r["matches"]
            if (m.get("census_place") or m.get("neighborhood")) == name]


CASES = [
    # District numbers, however they are written
    ("HD-13", lambda: ids(find("HD-13")) == ["HD-13"]),
    ("HD13", lambda: ids(find("HD13")) == ["HD-13"]),
    ("13th House district", lambda: ids(find("13th House district")) == ["HD-13"]),
    ("thirteenth house district", lambda: ids(find("thirteenth house district")) == ["HD-13"]),
    ("Senate District Seven", lambda: ids(find("Senate District Seven")) == ["SD-7"]),
    ("senate twenty-five", lambda: ids(find("senate twenty-five")) == ["SD-25"]),
    ("Rep. district 13", lambda: ids(find("Rep. district 13")) == ["HD-13"]),
    ("HD 7 and SD 12", lambda: ids(find("HD 7 and SD 12")) == ["HD-7", "SD-12"]),
    ("district 7 (chamber not given)", lambda: ids(find("district 7")) == ["HD-7", "SD-7"]),
    ("House 60 does not exist", lambda: ids(find("House 60")) == [None]),
    # Whole-word matching: no substring or generic-word matches
    ("Hanalei is not Hana", lambda: names(find("Hanalei")) == ["Hanalei"]),
    ("Lanai City is not Pearl City", lambda: names(find("Lanai City")) == ["Lanai City"]),
    ("Waianae coast is not Hāmākua Coast", lambda: names(find("Waianae coast")) == ["Waiʻanae Coast"]),
    ("Ewa Beach is not also ʻEwa", lambda: names(find("Ewa Beach")) == ["Ewa Beach"]),
    ("Ewa (3 letters)", lambda: "ʻEwa" in names(find("Ewa"))),
    ("Puna (hyphenated tax area)", lambda: names(find("Puna")) == ["Puna-Kaʻū"]),
    ("Kaʻū", lambda: names(find("Kaʻū")) == ["Puna-Kaʻū"]),
    ("Kāneʻohe with diacritics", lambda: "Kaneohe" in names(find("Kāneʻohe"))),
    # Islands and counties
    ("Big Island lists Hawaiʻi County districts", lambda: all(
        agent.kyd.district_county(d["district_id"]) == "COUNTY-001"
        for m in find("Big Island")["matches"] for d in m["districts"])),
    ("Oahu is the whole island, not the North Shore",
     lambda: {m.get("island_or_county") for m in find("Oahu")["matches"]}
     == {"Oʻahu (the City and County of Honolulu)."}),
    ("Honolulu County is the county, not the town", lambda: all(
        "island_or_county" in m for m in find("Honolulu County")["matches"])),
    ("Kauai is the county, not two tax areas", lambda: all(
        "island_or_county" in m for m in find("Kauai")["matches"])),
    ("neighbor islands", lambda: len(find("neighbor islands")["matches"]) == 2),
    # Names on several islands
    ("Kailua alone: both, with sizes", lambda: {"Hawaiʻi County", "Honolulu County"}
     <= set(counties(find("Kailua"), "Kailua"))
     and all(m.get("residents_2020") for m in find("Kailua")["matches"] if m.get("census_place"))),
    ("Kailua, Oahu", lambda: counties(find("Kailua, Oahu"), "Kailua") == ["Honolulu County"]),
    ("Kailua-Kona", lambda: counties(find("Kailua-Kona"), "Kailua") == ["Hawaiʻi County"]),
    ("Kailua and Hilo keeps every Kailua", lambda: len(counties(find("Kailua and Hilo"), "Kailua")) == 3),
    ("Waimea Kauai", lambda: counties(find("Waimea Kauai"), "Waimea") == ["Kauaʻi County"]),
    ("North Shore Kauai", lambda: names(find("North Shore Kauai")) == ["North Kauaʻi"]),
    # Typos get suggestions, not silence
    ("Kaneohee", lambda: "Kaneohe" in find("Kaneohee").get("did_you_mean", [])),
    ("Wainae", lambda: "Waianae" in find("Wainae").get("did_you_mean", [])),
    ("Mililanii", lambda: "Wahiawā, Mililani" in find("Mililanii").get("did_you_mean", [])),
    ("Mānoa: no match, told to ask for a ZIP", lambda: not find("Mānoa")["matches"]
     and "ZIP" in find("Mānoa")["note"]),
    # ZIP codes
    ("ZIP+4", lambda: names(find("96813-1234")) == ["96813"]),
    # Reverse lookup, county rankings and counts
    ("HD-20 places include Kāhala",
     lambda: "Kāhala" in agent.tool_get_district_places({"district_id": "HD-20"},
                                                        agent.Sources())["neighborhoods_and_villages"]),
    ("Maui-only ranking", lambda: all(
        agent.kyd.district_county(d["district_id"]) == "COUNTY-009"
        for d in agent.tool_rank_districts({"metric_id": "poverty_rate", "chamber": "house",
                                            "by": "share", "highest_first": True, "limit": 51,
                                            "county": "Maui"}, agent.Sources())["districts"])),
    ("profile gives counts for rates", lambda: next(
        m for m in agent.tool_get_district_profile({"district_id": "HD-16", "groups": []},
                                                   agent.Sources())["measures"]
        if m["metric_id"] == "share_65_plus").get("district_count")),
]


def main() -> None:
    failed = 0
    for label, test in CASES:
        try:
            ok = bool(test())
        except Exception as exc:  # a crash is a failure, with its reason
            ok, label = False, f"{label} ({type(exc).__name__}: {exc})"
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {label}")
    print(f"\n{len(CASES) - failed} of {len(CASES)} lookup checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
