"""The Know Your District research assistant: Claude answering questions with tools that read
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

from api import main as kyd

load_dotenv()
MODEL = os.getenv("KYD_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("KYD_EFFORT", "medium")
MAX_TOOL_ROUNDS = 10

SYSTEM_PROMPT = """You are the research assistant in Know Your District, a tool for Hawaiʻi state \
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
- Census survey figures have margins of error; mention them for small groups or close comparisons.
- Tax-area figures describe the whole DOTAX tax area, not the district. County context figures \
describe the county, not the district. Say so when you use them.
- Program-need figures (income below the poverty line, households without SNAP, low-income \
uninsured) are not eligibility counts: each program has its own rules and the administering \
agency decides eligibility. The share of households not receiving SNAP is likely overstated, \
because the survey counts fewer SNAP households than DHS records; say so when you use it.
- Program details (eligibility rules, how to apply) are not loaded in this tool yet. If asked, say \
so, describe the relevant population with figures, and suggest checking the agency's official \
site. Do not state eligibility rules or income limits from memory.

Other rules:
- Describe groups of residents, never individuals. Do not infer anything about a specific person.
- Stay nonpartisan: present data without political commentary, opinions on policy, or advice on \
how to vote or campaign.
- Write in plain language for a busy legislator: lead with the answer, keep it short, use a short \
list or small table when it helps. Spell Hawaiian place names with the ʻokina and kahakō.
- If the question does not name a district, use the district selected on the page if one is \
given; otherwise use find_district or ask which district they mean."""


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


def check_district(district_id: str) -> str:
    gid = (district_id or "").strip().upper()
    if not re.fullmatch(r"(HD|SD)-\d{1,2}", gid) or not kyd.query(
            "SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
        raise ValueError(f"Unknown district id {district_id!r}. Use HD-1 to HD-51 or SD-1 to "
                         "SD-25, or call find_district.")
    return gid


# --- Tools ----------------------------------------------------------------------------------

def tool_find_district(args: dict, src: Sources) -> dict:
    q = args["query"].strip()
    p = plain(q)
    out: dict = {"query": q, "matches": []}

    m = re.search(r"\b(house|hd|representative|rep)\b\D*(\d{1,2})\b", p)
    s = re.search(r"\b(senate|sd|senator|sen)\b\D*(\d{1,2})\b", p)
    for found, prefix in ((m, "HD"), (s, "SD")):
        if found:
            gid = f"{prefix}-{int(found.group(2))}"
            if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                out["matches"].append({"district_id": gid, "name": district_name(gid),
                                       "why": "district number"})
    if not out["matches"]:
        n = re.fullmatch(r"(district\s*)?(\d{1,2})", p)
        if n:
            for prefix in ("HD", "SD"):
                gid = f"{prefix}-{int(n.group(2))}"
                if kyd.query("SELECT 1 FROM geography WHERE geo_id = ?", [gid]):
                    out["matches"].append({"district_id": gid, "name": district_name(gid),
                                           "why": "district number (chamber not given)"})

    # DOTAX tax-area names (e.g. "North Shore", "Molokai", "Waianae")
    areas = kyd.query("SELECT area_id, name FROM tax_area")
    hit = [a for a in areas if plain(a["name"]) in p or any(
        len(w) > 3 and w in plain(a["name"]).replace(",", " ").split()
        for w in re.findall(r"[a-z]+", p))]
    for a in hit:
        rows = kyd.query("""SELECT geo_id, district_share, area_share FROM tax_area_district
                            WHERE area_id = ? AND relation = 'overlaps'
                            ORDER BY area_share DESC""", [a["area_id"]])
        out["matches"].append({
            "tax_area": a["name"],
            "why": "DOTAX tax area name; districts listed by how much of the area's land "
                   "they contain (land, not population)",
            "districts": [{"district_id": r["geo_id"], "name": district_name(r["geo_id"]),
                           "share_of_area_land": f"{100 * r['area_share']:.0f}%"}
                          for r in rows]})
    if not out["matches"]:
        out["note"] = ("No match. This tool can find districts by number, and places by DOTAX "
                       "tax-area name (e.g. Oʻahu North Shore, Waiʻanae Coast, Molokaʻi, Kona, "
                       "Hilo). It has no street-address or neighborhood lookup yet.")
    return out


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
    county_name = next((c["county"]["name"] for c in comps if c.get("county")), None)
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
                                        kyd.table_links("B01001,B11001", acs["year"]))},
        "households": {"value": fmt_value(hh, "households"), "moe": fmt_moe(hh_moe, "households")},
        "measures": [],
        "group_notes": {},
    }
    for c in comps:
        if groups and c["group"] not in groups:
            continue
        kind = c["format"]
        cite = src.cite(acs["publisher"], acs["dataset"], acs["year"],
                        f"{district_name(gid)}, {county_name or 'its county'} and the State of "
                        "Hawaiʻi", c["source"]["tables"])
        out["measures"].append({
            "metric_id": c["metric_id"], "label": c["label"], "group": c["group"],
            "district": fmt_value(c["district"]["value"], kind),
            "district_moe": fmt_moe(c["district"]["moe"], kind),
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
                        "DOTAX tax areas (whole areas), matched to districts by land overlap",
                        ta["source"]["tables"], ta["overlap_source"])
        out["tax_areas"] = {
            "applies_to": ta["applies_to"], "caveat": ta["caveat"], "label": ta["label"],
            "period": ta["period"],
            "district_land_in_no_tax_area": f"{100 * ta['district_land_in_no_tax_area']:.1f}%",
            "areas": [{"tax_area": a["name"], "relation": a["relation"],
                       "median_income_on_tax_returns": fmt_value(a["median_agi"], "dollars"),
                       "resident_tax_returns": fmt_value(a["returns"], "returns"),
                       "share_of_district_land_in_area": f"{100 * a['share_of_district_land']:.1f}%",
                       "share_of_area_land_in_district":
                           f"{100 * a['share_of_area_land_in_district']:.1f}%",
                       "cite": cite} for a in ta["areas"]]}
    return out


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
    ids = kyd.query("SELECT geo_id FROM geography WHERE geo_type = ?", [chamber])
    geo_ids = [r["geo_id"] for r in ids]
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
        "state_value": fmt_value(state_v, kind) if by == "share" else None,
        "note": "Neighboring ranks are often within each other's margins of error; treat the "
                "order as approximate.",
        "cite": cite,
        "districts": [{"rank": i + 1, "district_id": g, "name": district_name(g),
                       "value": fmt_value(v, k), "moe": fmt_moe(m, k)}
                      for i, (g, v, m, k) in enumerate(rows[:limit])]}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


DISTRICT_ID = {"type": "string", "description": "District id: HD-1 to HD-51 (House) or SD-1 to "
                                                "SD-25 (Senate)."}
TOOLS = [
    {"name": "find_district", "strict": True,
     "description": "Find district ids from a district number (e.g. 'House 13', 'Senate "
                    "District 7') or a place name that matches a DOTAX tax area (e.g. 'North "
                    "Shore', 'Molokaʻi', 'Waiʻanae', 'Kona'). Use this whenever the user names a "
                    "place or a district you do not have an id for.",
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
                    "within the margin of error. Groups: 'District profile' (age, income, "
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
                    "(2) the DOTAX tax areas that overlap the district (e.g. Oʻahu North Shore), "
                    "with each whole area's median income on tax returns, tax year 2023.",
     "input_schema": _schema({"district_id": DISTRICT_ID}, ["district_id"])},
    {"name": "rank_districts", "strict": True,
     "description": "Rank all House or all Senate districts on one measure, e.g. to find where "
                    "outreach could reach the most people. by='share' ranks the rate; by='count' "
                    "ranks the number of people or households (only for rate measures).",
     "input_schema": _schema({
         "metric_id": {"type": "string", "description": "A metric_id from list_measures."},
         "chamber": {"type": "string", "enum": ["house", "senate"]},
         "by": {"type": "string", "enum": ["share", "count"]},
         "highest_first": {"type": "boolean"},
         "limit": {"type": "integer", "description": "How many districts to return (1-51)."}},
         ["metric_id", "chamber", "by", "highest_first", "limit"])},
]
HANDLERS = {"find_district": tool_find_district, "list_measures": tool_list_measures,
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


def answer(history: list[dict], selected_district: str | None = None) -> dict:
    """history: [{"role": "user"|"assistant", "content": str}, ...], ending with the user's
    question. Returns {answer, sources, trace, stop_reason}."""
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
    note = (f"(District selected on the page: {district_name(selected_district)}, id "
            f"{selected_district}.)" if selected_district else
            "(No district is selected on the page.)")
    messages[-1] = {"role": "user", "content": [{"type": "text", "text": messages[-1]["content"]},
                                                {"type": "text", "text": note}]}

    client = anthropic.Anthropic()
    src = Sources()
    trace: list[dict] = []
    response = None
    for _ in range(MAX_TOOL_ROUNDS):
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
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, is_error = run_tool(block.name, dict(block.input), src)
            trace.append({"tool": block.name, "input": block.input, "error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result,
                            **({"is_error": True} if is_error else {})})
        messages.append({"role": "user", "content": results})

    text = "".join(b.text for b in response.content if b.type == "text").strip() if response else ""
    if response is not None and response.stop_reason == "refusal":
        text = "I can't help with that request. I can answer questions about district data."
    elif response is not None and response.stop_reason == "tool_use":
        text = (text + "\n\n" if text else "") + ("I stopped before finishing because the "
                                                  "question needed too many lookups. Please ask "
                                                  "a narrower question.")
    cited = {sid for group in re.findall(r"\[([^\]]*)\]", text)
             for sid in re.findall(r"\bS\d+\b", group)}
    return {"answer": text,
            "sources": [s for s in src.items if s["id"] in cited],
            "sources_consulted": len(src.items),
            "trace": trace,
            "model": response.model if response else MODEL,
            "stop_reason": response.stop_reason if response else None}
