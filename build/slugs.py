"""Slugs are data, not a function.

`data/slugs.tsv` is checked in and append-only: a headword keeps the slug it was
first given, for ever.  If the slugifier is later improved, existing URLs must
not move -- a permalink that changes because someone tidied a regex is a broken
permalink, and this corpus is meant to be cited.

Collisions get an explicit numeric suffix recorded in the ledger, so the
disambiguation is a decision on the record rather than an accident of ordering.
"""

from __future__ import annotations

import pathlib
import re
import unicodedata

LEDGER = pathlib.Path(__file__).resolve().parent.parent / "data" / "slugs.tsv"


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "").replace("'", "")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "entry"


def load() -> dict[str, str]:
    if not LEDGER.exists():
        return {}
    out = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        head, slug = line.split("\t")
        out[head] = slug
    return out


def assign(headwords, report) -> dict[str, str]:
    """Return {headword: slug}, extending the ledger for anything new."""
    ledger = load()
    used = set(ledger.values())
    added = []
    for head in headwords:                       # caller supplies a stable order
        if head in ledger:
            continue
        base = slugify(head)
        slug, n = base, 1
        while slug in used:
            n += 1
            slug = f"{base}-{n}"
        ledger[head] = slug
        used.add(slug)
        added.append((head, slug))
    if added:
        LEDGER.parent.mkdir(exist_ok=True)
        new = not LEDGER.exists()
        with open(LEDGER, "a", encoding="utf-8") as fh:
            if new:
                fh.write("# headword\tslug -- APPEND ONLY. An existing row is a "
                         "published URL and must never change.\n")
            for head, slug in added:
                fh.write(f"{head}\t{slug}\n")
    return ledger
