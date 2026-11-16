"""Extract each district's permanent-resident population from the 2021 Reapportionment Commission
Final Report (Tables 9 and 10). No network access.

    python pipeline/extract_reapportionment.py

Reads pipeline/raw/elections/2021-Reapportionment-Commission-Final-Report-952-pages-February-25-2022.pdf
(400 MB, downloaded by hand, not in Git; fingerprint in pipeline/raw/manifest.yaml) with the
`pdftotext` tool (poppler), and writes pipeline/raw/elections/reapportionment_2021_district_population.csv.

Checks before writing: 51 House and 25 Senate districts, and each chamber's districts add up to the
state permanent resident population stated in the report (1,348,054).
"""

import csv
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DIR = HERE / "raw" / "elections"
PDF = DIR / "2021-Reapportionment-Commission-Final-Report-952-pages-February-25-2022.pdf"
PDF_SHA256 = "5d37fcbc082551100f447285193a4e996daeb33e6e8d2af991cce248f6226c06"
OUT = DIR / "reapportionment_2021_district_population.csv"
ROW = re.compile(r"^\s*(\d{1,2})\s+(\d{1,3},\d{3})\s+(\d{1,3},\d{3})\b")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def number(s: str) -> int:
    return int(s.replace(",", ""))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF}. Download it by hand (see pipeline/raw/manifest.yaml).")
    if sha256(PDF) != PDF_SHA256:
        raise SystemExit("The report does not match its fingerprint in this script; review it.")
    if not shutil.which("pdftotext"):
        raise SystemExit("Needs the pdftotext tool (poppler; included with Git for Windows).")
    text = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", "40", str(PDF), "-"],
                          capture_output=True, check=True).stdout.decode("utf-8", "replace")
    pages = text.split("\f")

    state = re.search(r"State of Hawaii\s+([\d,]+)\s+persons", text)
    if not state:
        raise SystemExit("State permanent resident population not found in the report text")
    state_total = number(state.group(1))

    def table(start: str, end: str, chamber: str, expected: int) -> list[tuple]:
        rows, inside = [], False
        for page_no, page in enumerate(pages, 1):
            for line in page.splitlines():
                if start in line:
                    inside = True
                    continue
                if inside and end in line:
                    inside = False
                if inside:
                    m = ROW.match(line)
                    if m and len(rows) < expected:
                        rows.append((chamber, int(m.group(1)), number(m.group(3)),
                                     number(m.group(2)), page_no))
        districts = [r[1] for r in rows]
        if districts != list(range(1, expected + 1)):
            raise SystemExit(f"{chamber}: expected districts 1-{expected}, got {districts}")
        total = sum(r[2] for r in rows)
        if total != state_total:
            raise SystemExit(f"{chamber}: districts add to {total:,}, report states {state_total:,}")
        print(f"{chamber}: {expected} districts, total {total:,} = state total in the report")
        return rows

    house = table("Table 9 - House Statewide", "Table 10 - Senate Statewide", "house", 51)
    senate = table("Table 10 - Senate Statewide", "permanent resident population base for each",
                   "senate", 25)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["chamber", "district", "permanent_resident_population", "statewide_target",
                    "report_pdf_page"])
        w.writerows(house + senate)
    print(f"Wrote {OUT}  sha256 {sha256(OUT)}")


if __name__ == "__main__":
    main()
