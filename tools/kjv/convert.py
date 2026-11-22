"""The King James Version, converted once from The British Study Edition into data/kjv/.

    .venv/bin/python -m tools.kjv.convert            write data/kjv/ (the books and the verses)
    .venv/bin/python -m tools.kjv.convert --check    write nothing; fail unless data/kjv/ is this
                                                    conversion with data/kjv/corrections.tsv applied

The edition carries the whole Authorized Version, a file to a book, tex/Gen.tex
to tex/Rev.tex, added in one commit (7e652d3, 2021-09-21) and never edited
since.  It will not change, so ubsite keeps a copy of its own (Tigran,
2026-11-21: "you can just convert and copy them in whatever format you need
into ubsite"), and from then on that copy is the master: `make kjv` builds
var/kjv.db from data/kjv/ alone, and the edition is never read for it again.

Read at the commit build/config.py resolves the study edition to, through build/readers/_io
(the only module that may open a source path), the books in the order the
edition's own urantia-study-edition.tex includes them.  What each file holds,
and all that this takes:

  \\bibbook{title}{head}{name}{abbr}   the book's title page, name and abbreviation
  \\vs Abbr C:V text                  a verse, a line to each
  \\fn{...}                           the translators' marginal note, on the line
                                     after its verse, at most one to a verse
  \\bibtheend{...}                    "THE END OF THE PROPHETS." (Mal), "THE END." (Rev)

In a verse or a note only \\bibemph{...}, the words the translators supplied,
set in italic, and \\textsc{...}, the LORD in small capitals, are kept.  What
only the printed page needs goes: \\- (19 hints of where a word may break,
several of them wrong, "weig\\-hed", "Eve\\-ry"), \\tunemarkup{pgauraone}{\\linebreak}
at 1Ch 1:3, \\enlargethispage*{\\baselineskip} (Tit, Phi).  Anything else fails,
so that nothing is passed over unseen (trap 1: the edition's macros are its
own, never the press's).

data/kjv/corrections.tsv lists the slips mended in the copy, each with its
witness; they are applied here, after the conversion, so that --check proves
data/kjv/ is the edition's text and those corrections, and nothing else.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import config                       # noqa: E402
from build.readers import _io                  # noqa: E402

OUT = ROOT / "data" / "kjv"
MAIN = "urantia-study-edition.tex"

RE_VS = re.compile(r"\\vs ([1-3]?[A-Z][a-z]{1,2}) (\d+):(\d+) (.*)")
RE_FN = re.compile(r"\\fn\{(.*)\}")
RE_THEEND = re.compile(r"\\bibtheend\{([^{}]*)\}")
# The print-only lines and pieces, dropped whole.
DROP_LINES = {r"\enlargethispage*{\baselineskip}"}
DROP_PIECES = (r"\tunemarkup{pgauraone}{\linebreak}", r"\-")
# What a verse or a note may hold once those are gone.
RE_KEPT = re.compile(r"\\(?:bibemph|textsc)\{[^{}\\]*\}")
ROMAN = {"I": "1", "II": "2", "III": "3"}
FIELDS = ("chapter", "verse", "pilcrow", "head", "text", "after", "note")


def bibbook(line: str, where: str) -> tuple[str, str, str, str]:
    """`\\bibbook{title}{head}{name}{abbr}` -> (title, head, name, abbr): four
    groups balanced by braces, the title's own macros kept for the build."""
    if not line.startswith("\\bibbook{"):
        raise SystemExit(f"{where}: the first line is no \\bibbook: {line[:60]}")
    args, i = [], len("\\bibbook")
    while len(args) < 4:
        if line[i] != "{":
            raise SystemExit(f"{where}: \\bibbook's argument {len(args) + 1} is not braced")
        depth, j = 0, i
        while True:
            depth += {"{": 1, "}": -1}.get(line[j], 0)
            if depth == 0:
                break
            j += 1
        args.append(line[i + 1:j])
        i = j + 1
    if line[i:].strip():
        raise SystemExit(f"{where}: after \\bibbook: {line[i:]!r}")
    return tuple(args)                         # type: ignore[return-value]


def title_lines(tex: str, where: str) -> str:
    """The title page's lines, as `line \\\\ line \\\\ \\bibtitlemain{main}`: the
    size commands and the space between lines dropped, the case as written
    (the edition sets the lines in small capitals and the main one in capitals)."""
    t = re.sub(r"\\\\(\[\d+pt\])?", r" \\\\ ", tex)
    t = re.sub(r"\\(?:Large|LARGE|large|huge)\b\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    rest = re.sub(r"\\bibtitlemain\{[^{}]*\}|\\\\", "", t)
    if "\\" in rest or "{" in rest or "}" in rest:
        raise SystemExit(f"{where}: a title holds what is not kept: {tex!r}")
    return t


def ref_name(name: str) -> str:
    """The name a reference writes: 1 John for the KJV's I John, Song of
    Solomon and Acts without their article."""
    first, _, rest = name.partition(" ")
    if first in ROMAN:
        return f"{ROMAN[first]} {rest}"
    if name.startswith("The "):
        return name[4:]
    return name


# Whoever made the edition's copy ended every gloss of a note with a full stop,
# also where the gloss already ended in one, or in a question: "etc..",
# "Heb. lip..", "or, thoughts?." (1Ki 18:21).  The stop doubled is taken out,
# in the notes alone, never an ellipsis ("the light from...:"); the counts are
# held, so that nothing else is ever taken for one.
RE_DOUBLED = re.compile(r"(?<!\.)\.\.(?!\.)|(?<=[?!])\.")
STOPS = {"..": 9, "?.": 117}


def stops(note: str, tally: collections.Counter) -> str:
    def one(m):
        tally[".." if m[0] == ".." else "?."] += 1
        return "." if m[0] == ".." else ""
    return RE_DOUBLED.sub(one, note)


def clean(s: str, where: str) -> str:
    for piece in DROP_PIECES:
        s = s.replace(piece, "")
    s = s.strip()
    left = RE_KEPT.sub("", s)
    if "\\" in left or "{" in left or "}" in left or "\t" in s:
        raise SystemExit(f"{where}: holds what is not kept: {s!r}")
    if "  " in s or s != s.strip():
        raise SystemExit(f"{where}: stray space: {s!r}")
    return s


def convert() -> tuple[list[dict], dict[str, list[dict]], dict]:
    study = config.load()["study"]
    rev = study["at"]
    main = _io.read_tex(study["path"], MAIN, rev)
    if main is None:
        raise SystemExit(f"{MAIN} not found at {rev}")
    start = main.index("\\switchtobible")
    order, testament = [], None
    for m in re.finditer(r"\\bibpart\{[^}]*\}\{[^}]*\}\{(OT|NT)\}|\\include\{tex/([^}]+)\}", main[start:]):
        if m[1]:
            testament = m[1]
        else:
            order.append((m[2], testament))
    if len(order) != 66:
        raise SystemExit(f"{MAIN}: {len(order)} books after \\switchtobible, not 66")
    names = [f"{a}.tex" for a, _ in order]
    texts = _io.read_tex_many(study["tex"], names, rev)
    books, verses, digests, tally = [], {}, {}, collections.Counter()
    for n, (abbr, test) in enumerate(order, 1):
        where = f"tex/{abbr}.tex"
        src = texts[f"{abbr}.tex"]
        if src is None:
            raise SystemExit(f"{where}: not found at {rev}")
        digests[abbr] = hashlib.sha256(src.encode("utf-8")).hexdigest()
        lines = src.split("\n")
        if lines[-1] == "":
            lines.pop()
        title, head, name, babbr = bibbook(lines[0], where)
        if babbr != abbr:
            raise SystemExit(f"{where}: \\bibbook names {babbr}")
        rows, end = [], ""
        for k, line in enumerate(lines[1:], 2):
            at = f"{where}:{k}"
            if line in DROP_LINES:
                continue
            if m := RE_VS.fullmatch(line):
                if m[1] != abbr:
                    raise SystemExit(f"{at}: \\vs names {m[1]}")
                rows.append({"chapter": int(m[2]), "verse": int(m[3]), "pilcrow": "", "head": "",
                             "text": clean(m[4], at), "after": "", "note": ""})
            elif m := RE_FN.fullmatch(line):
                if not rows or rows[-1]["note"]:
                    raise SystemExit(f"{at}: a \\fn with no verse of its own before it")
                rows[-1]["note"] = stops(clean(m[1], at), tally)
            elif m := RE_THEEND.fullmatch(line):
                end = m[1]
            else:
                raise SystemExit(f"{at}: a line of no kind: {line[:60]!r}")
        books.append({"n": n, "abbr": abbr, "testament": test, "name": name,
                      "ref_name": ref_name(name), "head": head,
                      "title": title_lines(title, where), "end": end})
        verses[abbr] = rows
    if dict(tally) != STOPS:
        raise SystemExit(f"the doubled stops: {dict(tally)}, where {STOPS} were taken out (2026-11-21)")
    return books, verses, {"repo": str(study["path"].relative_to(ROOT.parent)),
                           "commit": study["commit"], "digests": digests}


def corrections() -> list[dict]:
    """data/kjv/corrections.tsv: book, chapter, verse, field (text or note),
    was, is, why.  Each `was` must stand exactly once in its field."""
    path = OUT / "corrections.tsv"
    if not path.exists():
        return []
    rows = path.read_text(encoding="utf-8").split("\n")
    head = rows[0].split("\t")
    if head != ["book", "chapter", "verse", "field", "was", "is", "why"]:
        raise SystemExit(f"{path.name}: header {head}")
    out = []
    for k, r in enumerate(rows[1:], 2):
        if not r:
            continue
        b, c, v, f, was, is_, why = r.split("\t")
        if f not in ("text", "note"):
            raise SystemExit(f"{path.name}:{k}: field {f!r}")
        out.append({"book": b, "chapter": int(c), "verse": int(v), "field": f,
                    "was": was, "is": is_, "why": why, "line": k})
    return out


def apply(verses: dict[str, list[dict]], fixes: list[dict]) -> None:
    for fx in fixes:
        row = next((r for r in verses.get(fx["book"], ())
                    if (r["chapter"], r["verse"]) == (fx["chapter"], fx["verse"])), None)
        if row is None:
            raise SystemExit(f"corrections.tsv:{fx['line']}: no {fx['book']} {fx['chapter']}:{fx['verse']}")
        if fx["was"] == "" and row[fx["field"]] != "":
            raise SystemExit(f"corrections.tsv:{fx['line']}: an empty `was` sets a field that is "
                             f"empty, and {fx['book']} {fx['chapter']}:{fx['verse']}'s {fx['field']} is not")
        if fx["was"] and row[fx["field"]].count(fx["was"]) != 1:
            raise SystemExit(f"corrections.tsv:{fx['line']}: {fx['was']!r} is not once in "
                             f"{fx['book']} {fx['chapter']}:{fx['verse']}'s {fx['field']}")
        row[fx["field"]] = row[fx["field"]].replace(fx["was"], fx["is"])


def witness() -> list[dict]:
    """data/kjv/witness.tsv (tools/kjv/merge.py): what the copy takes from the
    1769 witness, by Tigran's rulings of 2026-11-21."""
    path = OUT / "witness.tsv"
    if not path.exists():
        return []
    rows = path.read_text(encoding="utf-8").split("\n")
    if rows[0].split("\t") != ["book", "chapter", "verse", "field", "value", "why"]:
        raise SystemExit(f"{path.name}: header {rows[0]!r}")
    out = []
    for k, r in enumerate(rows[1:], 2):
        if r:
            b, c, v, f, val, why = r.split("\t")
            out.append({"book": b, "chapter": int(c), "verse": int(v), "field": f, "value": val, "line": k})
    return out


def take(verses: dict[str, list[dict]], rows: list[dict]) -> None:
    """Apply witness.tsv: a pilcrow set; a title split off the head of its
    verse, a subscription off its end, each where the verse has its words; a
    note replaced or set."""
    for w in rows:
        at = f"witness.tsv:{w['line']}"
        row = next((r for r in verses.get(w["book"], ())
                    if (r["chapter"], r["verse"]) == (w["chapter"], w["verse"])), None)
        if row is None:
            raise SystemExit(f"{at}: no {w['book']} {w['chapter']}:{w['verse']}")
        f, val = w["field"], w["value"]
        if f == "pilcrow" and val == "¶" and not row["pilcrow"]:
            row["pilcrow"] = val
        elif f == "head" and row["text"].startswith(val + " ") and not row["head"]:
            row["head"], row["text"] = val, row["text"][len(val) + 1:]
        elif f == "after" and row["text"].endswith(" " + val) and not row["after"]:
            row["after"], row["text"] = val, row["text"][:-len(val) - 1]
        elif f == "note" and val and val != row["note"]:
            row["note"] = val
        else:
            raise SystemExit(f"{at}: {f} {val[:40]!r} does not apply to "
                             f"{w['book']} {w['chapter']}:{w['verse']}")


BOOK_FIELDS = ("n", "abbr", "testament", "name", "ref_name", "head", "title", "end")


def files(books, verses, src) -> dict[str, str]:
    out = {"books.tsv": "\t".join(BOOK_FIELDS) + "\n"
           + "".join("\t".join(str(b[f]) for f in BOOK_FIELDS) + "\n" for b in books)}
    for b in books:
        out[f"{b['abbr']}.tsv"] = "\t".join(FIELDS) + "\n" + "".join(
            "\t".join(str(r[f]) for f in FIELDS) + "\n" for r in verses[b["abbr"]])
    out["SOURCE.tsv"] = ("repository\tcommit\n" + f"{src['repo']}\t{src['commit']}\n\n"
                         + "file\tsha256\n"
                         + "".join(f"tex/{a}.tex\t{d}\n" for a, d in src["digests"].items()))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    books, verses, src = convert()
    apply(verses, corrections())
    take(verses, witness())
    want = files(books, verses, src)
    if args.check:
        bad = [n for n, t in want.items()
               if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
        extra = sorted(p.name for p in OUT.glob("*.tsv")
                       if p.name not in want and p.name not in ("corrections.tsv", "witness.tsv", "marks.tsv"))
        for n in bad:
            print(f"  data/kjv/{n} differs from the conversion")
        for n in extra:
            print(f"  data/kjv/{n} is no file of the conversion")
        if not bad and not extra:
            print(f"data/kjv/: the edition's KJV at {src['commit'][:7]}, "
                  f"{len(corrections())} corrections and {len(witness())} lines of the 1769 witness "
                  f"applied, and nothing else")
        return 1 if bad or extra else 0
    OUT.mkdir(exist_ok=True)
    for n, t in want.items():
        (OUT / n).write_text(t, encoding="utf-8")
    nv = sum(len(r) for r in verses.values())
    nn = sum(1 for r in verses.values() for x in r if x["note"])
    print(f"data/kjv/: {len(books)} books, {nv:,} verses, {nn:,} notes, "
          f"from {src['repo']} at {src['commit'][:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
