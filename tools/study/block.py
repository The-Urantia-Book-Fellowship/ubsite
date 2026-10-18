"""Read Matthew Block's parallel chart for a paper: what he sets beside each
paragraph, and the sources he names on its first page.

The method is ../explore-tools/blockcol.py's, copied here rather than imported,
as a sibling's code is never put on sys.path: pdftotext's word boxes, the page
split at x = 262 into his column (left) and the paper's (right), and each left
line filed under the last paragraph marker seen on the right.  The endnotes at
the end run the full width, so they come out as one column at the end.

Only ever `pdftotext ... -`: without the dash pdftotext writes NNN.txt beside
the PDF, into ../block-sources, which is a master.
"""

from __future__ import annotations

import hashlib
import html
import re
import subprocess

RE_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>')
SPLIT = 262


def pdftotext(pdf, *args: str) -> str:
    out = subprocess.run(["pdftotext", *args, str(pdf), "-"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"pdftotext {pdf}: {out.stderr}")
    return out.stdout


def verify(pdf, row: dict) -> str | None:
    """None if the PDF is the one the manifest lists, else what is wrong."""
    got = hashlib.sha256(pdf.read_bytes()).hexdigest()
    return None if got == row["sha256"] else f"{pdf.name} is not the manifest's ({got[:12]})"


def sources_page(pdf) -> str:
    """Page 1: the chart's date and its numbered list of sources."""
    return pdftotext(pdf, "-layout", "-f", "1", "-l", "1").strip()


def column(pdf, paper: int) -> dict[str, list[str]]:
    """{'0:1.19': [the lines Block sets beside it], ...}, and '' for what
    stands before the first marker."""
    xml = pdftotext(pdf, "-bbox")
    out: dict[str, list[str]] = {}
    cur = ""
    for page in xml.split("<page ")[1:]:
        lines: dict[int, list] = {}
        for m in RE_WORD.finditer(page):
            lines.setdefault(round(float(m[2]) / 3), []).append((float(m[1]), html.unescape(m[3])))
        for key in sorted(lines):
            ws = sorted(lines[key])
            left = " ".join(w for x, w in ws if x < SPLIT)
            right = " ".join(w for x, w in ws if x >= SPLIT)
            m = re.search(rf"\b({paper}:\d+\.\d+)\b", right)
            if m:
                cur = m.group(1)
            if left.strip() and "SOURCE OR PARALLEL" not in left and not re.fullmatch(r"\d+", left.strip()):
                out.setdefault(cur, []).append(left)
    return out
