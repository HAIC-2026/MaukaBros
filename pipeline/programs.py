"""Program inventory (pipeline/programs.yaml): load it and check it against the saved documents.

Every fact's `quote` must appear in its saved file, and every number in every income table must be
printed in its file. Files are read with the `pdftotext` tool (poppler). Nothing is downloaded.

    python pipeline/programs.py        # prints each problem; exit code 1 if any
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RAW = HERE / "raw"
YAML_PATH = HERE / "programs.yaml"


def load() -> dict:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def norm(s: str) -> str:
    """Lowercase letters and digits only, so line breaks, hyphenation and the ʻokina don't matter."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def file_text(rel: str, cache: dict) -> str:
    if rel not in cache:
        path = RAW / rel
        if not path.exists():
            raise FileNotFoundError(rel)
        if not shutil.which("pdftotext"):
            raise SystemExit("Needs the pdftotext tool (poppler; included with Git for Windows).")
        cache[rel] = subprocess.run(["pdftotext", "-raw", str(path), "-"], capture_output=True,
                                    check=True).stdout.decode("utf-8", "replace")
    return cache[rel]


def printed(value: float, text: str) -> bool:
    """True if the number is printed in the text as a whole number (e.g. $1,989 or 1989) or with
    cents (e.g. 18,360.00 or 662.67)."""
    forms = {f"{value:,.2f}", f"{value:.2f}"}
    if float(value).is_integer():
        forms |= {f"{value:,.0f}", f"{value:.0f}"}
    return any(re.search(rf"(?<![\d,.]){re.escape(f)}(?![\d]|,\d)", text) for f in forms)


def table_values(limits: dict) -> list[float]:
    out = []
    for key, rows in limits.items():
        if key.startswith("by_") and isinstance(rows, dict):
            for v in rows.values():
                out += v.values() if isinstance(v, dict) else (v if isinstance(v, list) else [v])
    return out


def check() -> tuple[int, int, list[str]]:
    """(quotes checked, numbers checked, problems)."""
    data = load()
    cache: dict = {}
    n_quotes = n_numbers = 0
    problems = []

    pg = data["poverty_guidelines"]
    text = file_text(pg["source_file"], cache)
    n_quotes += 1
    if norm(pg["quote"]) not in norm(text):
        problems.append("poverty guidelines: quote not found")
    for v in table_values(pg):
        n_numbers += 1
        if not printed(v, text):
            problems.append(f"poverty guidelines: {v} not printed in the file")

    for p in data["programs"]:
        for f in p["facts"]:
            rel = f.get("file", p["file"])
            n_quotes += 1
            if norm(f["quote"]) not in norm(file_text(rel, cache)):
                problems.append(f"{p['id']}: quote not found in {rel}: {f['quote'][:60]!r}")
        lim = p.get("income_limits")
        if lim:
            rel = lim.get("file", p["file"])
            text = file_text(rel, cache)
            for v in table_values(lim):
                n_numbers += 1
                if not printed(v, text):
                    problems.append(f"{p['id']}: {v} not printed in {rel}")
    return n_quotes, n_numbers, problems


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    q, n, probs = check()
    for p in probs:
        print("PROBLEM:", p)
    print(f"{q} quotes and {n} numbers checked; {len(probs)} problems")
    sys.exit(1 if probs else 0)
