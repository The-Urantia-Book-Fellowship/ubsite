"""What data/kjv/ takes from the 1769 witness, by Tigran's rulings: data/kjv/witness.tsv.

    .venv/bin/python -m tools.kjv.merge            write data/kjv/witness.tsv
    .venv/bin/python -m tools.kjv.merge --check    write nothing; fail unless it is what the witness gives

The witness is eBible.org's King James Version, the 1769 text, "Public Domain"
by its own statement ("You may copy the King James Version of the Holy Bible
freely"), the CrossWire Bible Society's and eBible.org's (tools/kjv/compare.py
fetches it).  What it gives the copy (Tigran, 2026-11-21, ruling on
var/kjv/review.md):

  pilcrow  the 1769's paragraph mark, ¶, at the head of the verses it marks
           (2,902, the last at Acts 20:36): "Add them".
  head     a psalm's title, or a letter of Psalm 119, which the edition ran
           into verse 1 and which a printed KJV sets above it: "Set apart".
           The value is the copy's own words, split off the head of its verse
           where the witness's title ends, so the copy's spelling stays.
  after    an epistle's subscription, split off the end of its last verse in
           the same way.
  note     a note of the Old Testament whose words differ from the witness's,
           or one the copy lacks, in the witness's words: "Wording and missing
           notes".  The witness has no notes of the New Testament, so those
           842 are the copy's.  A note that differs only in its stops, its case
           or a name's hyphens is the copy's, and so are the names in every
           note taken: the copy writes Bethel where the 1769 prints Beth-el,
           and Caesar for Cæsar ("Keep as the copy has them").

tools/kjv/convert.py applies this file after data/kjv/corrections.tsv, so
that `convert --check` proves data/kjv/ is the edition, its corrections and
this, and nothing else; and this tool computes it from the edition as
corrected, never from data/kjv/ itself.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import kjvnotes                        # noqa: E402
from tools.kjv import compare as C            # noqa: E402
from tools.kjv import convert as V            # noqa: E402

OUT = ROOT / "data" / "kjv" / "witness.tsv"
# Notes the witness's words are not taken for, each with the reason.
KEEP = {("2Sa", 23, 8): "the witness's third gloss is its own slip, "
                        "\"1ch 11:11 he lift…: from whom he…: Heb. slain\"",
        ("Psa", 120, 3): "the witness's \"what shall is profit thee\" is the slip "
                         "data/kjv/corrections.tsv mends (2026-11-22)"}
FIELDS = ("book", "chapter", "verse", "field", "value", "why")


def witness_raw(usfm: str) -> dict:
    """{(c, v): [note in the witness's own markup]} and the verses' raw
    starts, for the pilcrows: what `compare.witness` flattens."""
    notes, pil = collections.defaultdict(list), set()
    c = 0
    for line in usfm.split("\n"):
        line = line.strip()
        for m in C.RE_F.finditer(line):
            notes[(int(m[1]), int(m[2]))].append(m[3].strip())
        line = C.RE_F.sub("", line)
        tag, _, rest = line.partition(" ")
        if tag == "\\c":
            c = int(rest)
        elif tag == "\\v":
            n, _, text = rest.partition(" ")
            # The mark stands at the verse's head, or at the head of the
            # words of Jesus that open it (`\\wj ¶ Ye are the salt`).
            if re.match(r"(?:\\wj\s+)?¶", text.strip()):
                pil.add((c, int(n)))
            elif "¶" in text:
                raise SystemExit(f"witness: a ¶ inside a verse, {c}:{n}: {text[:80]!r}")
    return {"notes": notes, "pilcrows": pil}


def ours_markup(note: str) -> str:
    """A witness note in the copy's markup: \\nd as \\textsc in the copy's
    case (the LORD written Lord, set in small capitals), \\add as \\bibemph,
    the ellipsis and the apostrophe as the copy types them, the stop at its end."""
    s = C.RE_W.sub(r"\1", note)
    s = re.sub(r"\\\+?add (.*?)\\\+?add\*", r"\\bibemph{\1}", s)
    s = re.sub(r"\\\+?nd (.*?)\\\+?nd\*", lambda m: "\\textsc{" + m[1][0] + m[1][1:].lower() + "}", s)
    s = s.replace("…", "...").replace("’", "'").replace("‘", "'")
    if re.search(r"\\(?!bibemph|textsc)", s):
        raise SystemExit(f"witness: a marker not read in a note: {note!r}")
    s = " ".join(s.split())
    return s if s.endswith(("?", "!", ".")) else s + "."


def names(books_verses: dict) -> dict[str, str]:
    """Every word of the copy that a name's hyphens or an æ could hide, by its
    folded form: {"bethel": "Bethel"}."""
    out: dict[str, str] = {}
    for rows in books_verses.values():
        for r in rows:
            for w in re.findall(r"[A-Za-z][A-Za-z'-]*", C.ours_flat(r["text"] + " " + r["note"])):
                out.setdefault(fold(w), w)
    return out


def fold(w: str) -> str:
    return w.replace("-", "").replace("æ", "ae").replace("Æ", "Ae").lower()


def our_names(note: str, known: dict[str, str], where: str, odd: list) -> str:
    """A name the witness hyphenates or writes with æ, as the copy writes it."""
    def one(m):
        w = m[0]
        if "-" not in w and "æ" not in w.lower():
            return w
        if w[0].islower() and "æ" not in w.lower():
            return w                                    # arrow-snake, standard-bearer: no name
        got = known.get(fold(w))
        if got is None:
            odd.append(f"{where}: {w!r}, a name the copy never writes")
            return w
        return got
    return re.sub(r"[A-Za-zæÆ][A-Za-zæÆ'-]*[A-Za-zæÆ]", one, note)


def loose(s: str) -> str:
    """For finding where a title ends in the copy's verse: its words alone,
    since the two may punctuate it otherwise (1Co 16:24's subscription)."""
    return " ".join(re.sub(r"[^\w\s]", " ", fold(C.norm(s))).split())


def split_head(tex: str, want: str) -> tuple[str, str] | None:
    """The copy's verse split after the words that are `want`, the witness's
    title: (head, rest), both in the copy's markup, or None."""
    goal = loose(want)
    for m in re.finditer(r" ", tex):
        head = tex[:m.start()]
        if head.count("{") != head.count("}"):
            continue
        if loose(C.ours_flat(head)) == goal:
            return head, tex[m.end():]
    return None


def split_after(tex: str, want: str) -> tuple[str, str] | None:
    """An epistle's subscription: what follows its last verse's last "Amen.",
    held to the witness's by most of its words, since six of the fourteen are
    worded otherwise in the copy ("To [the] Galatians written from Rome." for
    the witness's "Unto the Galatians written from Rome.")."""
    at = tex.rfind("Amen. ")
    if at < 0:
        return None
    body, tail = tex[:at + len("Amen.")], tex[at + len("Amen. "):]
    ours, theirs = set(loose(C.ours_flat(tail)).split()), set(loose(want).split())
    if len(ours & theirs) * 3 < len(theirs) * 2:
        return None
    return body, tail


def merge() -> tuple[list[dict], list[str]]:
    books, verses, _ = V.convert()
    V.apply(verses, V.corrections())
    wit = C.witness_books()
    known = names(verses)
    rows, odd = [], []
    for b in books:
        abbr = b["abbr"]
        usfm = wit[C.USFM[abbr]]
        wverses, wnotes, before, _ = C.witness(usfm)
        raw = witness_raw(usfm)
        mine = {(r["chapter"], r["verse"]): r for r in verses[abbr]}
        for cv in sorted(raw["pilcrows"]):
            if cv not in mine:
                raise SystemExit(f"{abbr} {cv}: a ¶ at a verse the copy lacks")
            rows.append(dict(book=abbr, chapter=cv[0], verse=cv[1], field="pilcrow", value="¶",
                             why="the 1769's paragraph mark"))
        for key, h in sorted(before.items()):
            cv, r = key[:2], mine.get(key[:2])
            where = f"{abbr} {cv[0]}:{cv[1]}"
            if r is None:
                raise SystemExit(f"{where}: a title or subscription at a verse the copy lacks")
            if len(key) == 3:
                got = split_after(r["text"], h)
                if got is None:
                    raise SystemExit(f"{where}: the subscription {h!r} is not the end of the copy's verse")
                rows.append(dict(book=abbr, chapter=cv[0], verse=cv[1], field="after", value=got[1],
                                 why="the epistle's subscription, set after its last verse"))
            else:
                got = split_head(r["text"], h)
                if got is None:
                    raise SystemExit(f"{where}: the title {h!r} is not the head of the copy's verse")
                rows.append(dict(book=abbr, chapter=cv[0], verse=cv[1], field="head", value=got[0],
                                 why="Psalm 119's letter, set above its verse" if re.fullmatch(r"[A-Z]+\.", h)
                                 else "the psalm's title, set above its verse 1"))
        if b["testament"] != "OT":
            if wnotes:
                raise SystemExit(f"{abbr}: the witness has notes in the New Testament now; rule on them")
            continue
        for cv, r in sorted(mine.items()):
            if cv not in raw["notes"]:
                continue
            n_ours = C.norm(C.ours_flat(r["note"]))
            n_wit = C.norm(" ".join(x if x.endswith(("?", "!", ".")) else x + "." for x in wnotes[cv]))
            if n_ours == n_wit:
                continue
            kind = C.kind(n_ours, n_wit) if n_ours else "missing"
            if kind not in ("words", "missing") or (abbr, *cv) in KEEP:
                continue
            where = f"{abbr} {cv[0]}:{cv[1]}"
            new = our_names(" ".join(ours_markup(x) for x in raw["notes"][cv]), known, where, odd)
            if new == r["note"]:
                continue
            # A gloss whose lemma is not in its verse is the witness's slip, a
            # note repeated at the wrong verse (2Ch 6:29, "toward...: or, in
            # this place"): the copy's note stands, and the place is told.
            verse = C.ours_flat(r["text"])
            lemmas = lambda note: [g.lemma for g in kjvnotes.glosses(C.ours_flat(note)) if g.lemma]
            had = set(lemmas(r["note"]))
            astray = [x for x in lemmas(new) if not C.lemma_in(x, verse) and x not in had]
            if astray:
                odd.append(f"{where}: not taken, its lemma {astray[0]!r} is not in the verse: {new}")
                continue
            rows.append(dict(book=abbr, chapter=cv[0], verse=cv[1], field="note", value=new,
                             why="the 1769's note, which the copy lacks" if kind == "missing"
                             else "the 1769's words for the note"))
    return rows, odd


def text(rows: list[dict]) -> str:
    return "\t".join(FIELDS) + "\n" + "".join(
        "\t".join(str(r[f]) for f in FIELDS) + "\n" for r in rows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    rows, odd = merge()
    for o in odd:
        print(f"  {o}")
    by = collections.Counter(r["field"] for r in rows)
    want = text(rows)
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == want
        print(f"{OUT.relative_to(ROOT)}: " + ("what the witness gives" if same else "NOT what the witness gives"))
        return 0 if same else 1
    OUT.write_text(want, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: " + ", ".join(f"{v:,} {k}" for k, v in sorted(by.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
