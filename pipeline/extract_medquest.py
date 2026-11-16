"""Extract Med-QUEST managed-care enrollment by island from the Hawaiʻi Medicaid Enrollment Report.
No network access.

    python pipeline/extract_medquest.py

Reads pipeline/raw/dhs/Website Enrollment Report 2026 20261106.pdf (downloaded by hand from the
Med-QUEST reports page; fingerprint in pipeline/raw/manifest.yaml) with the `pdftotext` tool and
writes pipeline/raw/dhs/medquest_managed_care_by_island_2026.csv: one row per island and month,
plus the report's managed-care total.

Checks before writing: the six islands add up to "MEDICAID MANAGED CARE TOTAL" in every month.
"""

import csv
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DIR = HERE / "raw" / "dhs"
PDF = DIR / "Website Enrollment Report 2026 20261106.pdf"
PDF_SHA256 = "e685237a20dcfcb51271edcf55629bd682ae0bc84212a9b2cf1aefe464c76d82"
OUT = DIR / "medquest_managed_care_by_island_2026.csv"
ISLANDS = ["Oahu", "Kauai", "Hawaii", "Maui", "Molokai", "Lanai"]
TOTAL = "MEDICAID MANAGED CARE TOTAL"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not PDF.exists():
        raise SystemExit(f"Missing {PDF}. Download it by hand (see pipeline/raw/manifest.yaml).")
    if sha256(PDF) != PDF_SHA256:
        raise SystemExit("The report does not match its fingerprint in this script; review it.")
    if not shutil.which("pdftotext"):
        raise SystemExit("Needs the pdftotext tool (poppler; included with Git for Windows).")
    lines = subprocess.run(["pdftotext", "-raw", str(PDF), "-"], capture_output=True,
                           check=True).stdout.decode("utf-8").splitlines()

    report_date = next(m.group(1) for ln in lines if (m := re.search(r"Report Date: (\S+)", ln)))
    header = next(ln for ln in lines if ln.startswith("Managed Care By Program"))
    months = re.findall(r"[A-Z][a-z]{2}-\d{2}", header)
    if len(months) != 12:
        raise SystemExit(f"Expected 12 month columns, got {months}")

    def row(label: str) -> list[int]:
        i = lines.index("Managed Care By Island") if label in ISLANDS else 0
        for ln in lines[i:]:
            if ln.startswith(label + " "):
                nums = re.findall(r"\d[\d,]*", ln[len(label):])
                return [int(n.replace(",", "")) for n in nums]
        raise SystemExit(f"Row {label!r} not found")

    data = {isl: row(isl) for isl in ISLANDS}
    total = row(TOTAL)
    n = len(total)
    if any(len(v) != n for v in data.values()):
        raise SystemExit("Island rows and the total have different numbers of months")
    for k in range(n):
        s = sum(v[k] for v in data.values())
        if s != total[k]:
            raise SystemExit(f"{months[k]}: islands add to {s:,}, total is {total[k]:,}")
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["report_date", "month", "area", "managed_care_enrollment"])
        for k in range(n):
            for isl in ISLANDS:
                w.writerow([report_date, months[k], isl, data[isl][k]])
            w.writerow([report_date, months[k], "TOTAL", total[k]])
    print(f"Report dated {report_date}: {n} months ({months[0]} to {months[n - 1]}); islands add "
          f"up to the total in every month. Wrote {OUT.name}  sha256 {sha256(OUT)}")


if __name__ == "__main__":
    main()
