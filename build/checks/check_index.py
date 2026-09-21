"""Phase 3 gate: every citation parses and reaches a real paragraph, every
cross-reference resolves.

Structural failures here are always fatal.  Counts are reported as a band against
`expectations.toml`, because the index is under active editorial work and its own
EXPECT_ENTRIES moved four times in five commits.
"""

from __future__ import annotations

import pathlib
import sys

VENDOR = pathlib.Path(__file__).resolve().parent.parent.parent / "vendor" / "index"
sys.path.insert(0, str(VENDOR))
import cite   # noqa: E402
import xref   # noqa: E402

RE_PAREN = __import__("re").compile(r"\s*\([^)]*\)")
RE_SEE = __import__("re").compile(r"\s*\bSee(?: also)?\b.*$")


def _clean(s: str) -> str:
    """One chain element, stripped of its citations and trailing See clause.

    Per element -- never on the joined chain, or the parent's `See also ...`
    swallows every descendant's text after it.
    """
    return RE_PAREN.sub("", RE_SEE.sub("", s)).strip()


def path_key(parts) -> str:
    return xref.fold(" ".join(_clean(p) for p in parts))


def check_citations(entries, events, paragraphs, report) -> dict:
    """paragraphs: {(p,s,n)} from the press edition."""
    papers = {p for (p, s, n) in paragraphs}
    sections = {(p, s) for (p, s, n) in paragraphs}
    n_cit = n_target = 0
    by_precision = {"para": 0, "sec": 0, "paper": 0}
    unreachable = []
    for e in list(entries) + list(events):
        for raw in e.cites:
            n_cit += 1
            c = cite.parse(raw)
            if c is None:
                d = cite.diagnose(raw)
                report.hard("citation-unparseable", e.where,
                            f"\\cit{{{raw}}} -- {d}")
                continue
            for p, s, n in c.expand():
                n_target += 1
                if n is not None:
                    by_precision["para"] += 1
                    if (p, s, n) not in paragraphs:
                        unreachable.append((e.where, raw, f"{p}:{s}.{n}"))
                elif s is not None:
                    by_precision["sec"] += 1
                    if (p, s) not in sections:
                        unreachable.append((e.where, raw, f"{p}:{s}sec"))
                else:
                    by_precision["paper"] += 1
                    if p not in papers:
                        unreachable.append((e.where, raw, f"Paper {p}"))
    for where, raw, target in unreachable[:20]:
        report.hard("citation-unreachable", where,
                    f"\\cit{{{raw}}} -> {target} does not exist")
    return {"citations": n_cit, "targets": n_target,
            "by_precision": by_precision, "unreachable": len(unreachable)}


def check_xrefs(az_entries, app_entries, report) -> dict:
    """Resolve every See / See also target against the A-Z headword set.

    `check_tex` builds the head set from A-Z level-1 entries only and passes no
    `paths`, so only the segment before the first colon is verified.  We do the
    same for the fatal gate -- matching the print edition's own contract -- and
    additionally report how many would resolve against real ancestor paths,
    which a database can supply and the print gate cannot.
    """
    heads = {xref.fold(e.headword) for e in az_entries
             if e.level == 1 and e.headword}
    paths = {path_key(e.chain) for e in az_entries}

    n = dangling = strict_only = 0
    for e in list(az_entries) + list(app_entries):
        for kind, target in e.xrefs:
            n += 1
            if xref.resolves(heads, target):
                # The print gate verifies only the segment before the first
                # colon, so "Jesus: events in life: crucifixion" passes on
                # "jesus" alone.  A database has the real ancestor paths, so ask
                # the stricter question: does the WHOLE qualified target name a
                # path that exists?  Reported, never fatal.
                if ":" in target and path_key(target.split(":")) not in paths:
                    strict_only += 1
            else:
                dangling += 1
                report.hard("xref-dangling", e.where,
                            f"\\{kind}{{...}} -> {target!r} resolves to nothing")
    qualified = sum(1 for e in list(az_entries) + list(app_entries)
                    for _k, t in e.xrefs if ":" in t)
    return {"targets": n, "dangling": dangling,
            "qualified": qualified,
            "deep_linkable": qualified - strict_only,
            "headword_only": strict_only}
