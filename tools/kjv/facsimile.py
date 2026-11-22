"""Where each gloss of the KJV's notes stands, as the 1769 printing set it.

    .venv/bin/python -m tools.kjv.facsimile --fetch   fetch the facsimile's OCR, held to its digest
    .venv/bin/python -m tools.kjv.facsimile           -> var/kjv/marks-review.md

The witness is the 1769 Oxford printing itself, in a facsimile on archive.org
(build/config.py kjv_1769()): its OCR text, fetched into var/kjv/facsimile/,
never committed, and read here as data.  The printing set a mark before the
first word each marginal note glosses, a dagger before the Hebrew's words, a
double bar before another reading, and the OCR keeps most of them, read as
`+`, `|`, `||`, `{`, `}`, `t`: "divided + the light from the darkness" (Gen
1:4), "called | Marah" (Exo 15:23).  Cross-references have marks of their own,
letters and `*`, which are not the notes'.

Each verse with a note is found in the OCR by its words (the long s read as f,
both folded to s, and three words at a time voted for a place, the verses in
the book's order), its words aligned to the OCR's, and for every place a
lemma's first word stands in the verse, what the OCR has just before it.  The
review lists every gloss build/bible.py cannot place by its rule, a lemma
standing once in its verse and its psalm's title, and every gloss
data/kjv/marks.tsv places, with the facsimile's lines and the mark seen at
each place; and counts how many of the glosses placed by the rule have a
note's mark before them.  It decides nothing: a place is read, and written in
data/kjv/marks.tsv with its reason.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import difflib
import hashlib
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import bible, config, kjvnotes          # noqa: E402
from build.problems import Report                  # noqa: E402

DIR = ROOT / "var" / "kjv" / "facsimile"
OCR = DIR / "kjv1769_djvu.txt"
REVIEW = ROOT / "var" / "kjv" / "marks-review.md"

RE_TOKEN = re.compile(r"[A-Za-z]+")
# What the OCR makes of a mark before a word, besides signs: a letter alone,
# "Make t bright the arrows" (Jer 51:11), "let “q Satan" (Psa 109:6).  The
# notes' dagger and double bar and the cross-references' letters and stars
# are not told apart: the OCR reads them all as anything.
MARK_WORDS = {"t", "q", "b", "I", "l", "Il", "ll", "tt", "ft", "f"}


def fetch() -> None:
    cfg = config.kjv_1769()
    req = urllib.request.Request(cfg["url"], headers={"User-Agent": "ubsite-build"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    got = hashlib.sha256(blob).hexdigest()
    if got != cfg["sha256"]:
        raise SystemExit(f"{cfg['url']}: SHA-256 {got}, where the facsimile named is {cfg['sha256']}")
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = OCR.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(OCR)
    print(f"{OCR.relative_to(ROOT)}: {len(blob):,} bytes, the digest it is named by")


def fold(w: str) -> str:
    return w.lower().replace("f", "s")


class Facsimile:
    def __init__(self, text: str):
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != config.kjv_1769()["sha256"]:
            raise SystemExit(f"{OCR.relative_to(ROOT)}: not the file the facsimile is named by (--fetch)")
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer(r"\n", text)]
        self.tok = [(fold(m[0]), m.start(), m.end()) for m in RE_TOKEN.finditer(text)]
        self.words = [t for t, _, _ in self.tok]
        self.tri = collections.defaultdict(list)
        for i in range(len(self.words) - 2):
            self.tri[(self.words[i], self.words[i + 1], self.words[i + 2])].append(i)

    def locate(self, ws: list[str], lo: int, hi: int) -> int | None:
        """The OCR token where the words ws begin, voted by their trigrams,
        between lo and hi if any vote falls there, else anywhere."""
        votes: collections.Counter = collections.Counter()
        for k in range(len(ws) - 2):
            ps = self.tri.get((ws[k], ws[k + 1], ws[k + 2]), ())
            if len(ps) > 400:
                continue
            for p in ps:
                votes[(p - k) // 8] += 1
        enough = max(2, (len(ws) - 2) // 5)
        good = [(n, b) for b, n in votes.items() if n >= enough]
        if not good:
            return None
        near = [(n, b) for n, b in good if lo <= b * 8 <= hi]
        return max(near or good)[1] * 8

    def align(self, ws: list[str], at: int) -> dict[int, int]:
        """{index of a verse word: index of its OCR token} near at."""
        a, z = max(0, at - 12), min(len(self.words), at + len(ws) * 2 + 60)
        sm = difflib.SequenceMatcher(None, ws, self.words[a:z], autojunk=False)
        out = {}
        for i, j, n in sm.get_matching_blocks():
            for k in range(n):
                out[i + k] = a + j + k
        return out

    def before(self, t: int) -> str:
        """What the OCR has before the token t, back to the word before it:
        signs, and letters alone that are a mark read as a letter."""
        k = t - 1
        while k >= 0 and self.text[self.tok[k][1]:self.tok[k][2]] in MARK_WORDS and t - k < 3:
            k -= 1
        start = self.tok[k][2] if k >= 0 else 0
        # The verse's own stops and commas are not marks.
        return " ".join(re.sub(r"[,.;:?]", " ", self.text[start:self.tok[t][1]]).split())

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.lines, offset) - 1

    def lines_between(self, t0: int, t1: int) -> str:
        a = self.line_of(self.tok[t0][1])
        z = self.line_of(self.tok[t1][1])
        end = self.lines[z + 1] if z + 1 < len(self.lines) else len(self.text)
        return self.text[self.lines[a]:end].rstrip("\n")


def verses_with_notes() -> list[dict]:
    """Each verse with a note, expanded as the build expands it: abbr, c, v,
    parts [(title|text, words)], glosses, testament."""
    report = Report()
    kb, kv, _, _, _ = bible.read(report)
    if report.blocking:
        raise SystemExit("\n".join(str(p) for p in report.blocking))
    out = []
    for b in kb:
        for r in kv[b["abbr"]]:
            if not r["note"]:
                continue
            ex = lambda tex, what: bible.expand(tex, f"{b['abbr']} {r['chapter']}:{r['verse']} {what}",
                                                report, bible.KJV_TABLE, bible.KJV_SUBS)
            text, _, _ = ex(r["text"], "")
            parts = []
            if r["head"] and not bible.RE_LETTER.fullmatch(r["head"]):
                parts.append(("title", ex(r["head"], "(heading)")[0]))
            parts.append(("text", text))
            ntext, nspans, _ = ex(r["note"], "(note)")
            out.append(dict(abbr=b["abbr"], c=r["chapter"], v=r["verse"], parts=parts,
                            glosses=kjvnotes.glosses(ntext, nspans), testament=b["testament"]))
    return out


def word_index(parts: list[tuple[str, str]]) -> tuple[list[str], dict[tuple[str, int], int]]:
    """The verse's folded words, and {(part, offset): its index}."""
    ws, at = [], {}
    for part, text in parts:
        for m in kjvnotes.RE_WORD.finditer(text):
            at[(part, m.start())] = len(ws)
            ws.extend(fold(x) for x in RE_TOKEN.findall(m[0]) or [m[0]])
    return ws, at


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args(argv)
    if args.fetch:
        fetch()
    if not OCR.exists():
        raise SystemExit(f"{OCR.relative_to(ROOT)}: not fetched (--fetch)")
    fac = Facsimile(OCR.read_text(encoding="utf-8"))
    marks = bible.read_marks(Report())
    counts = collections.Counter()
    review = []
    last = 0
    for vr in verses_with_notes():
        ws, at = word_index(vr["parts"])
        where = f"{vr['abbr']} {vr['c']}:{vr['v']}"
        t0 = fac.locate(ws, last, last + 40000)
        al = fac.align(ws, t0) if t0 is not None else {}
        if t0 is not None and len(al) >= len(ws) // 3:
            last = t0
        else:
            al = {}
        for g in vr["glosses"]:
            key = (vr["abbr"], vr["c"], vr["v"], kjvnotes.lemma_key(g.lemma))
            occ = kjvnotes.occurrences(g.lemma, vr["parts"]) if g.lemma else []
            seen = []
            for part, off in occ:
                i = at.get((part, off))
                t = al.get(i) if i is not None else None
                seen.append(None if t is None else fac.before(t))
            ruled = key in marks
            if len(occ) == 1 and not ruled:
                counts["placed by the rule"] += 1
                if seen[0] is None:
                    counts["  the word not found in the facsimile"] += 1
                elif seen[0]:
                    counts["  a mark before it"] += 1
                else:
                    counts["  no mark before it"] += 1
                continue
            counts["read" if ruled else "UNPLACED"] += 1
            lines = []
            if al:
                lines = fac.lines_between(min(al.values()), max(al.values())).split("\n")
            shown = " | ".join(f"{p}: {t}" for p, t in vr["parts"])
            review.append(
                f"### {where}  {g.lemma or '(no lemma)'!s}  ({len(occ)} places)"
                + (f"  RULED: {marks[key][0]}  ({marks[key][1]})" if ruled else "") + "\n\n"
                + f"note: {g.text}\n\nverse: {shown}\n\n"
                + "".join(f"- place {n} ({p}, {o}): mark seen {s!r}\n"
                          for n, ((p, o), s) in enumerate(zip(occ, seen), 1))
                + ("\n1769:\n\n```\n" + "\n".join(lines[:16]) + "\n```\n" if lines else "\n1769: not found\n")
                + "\n")
    with REVIEW.open("w", encoding="utf-8") as fh:
        fh.write("# The KJV's glosses beside the 1769 printing\n\n")
        for k, v in counts.items():
            fh.write(f"- {k}: {v:,}\n")
        fh.write("\n" + "".join(review))
    for k, v in counts.items():
        print(f"  {k}: {v:,}")
    print(f"-> {REVIEW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
