"""The Russian Synodal Bible, converted once from Tigran's edition into data/rsb/.

    .venv/bin/python -m tools.rsb.convert            write data/rsb/ (the books and the verses)
    .venv/bin/python -m tools.rsb.convert --check    write nothing; fail unless data/rsb/ is this
                                                    conversion with data/rsb/corrections.tsv applied

The edition (config.rsb(), Tigran's repository; Bibles.org.uk, made
by Tigran Aivazian and Vladimir Volovich) carries a book to a file, tex/Gen.tex
and so on, its text unchanged since 2016.  As the KJV's was (Tigran,
2026-11-21: "you can just convert and copy them in whatever format you need
into ubsite"), it is converted once, and from then on data/rsb/ is the master:
the build reads data/rsb/ alone, and the edition is never read for it again.

Read at the commit build/config.py rsb() resolves, through build/readers/_io
(the only module that may open a source path), the books in the order the
edition's own russian-synodal-bible.tex includes them between its Old
Testament's \\bibpart and its "Апокрифа": the 66 and the eleven the Synodal
prints as non-canonical, marked * in its contents (Tigran, 2026-11-21: "Synodal
as printed").  Not its Acts 29, Sonnini's "lost chapter", which no Synodal
Bible has, nor the appendix of apocrypha after it.  What each file holds:

  \\bibbookdescr{Abbr}{inline=..., toc=..., abbr=...}   the title page, the
                                    contents' name (* non-canonical), the abbreviation
  [\\rsbpar]\\vs Abbr C:V text        a verse, a line to each; \\rsbpar opens a paragraph
  \\vs 3Ez 7:(36) text               the 70 verses 3 Ezra numbers in brackets
                                    between 7:35 and 7:36, kept as written
  \\chhdr{...}                        a heading over the next verse (2Ch 37, Sir's prologue)

In a verse only \\bibemph{...}, the words supplied, set in italic,
\\fns{...}, a note at its place, and \\rsbpar where a paragraph opens inside
a verse (twelve of them, Gen 35:22), are kept as macros.  What TeX writes for a
character becomes the character: \\acc{о} о and U+0301, the stress; <<, >> « »;
~--- a no-break space and an em dash; -- an en dash, in notes; \\dots, an
ellipsis.  What only the printed page needs goes: \\- (seven hints of where a
word may break).  Anything else fails, so that nothing is passed over unseen.

data/rsb/corrections.tsv lists the slips mended in the copy, each with its
reason; they are applied here, after the conversion, so that --check proves
data/rsb/ is the edition's text and those corrections, and nothing else.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import config                       # noqa: E402
from build.readers import _io                  # noqa: E402

OUT = ROOT / "data" / "rsb"
MAIN = "russian-synodal-bible.tex"

RE_VS = re.compile(r"(\\rsbpar)?\\vs ([1-3]?[A-Z][a-z]{1,2}) (\d+):(\d+|\(\d+\))(?: (.*))?")
RE_CHHDR = re.compile(r"\\chhdr\{(.*)\}")
# What a verse, a heading or a note may hold once the characters are made.
RE_KEPT = re.compile(r"\\bibemph\{[^{}\\]*\}|\\rsbpar(?= )")
RE_FNS = re.compile(r"\\fns\{([^{}]*(?:\\bibemph\{[^{}\\]*\}[^{}]*)*)\}")
FIELDS = ("chapter", "verse", "pilcrow", "head", "text")
BOOK_FIELDS = ("n", "abbr", "group", "name", "ref", "title")
NBSP = "\u00a0"
ACUTE = "\u0301"


def chars(s: str) -> str:
    """TeX's spellings of characters made the characters."""
    s = s.replace("\\-", "")
    s = re.sub(r"\\acc\{([^{}\\])\}", lambda m: m[1] + ACUTE, s)
    s = s.replace("\\dots\\ ", "… ").replace("\\dots", "…").replace("\\ldots", "…")
    s = s.replace("~---", NBSP + "—").replace("---", "—").replace("--", "–")
    s = s.replace("<<", "«").replace(">>", "»").replace("~", NBSP)
    return s


def clean(s: str, where: str) -> str:
    s = chars(s).strip()
    left = RE_KEPT.sub("", RE_FNS.sub(lambda m: RE_KEPT.sub("", m[1]), s))
    if "\\" in left or "{" in left or "}" in left or "\t" in s:
        raise SystemExit(f"{where}: holds what is not kept: {s!r}")
    if "  " in s:
        raise SystemExit(f"{where}: two spaces: {s!r}")
    return s


def braced(s: str, i: int, where: str) -> tuple[str, int]:
    """The group opening at s[i] == '{': (its contents, the index after it)."""
    if s[i] != "{":
        raise SystemExit(f"{where}: no group at {s[i:i + 20]!r}")
    depth = 0
    for j in range(i, len(s)):
        depth += {"{": 1, "}": -1}.get(s[j], 0)
        if depth == 0:
            return s[i + 1:j], j + 1
    raise SystemExit(f"{where}: a group never closed")


def descr(lines: list[str], abbr: str, where: str) -> tuple[dict, int]:
    """`\\bibbookdescr{Abbr}{ key={...}, ... }` -> ({key: value}, the line after it).
    Lines the edition comments out (%headerleft) are not read."""
    if lines[0] != "\\bibbookdescr{" + abbr + "}{":
        raise SystemExit(f"{where}: the first line is no \\bibbookdescr of {abbr}: {lines[0][:60]}")
    end = lines.index("}")
    body = "\n".join(x for x in lines[1:end] if not x.lstrip().startswith("%"))
    keys, i = {}, 0
    for m in re.finditer(r"\s*(\w+)=", body):
        if m.start() < i:
            continue
        val, i = braced(body, m.end(), where)
        keys[m[1]] = val
        if body[i:i + 1] not in (",", ""):
            raise SystemExit(f"{where}: after {m[1]}: {body[i:i + 10]!r}")
        i += 1
    want = {"inline", "toc", "bookmark", "header", "abbr"}
    if set(keys) != want:
        raise SystemExit(f"{where}: \\bibbookdescr has {sorted(keys)}, not {sorted(want)}")
    return keys, end + 1


def title(inline: str, where: str) -> str:
    """The title page's lines as the KJV's copy writes them, `line \\\\
    \\bibtitlemain{main}`: a line set \\Huge, or at the size the title begins
    with, is main, one set \\LARGE is not; a size holds to the next.  A note
    stays at the end of its line, after the main line's group."""
    lines, main, out = re.split(r"\\\\", chars(inline)), True, []
    for line in lines:
        line = line.strip()
        m = re.match(r"\\(LARGE|Huge)\s*", line)
        if m:
            main, line = m[1] == "Huge", line[m.end():]
        note = ""
        if (k := line.find("\\fns{")) >= 0:
            line, note = line[:k].rstrip(), line[k:]
        if not line or "\\" in line or "{" in line:
            raise SystemExit(f"{where}: a title line of no kind: {line!r}")
        clean(line + note, where)
        out.append((f"\\bibtitlemain{{{line}}}" if main else line) + note)
    return " \\\\ ".join(out)


def book_order(main: str) -> list[tuple[str, str]]:
    """(abbr, group) for the 77, in the edition's order: OT, DC (its contents
    mark them *), NT, from its first \\bibpart to the apocrypha's."""
    start = main.index("\\bibpart{Книги Ветхого Завета")
    stop = main.index("\\bibpart{Апокрифа}")
    order, group = [], None
    for m in re.finditer(r"\\bibpart\{[^}]*(?:\}[^}]*)*?\}\{[^}]*\}\{(OT|NT)\}|\\include\{tex/([^}]+)\}",
                         main[start:stop]):
        if m[1]:
            group = m[1]
        else:
            order.append((m[2], group))
    return order


def convert() -> tuple[list[dict], dict[str, list[dict]], dict]:
    src = config.rsb()
    rev = src["at"]
    main = _io.read_tex(src["path"], MAIN, rev)
    if main is None:
        raise SystemExit(f"{MAIN} not found at {rev}")
    order = book_order(main)
    if len(order) != 77:
        raise SystemExit(f"{MAIN}: {len(order)} books, not 77")
    texts = _io.read_tex_many(src["tex"], [f"{a}.tex" for a, _ in order], rev)
    books, verses, digests = [], {}, {}
    for n, (abbr, group) in enumerate(order, 1):
        where = f"tex/{abbr}.tex"
        text = texts[f"{abbr}.tex"]
        if text is None:
            raise SystemExit(f"{where}: not found at {rev}")
        digests[abbr] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        lines = text.split("\n")
        keys, first = descr(lines, abbr, where)
        name = keys["toc"]
        if name.endswith("*"):
            name, group = name[:-1], "DC" if group == "OT" else None
        if group is None:
            raise SystemExit(f"{where}: a book marked * outside the Old Testament")
        rows, head = [], ""
        for k, line in enumerate(lines[first:], first + 1):
            at = f"{where}:{k}"
            if abbr == "Act" and line.startswith("\\vs Act 29:1 "):
                break                                       # Sonnini's chapter: not the Synodal's
            if not line.strip():
                continue
            if m := RE_CHHDR.fullmatch(line):
                if head:
                    raise SystemExit(f"{at}: two headings over one verse")
                head = clean(m[1], at)
            elif m := RE_VS.fullmatch(line):
                if m[2] != abbr:
                    raise SystemExit(f"{at}: \\vs names {m[2]}")
                if not m[5]:
                    raise SystemExit(f"{at}: a verse with no words")
                rows.append({"chapter": int(m[3]), "verse": m[4], "pilcrow": "¶" if m[1] else "",
                             "head": head, "text": clean(m[5], at)})
                head = ""
            else:
                raise SystemExit(f"{at}: a line of no kind: {line[:60]!r}")
        if head:
            raise SystemExit(f"{where}: a heading over no verse")
        books.append({"n": n, "abbr": abbr, "group": group, "name": chars(name),
                      "ref": chars(keys["abbr"]).replace(NBSP, " "),
                      "title": title(keys["inline"], where)})
        verses[abbr] = rows
    return books, verses, {"repo": str(src["path"].relative_to(ROOT.parent)),
                           "commit": src["commit"], "digests": digests}


def corrections() -> list[dict]:
    """data/rsb/corrections.tsv: book, chapter, verse, field (text or head),
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
        if f not in ("text", "head", "name", "title") or not was:
            raise SystemExit(f"{path.name}:{k}: field {f!r}, or nothing to mend")
        out.append({"book": b, "chapter": c, "verse": v, "field": f,
                    "was": was, "is": is_, "why": why, "line": k})
    return out


def apply(books: list[dict], verses: dict[str, list[dict]], fixes: list[dict]) -> None:
    for fx in fixes:
        if fx["field"] in ("name", "title"):
            row = next((b for b in books if b["abbr"] == fx["book"]), None)
        else:
            row = next((r for r in verses.get(fx["book"], ())
                        if (str(r["chapter"]), r["verse"]) == (fx["chapter"], fx["verse"])), None)
        if row is None:
            raise SystemExit(f"corrections.tsv:{fx['line']}: no {fx['book']} {fx['chapter']}:{fx['verse']}")
        if row[fx["field"]].count(fx["was"]) != 1:
            raise SystemExit(f"corrections.tsv:{fx['line']}: {fx['was']!r} is not once in "
                             f"{fx['book']} {fx['chapter']}:{fx['verse']}'s {fx['field']}")
        row[fx["field"]] = row[fx["field"]].replace(fx["was"], fx["is"])


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


KEPT = ("corrections.tsv", "versification.tsv")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    books, verses, src = convert()
    apply(books, verses, corrections())
    want = files(books, verses, src)
    if args.check:
        bad = [n for n, t in want.items()
               if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
        extra = sorted(p.name for p in OUT.glob("*.tsv") if p.name not in want and p.name not in KEPT)
        for n in bad:
            print(f"  data/rsb/{n} differs from the conversion")
        for n in extra:
            print(f"  data/rsb/{n} is no file of the conversion")
        if not bad and not extra:
            print(f"data/rsb/: the edition's Synodal Bible at {src['commit'][:7]}, "
                  f"{len(corrections())} corrections applied, and nothing else")
        return 1 if bad or extra else 0
    OUT.mkdir(exist_ok=True)
    for n, t in want.items():
        (OUT / n).write_text(t, encoding="utf-8")
    nv = sum(len(r) for r in verses.values())
    nn = sum(len(RE_FNS.findall(x["text"] + x["head"])) for r in verses.values() for x in r)
    print(f"data/rsb/: {len(books)} books, {nv:,} verses, {nn:,} notes in verses, "
          f"from {src['repo']} at {src['commit'][:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
