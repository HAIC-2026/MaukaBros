"""The District Insight research assistant: Claude answering questions with tools that read
only our validated fact store (data/kyd.duckdb), never the web or the model's memory.

Every figure a tool returns carries a source id such as "S3". The model must cite figures with
those ids, and the API returns the matching source list (publisher, dataset, period, geography,
table links) with each answer, so a reader can check every number.

Configuration (.env): ANTHROPIC_API_KEY (required), KYD_MODEL (default claude-opus-5-5),
KYD_EFFORT (default medium).
"""

import json
import os
import re
import unicodedata

import anthropic
from dotenv import load_dotenv

from api import answer_check
from api import main as kyd

load_dotenv()
MODEL = os.getenv("KYD_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("KYD_EFFORT", "medium")
MAX_TOOL_ROUNDS = 10

SYSTEM_PROMPT = """You are the research assistant in District Insight, a tool for Hawaiʻi state \
legislators and their staff. You describe the people who live in a House or Senate district, \
compare the district with its county and the state, and point out where outreach could help \
residents use programs that already exist.

Rules for figures:
- Every number in your answer must come from a tool result in this conversation turn. Never use \
figures from memory or from earlier answers; call the tools again instead.
- Cite each figure with the source id the tool gave it, in square brackets, e.g. [S2]. Say the \
period (e.g. 2020-2024) and the geography when it is not obvious.
- If the tools do not have something, say plainly that it is not available in this tool's data, \
and say what related figures are available. Do not guess, estimate from general knowledge, or \
fill gaps with typical values.
- Give comparisons, not bare numbers: compare the district with its county and the state. When a \
tool marks a difference as within the margin of error, say it may not be a real difference.
- Census survey figures have margins of error: give the margin with each district survey figure \
you state, e.g. "15.0% (±2.3 points)". Tax and program-record figures have none.
- Cite only source ids a tool returned, and never name the tools in your answer. find_district \
returns no source id: when you use its shares, say in words that they are shares of 2020 Census \
residents.
- Tax-area figures describe the whole DOTAX tax area, not the district. County context figures \
describe the county, not the district. Say so when you use them.
- Program-need figures (income below the poverty line, households without SNAP, low-income \
uninsured) are not eligibility counts: each program has its own rules and the administering \
agency decides eligibility. Survey answers under-count program use (the survey finds about 68% \
of the SNAP households and Med-QUEST members in DHS records), so survey shares receiving SNAP or \
Medicaid are likely understated and the share of households not receiving SNAP is likely \
overstated; say so when you use them. County Med-QUEST and SNAP figures from get_local_context \
are program records.
- For programs, use get_programs: it returns each program's eligibility rules, income limits, how \
to apply, documents to bring and official link, all from saved official documents. Cite them, give \
the official link, and always say that final eligibility is decided by the agency. Never say a \
person or group "is eligible"; say they "may qualify". Do not state rules, limits or programs that \
get_programs does not return; if asked about another program, say it is not in this tool yet and \
suggest the agency's official site. To turn "% of poverty" into dollars, use the HHS Hawaiʻi \
poverty guidelines that get_programs returns.

How to read questions (people type fast, use local words and follow up on earlier answers):
- Answer the most reasonable reading. When one exists, answer it and state your assumption in a \
few words ("Taking this as House District 7; ask if you meant Senate District 7."). Ask a \
question back only when no reading is reasonable, keep it to one sentence, and say what you can \
answer. Never ask more than one question at a time.
- Which district, in this order: one the question names (district, town, neighborhood, ZIP code \
or island; use find_district); one discussed earlier in this conversation when the question \
refers back ("there", "that district", "what about rent?"); the district selected on the page. \
If there is none, ask which district, town or ZIP code they mean.
- A bare number ("district 7") may be House or Senate: use the chamber from the conversation or \
the selected district, otherwise House, and say so.
- A town split across districts: answer for the district with the largest share of its \
residents, say that share, and name the other districts. A name used on several islands \
(Kailua, Waimea): the island the question names, else the larger place; say which.
- Island, county or statewide questions: county and state figures come with every district \
profile, so call get_district_profile for one district in that county (find_district on the \
island name lists them) and give its county or state column, saying it is the county or state \
figure. rank_districts also returns the state figure, and its county option ranks one county's \
districts.
- Local words: kūpuna = older residents (say whether the measure is 60+ or 65+); keiki = \
children under 18; ʻohana = family or household; "food stamps" or EBT = SNAP; QUEST or Medicaid \
= Med-QUEST; Big Island = Hawaiʻi County; neighbor islands = Hawaiʻi, Maui and Kauaʻi counties; \
in Pidgin "stay" often means "live". Loose words map to measures: "poor" or "low-income" to \
poverty and income; "cost of living" or "housing costs" to rent burden, homeowner cost burden \
and median rent; "seniors" to the kūpuna measures; "jobs" or "the economy" to unemployment, \
industries and income. Say which measure you used when the word was loose.
- "How many" questions: give the count (district_count with its margin) and the share.
- Open questions ("How is House District 5 doing?", "What stands out?", "biggest needs"): pick \
the two or three measures where the district differs most from the state beyond the margin of \
error, in either direction.
- "What areas are in my district?" or "Does it include X?": use get_district_places.
- Several questions in one message: answer each one.
- Follow-ups such as "shorter", "as a table", "simpler", "talking points" or "for a newsletter" \
redo your previous answer in that form (call the tools again for its numbers).
- "Why" questions about causes: the data show what, not why. Say so in one clause and give the \
related figures; do not speculate about causes.
- Greetings and thanks: reply in one short sentence, without tools. "What can you do?": say \
you describe the residents of any House or Senate district compared with the county and state, \
rank districts, find the district for a town or ZIP code, and explain programs and how to apply; \
give two example questions. Questions about terms (margin of error, ACS, poverty line, rent \
burden): explain in two or three plain sentences.
- Hypothetical households ("a family of three earning $4,000 a month") are fine: compare with the \
published limits from get_programs, say they may qualify, that the agency decides, and how to \
apply. Looking up or guessing about a named or real person is not.

When the data cannot answer:
- Say so in one sentence, then give the closest figures the tools do have. Do not stop at "not \
available". Where it helps, name who publishes it, without giving their figures yourself: who \
represents a district, bills and hearings: the Legislature's website (capitol.hawaii.gov); \
election results and voter registration: the State Office of Elections; homelessness: the \
Point-in-Time counts (Partners in Care on Oʻahu, Bridging the Gap on the neighbor islands); \
crime: the Department of the Attorney General; schools: the Hawaiʻi State Department of \
Education; programs not in get_programs: the administering agency.
- District survey figures cover one period (2020-2024), so there are no trends over time: say so \
and give the current figures compared with the county and state.

Other rules:
- Describe groups of residents, never individuals. Do not infer anything about a specific person.
- Stay nonpartisan: present data without political commentary, opinions on policy, or advice on \
how to vote or campaign. Factual talking points and summaries for a legislator's office are fine.
- Use neutral words for differences (higher, lower, about the same). Do not label a district or \
its residents (struggling, distressed, wealthy, affluent, poor, high-need, underserved).
- Write in plain language for a busy legislator. Lead with the answer and keep it short: at most \
about four sentences, or up to five short bullet points. Give the two or three figures that \
answer the question, not every related figure. State each required caveat once, in a short \
clause, not a paragraph. Do not use tables unless the user asks for one. These are defaults: \
follow the user's own requests for format and length. \
The page shows a link under your answer to a full district report with every figure, comparison \
and source, so you can end with "The full report has more detail." instead of listing more. \
Spell Hawaiian place names with the ʻokina and kahakō."""


# --- Source registry ------------------------------------------------------------------------

class Sources:
    """Numbers each distinct source as S1, S2, ... for one answer."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self._keys: dict[str, str] = {}

    def cite(self, publisher: str, dataset: str, period: str, geography: str,
             tables: list[dict] | None = None, note: str | None = None) -> str:
        tables = tables or []
        key = json.dumps([publisher, dataset, period, geography,
                          sorted(t["table_id"] for t in tables), note], ensure_ascii=False)
        if key not in self._keys:
            sid = f"S{len(self.items) + 1}"
            self._keys[key] = sid
            self.items.append({"id": sid, "publisher": publisher, "dataset": dataset,
                               "period": period, "geography": geography, "tables": tables,
                               "note": note})
        return self._keys[key]


# --- Formatting helpers (so the model copies numbers instead of doing arithmetic) -------------

def fmt_value(v: float | None, kind: str) -> str:
    if v is None:
        return "not available"
    if kind == "percent":
        return f"{100 * v:.1f}%"
    if kind == "dollars":
        return f"${v:,.0f}"
    return f"{v:,.0f}"


def fmt_moe(m: float | None, kind: str) -> str | None:
    if m is None:
        return None
    return f"±{100 * m:.1f} percentage points" if kind == "percent" else (
        f"±${m:,.0f}" if kind == "dollars" else f"±{m:,.0f}")


def fmt_diff(ref: dict | None, kind: str) -> str | None:
    d = ref and ref.get("difference")
    if not d:
        return None
    a = d["absolute"]
    if kind == "percent":
        size = f"{abs(100 * a):.1f} percentage points"
    elif kind == "dollars":
        size = f"${abs(a):,.0f}"
    else:
        size = f"{abs(a):,.0f}"
    word = "higher" if a > 0 else "lower" if a < 0 else "the same"
    text = f"{size} {word}" if a else "the same"
    if d.get("relative") is not None and kind == "dollars":
        text += f" ({abs(100 * d['relative']):.0f}% {word})"
    if d.get("within_margin_of_error"):
        text += "; within the margin of error, may not be a real difference"
    return text


def plain(s: str) -> str:
    """Lowercase, without ʻokina, apostrophes or kahakō, for matching place names."""
    s = unicodedata.normalize("NFD", s.lower().replace("ʻ", "").replace("'", "").replace("‘", ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def district_name(geo_id: str) -> str:
    chamber, n = geo_id.split("-")
    return f"{'House' if chamber == 'HD' else 'Senate'} District {n}"


def county_display(name: str | None) -> str | None:
    """Census county name ("Kauai County, Hawaii") in Hawaiian spelling ("Kauaʻi County")."""
    if not name:
        return name
    name = re.sub(r", Hawaii$", "", name)
    return name.replace("Hawaii County", "Hawaiʻi County").replace("Kauai County", "Kauaʻi County")


def check_district(district_id: str) -> str:
    gid = (district_id or "").strip().upper()
    if not re.fullmatch(r"(HD|SD)-\d{1,2}", gid) or not kyd.query(
            "SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
        raise ValueError(f"Unknown district id {district_id!r}. Use HD-1 to HD-51 or SD-1 to "
                         "SD-25, or call find_district.")
    return gid


# --- Tools ----------------------------------------------------------------------------------

_NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_ORDINALS = {"first": "one", "second": "two", "third": "three", "fifth": "five", "eighth": "eight",
             "ninth": "nine", "twelfth": "twelve", "twentieth": "twenty", "thirtieth": "thirty",
             "fortieth": "forty", "fiftieth": "fifty"}


def numbers_to_digits(p: str) -> str:
    """'thirteenth house district', 'senate twenty-five', 'hd13', '13th' -> digits a regex can
    read ('13 house district', 'senate 25', 'hd 13', '13'). Input is plain() text."""
    p = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", r"\1", p)
    p = re.sub(r"\b(hd|sd)(\d)", r"\1 \2", p)
    words = "|".join([*_ORDINALS, *(f"{w}th" for w in _NUMBER_WORDS if w not in
                                    ("zero", "one", "two", "three", "five", "eight", "nine",
                                     "twelve"))])
    p = re.sub(rf"\b({words})\b", lambda m: _ORDINALS.get(m[1], m[1][:-2]), p)
    p = re.sub(rf"\b({'|'.join(_TENS)})[\s-]+({'|'.join(list(_NUMBER_WORDS)[1:10])})\b",
               lambda m: str(_TENS[m[1]] + _NUMBER_WORDS[m[2]]), p)
    return re.sub(rf"\b({'|'.join([*_NUMBER_WORDS, *_TENS])})\b",
                  lambda m: str(_NUMBER_WORDS.get(m[1], _TENS.get(m[1]))), p)


def tokens(s: str) -> str:
    """plain() words separated by single spaces and padded, for whole-word phrase matching."""
    return f" {' '.join(re.findall(r'[a-z0-9]+', plain(s)))} "


# Islands and counties people name instead of a district. Oʻahu is the City and County of
# Honolulu; Kalawao County (Kalaupapa) lies on Molokaʻi and is part of HD-13 and SD-7.
COUNTY_IDS = {"hawaii": "COUNTY-001", "honolulu": "COUNTY-003", "kalawao": "COUNTY-005",
              "kauai": "COUNTY-007", "maui": "COUNTY-009"}
ISLANDS = [
    (["oahu", "honolulu county", "city and county of honolulu", "city county of honolulu"],
     ["COUNTY-003"], "Oʻahu (the City and County of Honolulu)."),
    (["big island", "hawaii island", "island of hawaii", "hawaii county"], ["COUNTY-001"],
     "Hawaiʻi Island (Hawaiʻi County)."),
    (["maui", "maui county"], ["COUNTY-009", "COUNTY-005"],
     "Maui County, which also includes Molokaʻi and Lānaʻi (and Kalawao County at Kalaupapa). "
     "House District 13 and Senate District 7 cover Molokaʻi, Lānaʻi and east Maui; for the "
     "island of Maui alone, say that these districts also cover other islands."),
    (["kauai", "kauai county"], ["COUNTY-007"], "Kauaʻi County (Kauaʻi and Niʻihau)."),
    (["kalawao", "kalaupapa"], ["COUNTY-005"], "Kalawao County (Kalaupapa, on Molokaʻi)."),
    (["neighbor islands", "neighbor island", "outer islands"],
     ["COUNTY-001", "COUNTY-009", "COUNTY-005", "COUNTY-007"],
     "The neighbor islands: Hawaiʻi, Maui (with Molokaʻi and Lānaʻi) and Kauaʻi counties."),
]


def tax_area_phrases(name: str) -> set[str]:
    """Names a DOTAX tax area answers to: the whole name and each part ('Puna-Kaʻū' -> 'puna',
    'kau'; 'Waiʻanae Coast' -> 'waianae'; 'Oʻahu North Shore' -> 'north shore'). Matching whole
    parts, not single words, keeps generic words ('city', 'coast', 'north') from matching."""
    parts = {name, *re.split(r",|&|-|\bto\b", name)}
    out = {tokens(x).strip() for x in parts if tokens(x).strip()}
    for x in list(out):
        if x.endswith(" coast"):
            out.add(x[:-len(" coast")])
        if x.startswith("oahu "):
            out.add(x[len("oahu "):])
    if name == "North Kauaʻi":
        out.add("north shore")  # matches with Oʻahu North Shore; the island word decides
    return out


def tool_find_district(args: dict, src: Sources) -> dict:
    q = args["query"].strip()
    p = numbers_to_digits(plain(q))
    padded = tokens(q)
    out: dict = {"query": q, "matches": []}

    m = re.search(r"\b(house|hd|representatives?|rep)\b\D*?(\d{1,2})\b", p) or re.search(
        r"\b(\d{1,2})\s+(?:state\s+)?(house|hd)\b", p)
    s = re.search(r"\b(senate|sd|senators?|sen)\b\D*?(\d{1,2})\b", p) or re.search(
        r"\b(\d{1,2})\s+(?:state\s+)?(senate|sd)\b", p)
    for found, prefix in ((m, "HD"), (s, "SD")):
        if found:
            n = next(g for g in found.groups() if g.isdigit())
            gid = f"{prefix}-{int(n)}"
            if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                out["matches"].append({"district_id": gid, "name": district_name(gid),
                                       "why": "district number"})
            else:
                out["matches"].append({"district_id": None, "why": f"There is no {gid}: House "
                                       "districts are 1-51 and Senate districts 1-25."})
    if not out["matches"]:
        n = re.fullmatch(r"(?:the\s+)?(?:district\s*(?:number|no)?\s*)?(\d{1,2})", p.strip())
        if n:
            for prefix in ("HD", "SD"):
                gid = f"{prefix}-{int(n.group(1))}"
                if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                    out["matches"].append({"district_id": gid, "name": district_name(gid),
                                           "why": "district number (chamber not given)"})

    def pct(x: float) -> str:
        return "<1%" if x < 0.005 else f"{100 * x:.0f}%"

    def shares(rows: list[dict], key: str) -> list[dict]:
        return [{"district_id": r["geo_id"], "name": district_name(r["geo_id"]),
                 "share_of_residents": pct(r[key])} for r in rows]

    # 5-digit ZIP codes (as Census ZIP code tabulation areas)
    for z in re.findall(r"\b(96\d{3})\b", q):
        rows = kyd.query("""SELECT geo_id, zcta_share FROM zcta_district WHERE zcta = ?
                            ORDER BY zcta_share DESC""", [z])
        out["matches"].append({"zip_code": z, "why": "ZIP code area; districts listed with the "
                               "share of its 2020 residents in each" if rows else
                               "ZIP code not found as a Census ZIP area (it may be a PO-box-only "
                               "ZIP with no residents)", "districts": shares(rows, "zcta_share")})

    # Places, neighborhoods and tax areas, matched as whole words ('Hanalei' must not match
    # 'Hana'). _counties (removed before returning) lets an island name narrow the matches.
    places: list[dict] = []

    # Census places (towns and CDPs), Census spelling without ʻokina, matched ignoring them
    for pl in [pl for pl in kyd.query("SELECT place_fp, name FROM place")
               if tokens(pl["name"]) in padded]:
        rows = kyd.query("""SELECT geo_id, place_share FROM place_district WHERE place_fp = ?
                            ORDER BY place_share DESC""", [pl["place_fp"]])
        # Some names belong to two places (Kailua on Oʻahu and on Hawaiʻi Island; Waimea on Kauaʻi
        # and Hawaiʻi Island), so each match carries its county and size to tell them apart.
        info = kyd.query("""SELECT b.county_geo_id, g.name AS county, sum(b.pop20) AS pop
                            FROM block b JOIN geography g ON g.geo_id = b.county_geo_id
                            WHERE b.place_fp = ? GROUP BY 1, 2 ORDER BY 1""", [pl["place_fp"]])
        places.append({"census_place": pl["name"],
                       "county": ", ".join(county_display(r["county"]) for r in info),
                       "residents_2020": fmt_value(sum(r["pop"] for r in info), "people"),
                       "why": "Census place (town or CDP); districts listed with the share of its "
                              "2020 residents in each. The name is in Census spelling without "
                              "ʻokina or kahakō (Pahoa for Pāhoa); write the Hawaiian spelling.",
                       "districts": shares(rows, "place_share"),
                       "_counties": {r["county_geo_id"] for r in info}})

    # Neighborhoods and villages (USGS GNIS populated places, e.g. Kāhala, Kaimukī) that are not
    # Census places: one official reference point each, placed in the OPSD district shapes.
    # Skip a name already answered above as a Census place in the same county; Waimea on Oʻahu
    # is a GNIS village, while the Waimea Census places are on Kauaʻi and Hawaiʻi Island.
    census_names = {(plain(r["name"]), r["county"]) for r in kyd.query(
        """SELECT DISTINCT p.name, g.name AS county FROM place p JOIN block b USING (place_fp)
           JOIN geography g ON g.geo_id = b.county_geo_id""")}
    named = [n for n in kyd.query("SELECT name, county, house_id, senate_id, feature_id "
                                  "FROM named_place WHERE house_id IS NOT NULL")
             if len(plain(n["name"])) >= 3
             and not any(nm == plain(n["name"]) and plain(n["county"]) in plain(c)
                         for nm, c in census_names)
             and tokens(n["name"]) in padded]
    if named:
        cite = src.cite("U.S. Geological Survey", "Geographic Names Information System (GNIS), "
                        "populated places", "published 2026-11-02",
                        "Official reference point of each named place, located in the State of "
                        "Hawaiʻi's 2022 district boundaries (Office of Planning and Sustainable "
                        "Development)", [],
                        "https://www.usgs.gov/tools/geographic-names-information-system-gnis")
    for n in named:
        places.append({
            "neighborhood": n["name"], "county": f"{n['county']} County",
            "why": "Neighborhood or village with no Census boundary. Its official USGS reference "
                   "point lies in the districts below. Say that this places the neighborhood's "
                   "reference point, and that parts near a district line may be in a neighboring "
                   "district. Write the name as given here (with ʻokina and kahakō).",
            "districts": [{"district_id": n["house_id"], "name": district_name(n["house_id"])},
                          {"district_id": n["senate_id"], "name": district_name(n["senate_id"])}],
            "cite": cite, "_counties": {COUNTY_IDS.get(plain(n["county"]))}})

    # DOTAX tax-area names (e.g. "North Shore", "Molokai", "Waianae Coast")
    for a in kyd.query("SELECT area_id, name FROM tax_area"):
        said = [ph for ph in tax_area_phrases(a["name"]) if f" {ph} " in padded]
        if not said:
            continue
        rows = kyd.query("""SELECT geo_id, area_share FROM tax_area_district
                            WHERE area_id = ? AND area_share > 0 ORDER BY area_share DESC""",
                         [a["area_id"]])
        places.append({"tax_area": a["name"],
                       "why": "DOTAX tax area; districts listed with the share of the area's 2020 "
                              "residents in each",
                       "districts": shares(rows, "area_share"),
                       "_counties": {kyd.district_county(r["geo_id"]) for r in rows},
                       "_phrase": max(said, key=len)})

    # The longest name wins: "Ewa Beach" is the Census place, not also the ʻEwa neighborhood and
    # the "Kapolei, Ewa" tax area; "Lanai City" is not also every place with "City" in it.
    def phrase(x: dict) -> str:
        return x.get("_phrase") or tokens(x.get("census_place") or x.get("neighborhood")).strip()
    island_said = {nm for names, _, _ in ISLANDS for nm in names if f" {nm} " in padded}
    said = {phrase(x) for x in places} | island_said
    places = [x for x in places if not any(
        phrase(x) != y and f" {phrase(x)} " in f" {y} "
        and padded.count(f" {phrase(x)} ") <= padded.count(f" {y} ") for y in said)]

    # A name on several islands takes the island of a place written right next to it: "Kailua
    # Kona" is the Kailua on Hawaiʻi Island ("Kailua and Hilo" is not narrowed).
    by_phrase: dict[str, list[dict]] = {}
    for x in places:
        by_phrase.setdefault(phrase(x), []).append(x)
    for ph, group in by_phrase.items():
        others = set().union(*([x["_counties"] for x in places if phrase(x) != ph and (
            f" {ph} {phrase(x)} " in padded or f" {phrase(x)} {ph} " in padded)] or [set()]))
        if len({c for x in group for c in x["_counties"]}) > 1 and others:
            keep = [x for x in group if x["_counties"] & others]
            if keep:
                places = [x for x in places if phrase(x) != ph or x in keep]

    # An island or county name narrows the places ("Kailua, Oʻahu"); alone ("Big Island",
    # "Maui") it lists the districts there.
    islands = [(ids, label) for names, ids, label in ISLANDS if set(names) & island_said]
    island_ids = {i for ids, _ in islands for i in ids}
    if island_ids and places:
        narrowed = [x for x in places if x["_counties"] & island_ids]
        places = narrowed or places
        if not narrowed:
            out["island_note"] = ("The island named does not hold any of the places matched; "
                                  "check which one the user means.")
    elif islands:
        for ids, label in islands:
            marks = ",".join("?" * len(ids))
            for chamber, col in (("House", "house_id"), ("Senate", "senate_id")):
                rows = kyd.query(f"""SELECT {col} AS geo_id, sum(pop20) AS pop FROM block
                                     WHERE county_geo_id IN ({marks}) GROUP BY 1""", ids)
                total = sum(r["pop"] for r in rows) or 1
                rows = sorted(rows, key=lambda r: int(r["geo_id"].split("-")[1]))
                out["matches"].append({
                    "island_or_county": label, "chamber": chamber,
                    "why": f"Every {chamber} district with residents on {label} Districts listed "
                           "with the share of the island's or county's 2020 residents in each. "
                           "For a county or island figure, get_district_profile for any of these "
                           "districts gives county and state columns.",
                    "districts": shares([{"geo_id": r["geo_id"], "s": r["pop"] / total}
                                         for r in rows], "s")})
    for x in places:
        x.pop("_counties", None)
        x.pop("_phrase", None)
    out["matches"].extend(places)

    if len(places) > 1:
        out["several_places"] = ("More than one place matched. Often they are the same area "
                                 "(a town and the tax area around it). If they are the same name "
                                 "on different islands and the question does not say which, use "
                                 "the one with more residents (usually the Oʻahu one) and say "
                                 "which you used in a few words; do not stop to ask.")
    if not out["matches"]:
        out["note"] = ("No match. This tool finds districts by number, ZIP code, island, Census "
                       "place name (towns and CDPs such as Kaneohe, Hilo, Waianae), USGS "
                       "neighborhood name (e.g. Kāhala, Kaimukī) and DOTAX tax-area name (e.g. "
                       "Oʻahu North Shore, Kona). It has no street-address lookup, and some "
                       "neighborhoods (e.g. Mānoa, Kakaʻako) are not in its lists: ask the user "
                       "for the ZIP code or a nearby town instead of guessing.")
        guesses = spelling_guesses(padded)
        if guesses:
            out["did_you_mean"] = guesses
            out["note"] += (" Names spelled like the query are listed in did_you_mean; if one "
                            "is clearly meant, call find_district with it and say which name "
                            "you used.")
    return out


_KNOWN_NAMES: list[tuple[str, str]] | None = None


def spelling_guesses(padded: str) -> list[str]:
    """Place, neighborhood and tax-area names spelled close to words of the query
    ('kaneohee' -> 'Kaneohe', 'wainae' -> 'Waianae')."""
    import difflib
    global _KNOWN_NAMES
    if _KNOWN_NAMES is None:
        names = ([r["name"] for r in kyd.query("SELECT name FROM place")]
                 + [r["name"] for r in kyd.query("SELECT name FROM named_place")])
        _KNOWN_NAMES = [(tokens(n).strip(), n) for n in names] + [
            (ph, r["name"]) for r in kyd.query("SELECT name FROM tax_area")
            for ph in tax_area_phrases(r["name"])]
    lookup = {}
    for key, name in _KNOWN_NAMES:
        lookup.setdefault(key, name)
    words = padded.split()
    grams = {" ".join(words[i:i + k]) for k in (1, 2, 3) for i in range(len(words) - k + 1)}
    found: list[str] = []
    for g in sorted(grams, key=len, reverse=True):
        if len(g) < 4:
            continue
        for key in difflib.get_close_matches(g, list(lookup), n=3, cutoff=0.8):
            if lookup[key] not in found:
                found.append(lookup[key])
    return found[:5]


def tool_list_measures(args: dict, src: Sources) -> dict:
    return {"measures": [{"metric_id": k, "label": m["label"],
                          "group": m.get("group", "District profile")}
                         for k, m in kyd.ordered_metrics()],
            "group_notes": {g: n for g, n in kyd.METRIC_GROUPS.items() if n}}


def tool_get_district_profile(args: dict, src: Sources) -> dict:
    gid = check_district(args["district_id"])
    geo_type = "house" if gid.startswith("HD") else "senate"
    groups = set(args.get("groups") or [])
    comps = kyd.build_comparisons(gid, geo_type)
    county_name = county_display(next((c["county"]["name"] for c in comps if c.get("county")),
                                      None))
    vals = kyd.fetch_values([gid])[gid]
    pop, pop_moe = vals.get("pop_total", (None, None))
    hh, hh_moe = vals.get("households_total", (None, None))
    acs = comps[0]["source"]
    out = {
        "district_id": gid, "name": district_name(gid), "county": county_name,
        "period": acs["year"],
        "population": {"value": fmt_value(pop, "people"), "moe": fmt_moe(pop_moe, "people"),
                       "cite": src.cite(acs["publisher"], acs["dataset"], acs["year"],
                                        f"{district_name(gid)}",
                                        kyd.table_links("B01001,B11001", acs["year"], [gid]))},
        "households": {"value": fmt_value(hh, "households"), "moe": fmt_moe(hh_moe, "households")},
        **({"official_permanent_resident_population": {
            "value": fmt_value(plan["permanent_residents"], "people"),
            "note": plan["note"],
            "cite": src.cite(plan["source"]["publisher"], plan["source"]["dataset"],
                             "2020 Census base", district_name(gid), [],
                             plan["source"]["page"])}} if (plan := kyd.district_plan(gid)) else {}),
        "measures": [],
        "group_notes": {},
    }
    count_labels = {r["indicator_id"]: r["label"]
                    for r in kyd.query("SELECT indicator_id, label FROM indicator")}
    for c in comps:
        if groups and c["group"] not in groups:
            continue
        kind = c["format"]
        cite = src.cite(acs["publisher"], acs["dataset"], acs["year"],
                        f"{district_name(gid)}, {county_name or 'its county'} and the State of "
                        "Hawaiʻi", c["source"]["tables"])
        # "How many" questions: the count behind a rate (people or households), with its margin.
        num = kyd.MAP_METRICS.get(c["metric_id"], {}).get("numerator")
        cnt, cnt_moe = vals.get(num, (None, None)) if num else (None, None)
        out["measures"].append({
            "metric_id": c["metric_id"], "label": c["label"], "group": c["group"],
            "district": fmt_value(c["district"]["value"], kind),
            "district_moe": fmt_moe(c["district"]["moe"], kind),
            **({"district_count": fmt_value(cnt, "count"),
                "district_count_moe": fmt_moe(cnt_moe, "count"),
                "count_of": count_labels.get(num, c["label"])} if cnt is not None else {}),
            **({"reliability": "LOW RELIABILITY: the margin of error is large compared with the "
                               "estimate (coefficient of variation over 30%). Say so and treat "
                               "the figure with caution."}
               if c["district"].get("low_reliability") else {}),
            "county": fmt_value(c["county"]["value"], kind) if c.get("county") else None,
            "vs_county": fmt_diff(c.get("county"), kind),
            "state": fmt_value(c["state"]["value"], kind),
            "vs_state": fmt_diff(c.get("state"), kind),
            "cite": cite})
        if c["group_note"]:
            out["group_notes"][c["group"]] = c["group_note"]
    return out


def tool_get_local_context(args: dict, src: Sources) -> dict:
    """County/state context and the DOTAX tax areas that overlap the district."""
    gid = check_district(args["district_id"])
    county_id = kyd.district_county(gid)
    out: dict = {"district_id": gid, "name": district_name(gid)}

    def ctx_value(entry: dict | None, unit: str) -> str | None:
        # Context figures are stored as published: a BLS rate of 2.3 means 2.3%, not a fraction.
        if not entry:
            return None
        v = entry["value"]
        return "not available" if v is None else (f"{v:.1f}%" if unit == "percent"
                                                  else fmt_value(v, unit))

    ctx = kyd.build_context(county_id)
    out["county_and_state_context"] = {
        "applies_to": "The county and the state, not this district.",
        "figures": [{
            "label": c["label"], "period": c["period"],
            "county": ctx_value(c.get("county"), c["unit"]),
            "county_note": c["county"]["note"] if c.get("county") else None,
            "state": ctx_value(c.get("state"), c["unit"]),
            "state_note": c["state"]["note"] if c.get("state") else None,
            "caveat": c["caveat"],
            "cite": src.cite(c["source"]["publisher"], c["source"]["dataset"], c["period"],
                             "County and State of Hawaiʻi", c["source"]["tables"],
                             c["source"].get("original_source"))}
            for c in ctx]}

    ta = kyd.build_tax_areas(gid)
    if ta:
        cite = src.cite(ta["source"]["publisher"], ta["source"]["dataset"], ta["period"],
                        "DOTAX tax areas (whole areas), matched to districts by 2020 residents",
                        ta["source"]["tables"], ta["overlap_source"])
        cr = ta.get("credits")
        credits_cite = src.cite(cr["source"]["publisher"], cr["source"]["dataset"], cr["period"],
                                "DOTAX tax areas (whole areas) and the State of Hawaiʻi",
                                cr["source"]["tables"]) if cr else None
        out["tax_areas"] = {
            "applies_to": ta["applies_to"] + (
                " share_of_district_residents_in_area is the part of this district's residents "
                "who live in the area; share_of_area_residents_in_district is the part of the "
                "area's residents who live in this district. Do not swap them."),
            "caveat": ta["caveat"], "label": ta["label"],
            "period": ta["period"],
            "district_residents_in_no_tax_area":
                f"{100 * ta['district_residents_in_no_tax_area']:.1f}%",
            "areas": [{"tax_area": a["name"], "relation": a["relation"],
                       "median_income_on_tax_returns": fmt_value(a["median_agi"], "dollars"),
                       "resident_tax_returns": fmt_value(a["returns"], "returns"),
                       "share_of_district_residents_in_area":
                           f"{100 * a['share_of_district_residents']:.1f}%",
                       "share_of_area_residents_in_district":
                           f"{100 * (a['share_of_area_residents_in_district'] or 0):.1f}%",
                       "cite": cite,
                       **({"returns_claiming_hawaii_eitc": f"{100 * a['eitc_share']:.1f}%",
                           "returns_claiming_food_excise_credit":
                               f"{100 * a['food_excise_share']:.1f}%",
                           "credits_cite": credits_cite} if a.get("eitc_share") is not None
                          and credits_cite else {})} for a in ta["areas"]]}
        if ta.get("credits"):
            out["tax_areas"]["credit_claims_note"] = ta["credits"]["note"]
            out["tax_areas"]["state_returns_claiming_hawaii_eitc"] = (
                f"{100 * ta['credits']['state_eitc_share']:.1f}%")
            out["tax_areas"]["state_returns_claiming_food_excise_credit"] = (
                f"{100 * ta['credits']['state_food_excise_share']:.1f}%")
    return out


def tool_get_district_places(args: dict, src: Sources) -> dict:
    """What is in a district: towns, ZIP codes and neighborhoods (the reverse of find_district)."""
    gid = check_district(args["district_id"])
    col = "house_id" if gid.startswith("HD") else "senate_id"
    total = kyd.query(f"SELECT sum(pop20) AS p FROM block WHERE {col} = ?", [gid])[0]["p"] or 1
    cite = src.cite("U.S. Census Bureau", "2020 Census block population, in the State of "
                    "Hawaiʻi's 2022 district boundaries", "2020 Census", district_name(gid), [],
                    "Blocks assigned to districts with the Census Bureau's block assignment files; "
                    "towns are Census places (incorporated areas and CDPs).")

    def share(n: float) -> str:
        return "<1%" if n / total < 0.005 else f"{100 * n / total:.0f}%"

    places = kyd.query(f"""SELECT p.name, b.county_geo_id, sum(b.pop20) AS pop,
                               max(pd.place_share) AS place_share
                           FROM block b JOIN place p USING (place_fp)
                           LEFT JOIN place_district pd ON pd.place_fp = b.place_fp
                                AND pd.geo_id = b.{col}
                           WHERE b.{col} = ? GROUP BY p.place_fp, p.name, b.county_geo_id
                           HAVING sum(b.pop20) > 0 ORDER BY pop DESC""", [gid])
    in_places = sum(r["pop"] for r in places)
    zips = kyd.query(f"""SELECT zcta, sum(pop20) AS pop FROM block WHERE {col} = ?
                         AND zcta IS NOT NULL GROUP BY 1 HAVING sum(pop20) > 0
                         ORDER BY pop DESC""", [gid])
    named = [r["name"] for r in kyd.query(
        f"SELECT name FROM named_place WHERE {col} = ? ORDER BY name", [gid])]
    counties = [county_display(r["name"]) for r in kyd.query(
        f"""SELECT DISTINCT g.name FROM block b JOIN geography g ON g.geo_id = b.county_geo_id
            WHERE b.{col} = ? ORDER BY 1""", [gid])]
    return {
        "district_id": gid, "name": district_name(gid), "counties": counties,
        "residents_2020_census": fmt_value(total, "people"), "cite": cite,
        "note": "2020 Census counts (not the survey). Town names are in Census spelling without "
                "ʻokina or kahakō; write the Hawaiian spelling. Neighborhoods are USGS named "
                "places whose official reference point lies in the district.",
        "towns": [{"name": r["name"], "district_residents_living_there": fmt_value(r["pop"], "people"),
                   "share_of_district_residents": share(r["pop"]),
                   "share_of_town_in_this_district": f"{100 * (r['place_share'] or 0):.0f}%"}
                  for r in places],
        "district_residents_outside_any_town": share(total - in_places),
        "zip_codes": [{"zip_code": r["zcta"], "share_of_district_residents": share(r["pop"])}
                      for r in zips],
        "neighborhoods_and_villages": named[:60],
        **({"neighborhoods_not_listed": len(named) - 60} if len(named) > 60 else {})}


RANK_COUNTIES = {"Hawaiʻi": "COUNTY-001", "Honolulu": "COUNTY-003", "Kauaʻi": "COUNTY-007",
                 "Maui": "COUNTY-009"}


def tool_rank_districts(args: dict, src: Sources) -> dict:
    metric_id = args["metric_id"]
    metric = kyd.MAP_METRICS.get(metric_id)
    if metric is None:
        raise ValueError(f"Unknown metric_id {metric_id!r}. Call list_measures for valid ids.")
    chamber = args["chamber"]
    if chamber not in ("house", "senate"):
        raise ValueError("chamber must be 'house' or 'senate'")
    by = args.get("by", "share")
    if by == "count" and "numerator" not in metric:
        raise ValueError(f"{metric_id} has no count; rank by 'share' instead.")
    limit = max(1, min(int(args.get("limit", 10)), 51))
    county = args.get("county") or ""
    if county and county not in RANK_COUNTIES:
        raise ValueError(f"county must be one of {sorted(RANK_COUNTIES)} or empty.")
    ids = kyd.query("SELECT geo_id FROM geography WHERE geo_type = ?", [chamber])
    geo_ids = [r["geo_id"] for r in ids]
    if county:
        geo_ids = [g for g in geo_ids if kyd.district_county(g) == RANK_COUNTIES[county]]
    vals = kyd.fetch_values(geo_ids + ["STATE-15"])
    kind = metric["format"]
    rows = []
    for g in geo_ids:
        if by == "count":
            v, m = vals.get(g, {}).get(metric["numerator"], (None, None))
            rows.append((g, v, m, "count"))
        else:
            v, m = kyd.metric_estimate(metric, vals.get(g, {}))
            rows.append((g, v, m, kind))
    rows = [r for r in rows if r[1] is not None]
    rows.sort(key=lambda r: r[1], reverse=args.get("highest_first", True))
    year = kyd.query("SELECT year FROM source WHERE source_id = 'acs5'")[0]["year"]
    tables_ids = ",".join(sorted({t for i in ([metric["value"]] if "value" in metric else
                                               [metric["numerator"], metric["denominator"]])
                                  for t in kyd.query("SELECT table_ids FROM indicator WHERE "
                                                     "indicator_id = ?", [i])[0]["table_ids"]
                                  .split(",")}))
    cite = src.cite("U.S. Census Bureau", "American Community Survey 5-year estimates", year,
                    f"All {chamber.title()} districts and the State of Hawaiʻi",
                    kyd.table_links(tables_ids, year))
    state_v, _ = kyd.metric_estimate(metric, vals.get("STATE-15", {}))
    num_label = (kyd.query("SELECT label FROM indicator WHERE indicator_id = ?",
                           [metric["numerator"]])[0]["label"] if by == "count" else None)
    return {
        "measure": num_label or metric["label"], "ranked_by": by, "chamber": chamber,
        "districts_ranked": (f"{len(geo_ids)} {chamber.title()} districts in {county} County "
                             "(ranks are within the county)" if county else
                             f"all {len(geo_ids)} {chamber.title()} districts"),
        "state_value": fmt_value(state_v, kind) if by == "share" else None,
        "note": "Neighboring ranks are often within each other's margins of error; treat the "
                "order as approximate.",
        "cite": cite,
        "districts": [{"rank": i + 1, "district_id": g, "name": district_name(g),
                       "value": fmt_value(v, k), "moe": fmt_moe(m, k)}
                      for i, (g, v, m, k) in enumerate(rows[:limit])]}


def tool_get_programs(args: dict, src: Sources) -> dict:
    """Programs from pipeline/programs.yaml, optionally with a district's related figures."""
    data = kyd.program_data()
    wanted = set(args.get("program_ids") or [])
    gid = args.get("district_id") or ""
    related: dict[str, list] = {}
    moes: dict[str, float | None] = {}
    if gid:
        gid = check_district(gid)
        geo_type = "house" if gid.startswith("HD") else "senate"
        comps = kyd.build_comparisons(gid, geo_type)
        moes = {c["metric_id"]: c["district"]["moe"] for c in comps}
        built = kyd.build_programs(comps, kyd.build_context(kyd.district_county(gid)), gid)
        related = {p["id"]: p for p in built}
    out = []
    for p in data["programs"]:
        if wanted and p["id"] not in wanted:
            continue
        cite = src.cite(p["agency"], f"{p['name']}: official program information",
                        f"saved {data['checked_on']}", "Program rules (statewide)",
                        [{"table_id": "official page", "url": p["url"]}])
        entry = {"program_id": p["id"], "name": p["name"], "agency": p["agency"],
                 "serves": p["serves"], "official_link": p["url"], "cite": cite,
                 "facts": [{"topic": f["topic"], "text": f["text"]} for f in p["facts"]]}
        if p.get("uptake_note"):
            entry["program_use"] = p["uptake_note"]
        lim = p.get("income_limits")
        if lim:
            key = next(k for k in lim if k.startswith("by_"))
            entry["income_limits"] = {"valid_for": lim["valid_for"], "description": lim["description"],
                                      "unit": lim["unit"], "columns": lim["columns"],
                                      key: {str(k): v for k, v in lim[key].items()}}
        if gid and p["id"] in related:
            r = related[p["id"]]
            acs = kyd.query("SELECT publisher, dataset, year FROM source WHERE source_id = 'acs5'")[0]
            mcite = src.cite(acs["publisher"], acs["dataset"], acs["year"],
                             f"{district_name(gid)} and the State of Hawaiʻi", [])
            entry["in_this_district"] = [{
                "measure": m["label"], "district": fmt_value(m["district"], m["format"]),
                "district_moe": fmt_moe(moes.get(m["metric_id"]), m["format"]) or "not available",
                "state": fmt_value(m["state"], m["format"]), "cite": mcite,
                **({"reliability": "LOW RELIABILITY"} if m["low_reliability"] else {})}
                for m in r["district_measures"]]
            entry["in_this_district_note"] = ("Our link between the program and district figures; "
                                              "not counts of eligible people. State each district "
                                              "figure with its district_moe.")
            le = r.get("likely_eligible")
            if le and le.get("estimated") and le.get("district"):
                d = le["district"]
                le_cite = src.cite(le["source"]["publisher"], le["source"]["dataset"],
                                   le["source"]["year"], f"{district_name(gid)}", [])
                entry["residents_likely_eligible"] = {
                    "district": fmt_value(d["value"], "count"),
                    "district_moe": (("about " if d["moe_status"] == "derived" else "")
                                     + (fmt_moe(d["moe"], "count") or "not available")),
                    **({"reliability": "LOW RELIABILITY"} if d.get("low_reliability") else {}),
                    "cut_used": le["acs_cut"], "likely_direction": le.get("direction_text"),
                    "caveat": le["caveat"], "final_eligibility": le["final_eligibility"],
                    "cite": le_cite}
            elif le and not le.get("estimated"):
                entry["residents_likely_eligible"] = {"not_estimated": le["reason"]}
        out.append(entry)
    pg = data["poverty_guidelines"]
    pg_cite = src.cite(pg["publisher"], pg["title"], "2026", "Hawaiʻi", [{"table_id": "PDF",
                                                                         "url": pg["url"]}])
    return {"note": data["note_on_eligibility"], "programs": out,
            "hhs_poverty_guidelines_hawaii_2026": {
                "unit": pg["unit"], "cite": pg_cite, "caution": pg["quote"],
                "by_household_size": {str(k): {f"{pct}%": v for pct, v in row.items()}
                                      for k, row in pg["by_household_size"].items()}}}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


DISTRICT_ID = {"type": "string", "description": "District id: HD-1 to HD-51 (House) or SD-1 to "
                                                "SD-25 (Senate)."}
TOOLS = [
    {"name": "find_district", "strict": True,
     "description": "Find district ids from a district number (e.g. 'House 13', 'HD13', "
                    "'thirteenth House district', 'Senate District 7'), a ZIP code (e.g. "
                    "'96744'), a town or Census place (e.g. 'Kāneʻohe', 'Hilo', 'Waiʻanae'), a "
                    "neighborhood (e.g. 'Kāhala', 'Kaimukī'), a DOTAX tax area (e.g. 'North "
                    "Shore', 'Kona') or an island or county (e.g. 'Big Island', 'Maui County', "
                    "'neighbor islands'). Places spanning several districts come back with the "
                    "share of their 2020 residents in each. Use this whenever the user names a "
                    "place or a district you do not have an id for. Pass only the place or "
                    "district words (with an island name if given), not the whole question.",
     "input_schema": _schema({"query": {"type": "string",
                                        "description": "The district or place as the user wrote it."}},
                             ["query"])},
    {"name": "list_measures", "strict": True,
     "description": "List every measure available for districts (id, label, group), with notes "
                    "on how each group should be read. Use it to find a metric_id for "
                    "rank_districts or to check whether a topic is covered.",
     "input_schema": _schema({}, [])},
    {"name": "get_district_profile", "strict": True,
     "description": "Census ACS 2020-2024 figures for one district, each compared with its "
                    "county and the state, with margins of error and whether each difference is "
                    "within the margin of error. Rates also come with the count of people or "
                    "households behind them (district_count), for 'how many' questions. The "
                    "county and state columns also answer county-wide and statewide questions. "
                    "Groups: 'District profile' (age, income, "
                    "poverty, housing, insurance, disability, language, families, jobs), "
                    "'Program need and uptake', 'Ethnic background', 'Jobs held by residents, by "
                    "industry'. Leave groups empty for all.",
     "input_schema": _schema({
         "district_id": DISTRICT_ID,
         "groups": {"type": "array", "items": {"type": "string", "enum": list(kyd.METRIC_GROUPS)},
                    "description": "Optional: only these groups. Empty list for all."}},
         ["district_id", "groups"])},
    {"name": "get_local_context", "strict": True,
     "description": "For one district: (1) county and state figures from other sources (DHS "
                    "SNAP program records, DOTAX median income on tax returns, BLS unemployment "
                    "rate, BEA income per person), which describe the county, not the district; "
                    "(2) the DOTAX tax areas the district's residents live in (e.g. Oʻahu North "
                    "Shore), with each whole area's median income on tax returns and the share of "
                    "its returns claiming the Hawaiʻi EITC and food/excise credit (program use), "
                    "tax year 2023, compared with the state; plus county claim counts.",
     "input_schema": _schema({"district_id": DISTRICT_ID}, ["district_id"])},
    {"name": "rank_districts", "strict": True,
     "description": "Rank all House or all Senate districts on one measure, e.g. to find where "
                    "outreach could reach the most people. by='share' ranks the rate; by='count' "
                    "ranks the number of people or households (only for rate measures). Set "
                    "county to rank only that county's districts ('Which Maui district...'). "
                    "Also returns the statewide figure.",
     "input_schema": _schema({
         "metric_id": {"type": "string", "description": "A metric_id from list_measures."},
         "chamber": {"type": "string", "enum": ["house", "senate"]},
         "by": {"type": "string", "enum": ["share", "count"]},
         "highest_first": {"type": "boolean"},
         "limit": {"type": "integer", "description": "How many districts to return (1-51)."},
         "county": {"type": "string", "enum": ["", *RANK_COUNTIES],
                    "description": "Only districts in this county; empty string for all."}},
         ["metric_id", "chamber", "by", "highest_first", "limit", "county"])},
    {"name": "get_district_places", "strict": True,
     "description": "What is in one district: its towns (Census places) with how many of the "
                    "district's 2020 residents live in each, its ZIP codes, neighborhoods and "
                    "villages, and its county. Use for 'what areas are in House District 5?', "
                    "'does SD-12 include Waikīkī?' or to describe where a district is.",
     "input_schema": _schema({"district_id": DISTRICT_ID}, ["district_id"])},
]
TOOLS.append(
    {"name": "get_programs", "strict": True,
     "description": "Programs residents may qualify for (SNAP, Med-QUEST, Hawaiʻi EITC, food/excise "
                    "tax credit, WIC, Kūpuna Care, SSI): who they serve, eligibility rules, income "
                    "limits, how to apply, documents to bring, official link, from saved official "
                    "documents; plus the 2026 HHS poverty guidelines for Hawaiʻi. Give a district_id "
                    "to also get that district's related figures. Leave program_ids empty for all.",
     "input_schema": _schema({
         "district_id": {"type": "string", "description": "Optional district id (HD-n or SD-n); "
                                                          "empty string for none."},
         "program_ids": {"type": "array", "items": {"type": "string", "enum": [
             "snap", "med_quest", "hawaii_eitc", "food_excise_credit", "wic", "kupuna_care",
             "ssi"]}, "description": "Optional: only these programs. Empty list for all."}},
         ["district_id", "program_ids"])})
HANDLERS = {"find_district": tool_find_district, "list_measures": tool_list_measures,
            "get_programs": tool_get_programs, "get_district_places": tool_get_district_places,
            "get_district_profile": tool_get_district_profile,
            "get_local_context": tool_get_local_context, "rank_districts": tool_rank_districts}


def run_tool(name: str, args: dict, src: Sources) -> tuple[str, bool]:
    """(JSON result, is_error)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool {name}"}), True
    try:
        return json.dumps(handler(args, src), ensure_ascii=False), False
    except (ValueError, KeyError, TypeError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False), True


# --- Conversation ---------------------------------------------------------------------------

class AssistantUnavailable(Exception):
    pass


def answer(history: list[dict], selected_district: str | None = None, spend=None) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...], ending with the user's
    question. spend: an api.security.QuestionSpend (or None), checked before every model call.
    Returns {answer, sources, trace, stop_reason, unverified_numbers}."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AssistantUnavailable("The assistant needs ANTHROPIC_API_KEY in .env "
                                   "(see .env.example).")
    if not history or history[-1].get("role") != "user":
        raise ValueError("The last message must be the user's question.")

    messages: list[dict] = [{"role": m["role"], "content": str(m["content"])[:8000]}
                            for m in history[-12:] if m.get("role") in ("user", "assistant")
                            and m.get("content")]
    if messages and messages[0]["role"] != "user":
        messages = messages[1:]
    if not messages or messages[-1]["role"] != "user" or not messages[-1]["content"].strip():
        raise ValueError("The question is empty.")
    note = (f"(District selected on the page: {district_name(selected_district)}, id "
            f"{selected_district}.)" if selected_district else
            "(No district is selected on the page.)")
    messages[-1] = {"role": "user", "content": [{"type": "text", "text": messages[-1]["content"]},
                                                {"type": "text", "text": note}]}

    client = anthropic.Anthropic()
    src = Sources()
    trace: list[dict] = []
    tool_texts: list[str] = []  # every tool result, to check the numbers in the answer against
    response = None
    over_budget = False
    for _ in range(MAX_TOOL_ROUNDS):
        if spend is not None and not spend.allow():
            over_budget = True
            break
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if spend is not None:
            spend.record(response.usage)
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, is_error = run_tool(block.name, dict(block.input), src)
            tool_texts.append(result)
            trace.append({"tool": block.name, "input": block.input, "error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result,
                            **({"is_error": True} if is_error else {})})
        messages.append({"role": "user", "content": results})

    text = "".join(b.text for b in response.content if b.type == "text").strip() if response else ""
    if response is not None and response.stop_reason == "refusal":
        text = ("I can't help with that request. I can describe the residents of any House or "
                "Senate district compared with the county and state, rank districts, find the "
                "district for a town or ZIP code, and explain programs and how to apply.")
    elif over_budget and (response is None or response.stop_reason == "tool_use"):
        text = ("I stopped before finishing because the assistant reached its spending limit. "
                "Please ask a narrower question, or try again later.")
    elif response is not None and response.stop_reason == "tool_use":
        text = (text + "\n\n" if text else "") + ("I stopped before finishing because the "
                                                  "question needed too many lookups. Please ask "
                                                  "a narrower question.")
    # The model sometimes cites as "(S4)" or "(S1, S3)"; the page and the source list below
    # only recognise square brackets, so those figures would lose their source.
    text = re.sub(r"\((S\d+(?:\s*,\s*S\d+)*)\)", r"[\1]", text)
    # It also sometimes "cites" a tool, e.g. "[find_district]", despite the instructions. Tool
    # names mean nothing to readers and are not sources, so drop them.
    tool_names = "|".join(re.escape(t["name"]) for t in TOOLS)
    text = re.sub(rf"\s*\[(?:{tool_names})\]", "", text)
    # Every number the model wrote should appear in what its tools returned (or in the question).
    unverified = answer_check.unverified_numbers(text, tool_texts, [str(history[-1].get("content", ""))])
    cited = {sid for group in re.findall(r"\[([^\]]*)\]", text)
             for sid in re.findall(r"\bS\d+\b", group)}
    return {"answer": text,
            "sources": [s for s in src.items if s["id"] in cited],
            "sources_consulted": len(src.items),
            "trace": trace,
            "model": response.model if response else MODEL,
            "stop_reason": response.stop_reason if response else None,
            "unverified_numbers": unverified}
