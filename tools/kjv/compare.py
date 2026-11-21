"""Set data/kjv/ beside an independent electronic KJV, verse by verse.

    .venv/bin/python -m tools.kjv.compare             the differences -> var/kjv/compare.txt
    .venv/bin/python -m tools.kjv.compare --fetch     fetch the witness first, held to its digest

The witness is eBible.org's King James Version, the 1769 text, public domain
(build/config.py kjv_witness()): USFM, a file to a book, with the words the
translators supplied (\\add), the LORD (\\nd), the psalms' titles (\\d), Psalm
119's letters and the epistles' subscriptions (\\s1), and the translators'
marginal notes (\\f).  It is fetched into var/kjv/witness/, never committed,
and read here as data: nothing in it is run.

What is compared, after both are brought to one form (the supplied words in
[brackets], the LORD in capitals, the quotes and the ellipsis plain, the
pilcrows and Strong's numbers of the witness set aside):

  the verse's words, with a psalm's title or a letter of Psalm 119 put before
  its verse 1, and an epistle's subscription after its last verse, where the
  edition has them;
  the notes, the edition's one \\fn to a verse against the witness's notes at
  that verse, joined.

Each difference is a line of var/kjv/compare.txt, by kind.  It decides nothing:
a slip is mended by a line of data/kjv/corrections.tsv, with its witness.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import pathlib
import re
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "kjv"
VAR = ROOT / "var" / "kjv"
WITNESS = VAR / "witness"

# Our abbreviation -> the witness's book id.
USFM = dict(zip(
    "Gen Exo Lev Num Deu Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est Job Psa Pro Ecc Sol Isa Jer "
    "Lam Eze Dan Hos Joe Amo Oba Jon Mic Nah Hab Zep Hag Zec Mal Mat Mar Luk Joh Act Rom 1Co 2Co Gal "
    "Eph Phi Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jam 1Pe 2Pe 1Jo 2Jo 3Jo Jud Rev".split(),
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER "
    "LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL "
    "EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV".split()))


def config() -> dict:
    sys.path.insert(0, str(ROOT))
    from build import config as cfg
    return cfg.kjv_witness()


def fetch() -> None:
    cfg = config()
    WITNESS.mkdir(parents=True, exist_ok=True)
    zpath = WITNESS / pathlib.Path(cfg["url"]).name
    req = urllib.request.Request(cfg["url"], headers={"User-Agent": "ubsite-build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read()
    got = hashlib.sha256(blob).hexdigest()
    if got != cfg["sha256"]:
        raise SystemExit(f"{cfg['url']}: SHA-256 {got}, where the witness named is {cfg['sha256']}")
    tmp = zpath.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(zpath)
    print(f"{zpath.relative_to(ROOT)}: {len(blob):,} bytes, the digest it is named by")


def witness_books() -> dict[str, str]:
    """{USFM id: the book's USFM}, from the zip as fetched."""
    cfg = config()
    zpath = WITNESS / pathlib.Path(cfg["url"]).name
    if not zpath.exists():
        raise SystemExit(f"{zpath.relative_to(ROOT)}: not fetched (--fetch)")
    if hashlib.sha256(zpath.read_bytes()).hexdigest() != cfg["sha256"]:
        raise SystemExit(f"{zpath.relative_to(ROOT)}: not the file the witness is named by (--fetch)")
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            m = re.fullmatch(r"\d\d-([0-9A-Z]{3})eng-kjv\.usfm", n)
            if m:
                out[m[1]] = z.read(n).decode("utf-8")
    return out


RE_W = re.compile(r"\\\+?w ([^|\\]*)\|[^\\]*\\\+?w\*")
RE_F = re.compile(r"\\f \+ \\fr (\d+)\.(\d+) \\ft (.*?)\\f\*")


def flat(s: str) -> str:
    """USFM inline -> the one form: supplied words in [ ], the LORD in capitals."""
    s = RE_W.sub(r"\1", s)
    s = re.sub(r"\\\+?add (.*?)\\\+?add\*", r"[\1]", s)
    s = re.sub(r"\\\+?nd (.*?)\\\+?nd\*", lambda m: m[1].upper(), s)
    s = re.sub(r"\\\+?(?:wj|tl) ", "", s)
    s = re.sub(r"\\\+?(?:wj|tl)\*", "", s)
    if "\\" in s:
        raise SystemExit(f"witness: a marker not read: {s[:120]!r}")
    return s


def witness(usfm: str) -> tuple[dict, dict, dict, list]:
    """(verses {(c, v): text}, notes {(c, v): [note]}, before {(c, v): heading},
    pilcrows [(c, v)]) of one book."""
    verses, notes, before, pil = {}, collections.defaultdict(list), {}, []
    c = v = 0
    pending = []
    for line in usfm.split("\n"):
        line = line.strip()
        if not line:
            continue
        for m in RE_F.finditer(line):
            notes[(int(m[1]), int(m[2]))].append(flat(m[3]).strip())
        line = RE_F.sub("", line)
        tag, _, rest = line.partition(" ")
        if tag == "\\c":
            c, v = int(rest), 0
        elif tag == "\\v":
            n, _, text = rest.partition(" ")
            v = int(n)
            text = text.strip()
            if text.startswith("¶"):
                pil.append((c, v))
                text = text[1:].strip()
            verses[(c, v)] = flat(text)
            if pending:
                before[(c, v)] = " ".join(pending)
                pending = []
        elif tag in ("\\d", "\\s1"):
            h = flat(rest).strip()
            if v and tag == "\\s1" and not re.fullmatch(r"\S+ [A-Z]+\.", h):
                before[(c, v, "after")] = h        # an epistle's subscription
            else:
                pending.append(re.sub(r"^\S+ (?=[A-Z]+\.$)", "", h))   # Psalm 119's letter, Hebrew dropped
        elif tag in ("\\p", "\\q1", "\\b", "\\m", "\\nb"):
            if rest.strip():
                raise SystemExit(f"witness: text on a {tag} line: {rest[:60]!r}")
        elif tag in ("\\id", "\\h", "\\toc1", "\\toc2", "\\toc3", "\\mt1", "\\mt2", "\\ms1", "\\ide",
                     "\\imt1", "\\is1", "\\ip"):
            pass
        else:
            raise SystemExit(f"witness: a line of no kind: {line[:80]!r}")
    return verses, notes, before, pil


def ours_flat(s: str) -> str:
    s = re.sub(r"\\bibemph\{([^{}]*)\}", r"[\1]", s)
    return re.sub(r"\\textsc\{([^{}]*)\}", lambda m: m[1].upper(), s)


def norm(s: str) -> str:
    """Quotes, the ellipsis, the dash and the ligatures plain, the spaces single."""
    for x, y in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("…", "..."), ("—", "--"),
                 ("æ", "ae"), ("Æ", "Ae"), ("œ", "oe")):
        s = s.replace(x, y)
    s = " ".join(s.replace("¶", " ").split())
    # The witness's supplied words can hold a space or a stop at an edge,
    # `\\add  which\\add*`, `\\add it:\\add*`: the edge's, not the words'.
    s = s.replace("[ ", "[").replace(" ]", "]")
    return re.sub(r"([,.;:?!]+)\]", r"]\1", s)


def whole(r: dict) -> str:
    """A verse of the copy as one run of words: its title or letter, its
    text, its subscription (data/kjv/witness.tsv set them apart)."""
    return " ".join(x for x in (r.get("head", ""), r["text"], r.get("after", "")) if x)


def read_ours() -> tuple[list[dict], dict[str, list[dict]]]:
    rows = (DATA / "books.tsv").read_text(encoding="utf-8").split("\n")
    head = rows[0].split("\t")
    books = [dict(zip(head, r.split("\t"))) for r in rows[1:] if r]
    verses = {}
    for b in books:
        lines = (DATA / f"{b['abbr']}.tsv").read_text(encoding="utf-8").split("\n")
        h = lines[0].split("\t")
        verses[b["abbr"]] = [dict(zip(h, r.split("\t"))) for r in lines[1:] if r]
    return books, verses


# A note is one or more glosses, each `lemma: gloss.`: the lemma the verse's
# words it glosses, or their first words and "..." (`the light from...: Heb.
# between ...`).  A lemma is found at the start of the note and after each
# full stop, before the first colon that follows it.
RE_LEMMA = re.compile(r"(?:^|(?<=\. ))([^:.]+?(?:\.\.\.)?): ")


def lemmas(note: str) -> list[str]:
    return [m[1] for m in RE_LEMMA.finditer(note)
            if not re.fullmatch(r"(?:Heb|Gr|or|Chaldee|Syr|that is|i\.e)\b.*", m[1])]


def lemma_in(lemma: str, verse: str) -> bool:
    """Whether the lemma's words stand in the verse, the supplied words'
    brackets aside, case aside, and a lemma ending "..." taken as a beginning."""
    plain = lambda t: " ".join(re.sub(r"[^\w\s']", " ", t.replace("[", "").replace("]", "")).lower().split())
    v = " " + plain(verse) + " "
    if lemma.endswith("..."):
        return (" " + plain(lemma[:-3]) + " ") in v or (" " + plain(lemma[:-3])) in v
    return (" " + plain(lemma) + " ") in v


def words_diff(a: str, b: str) -> str:
    """The words where a and b differ, as `-ours +witness`, with a word of context."""
    x, y = a.split(" "), b.split(" ")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        ctx = x[i1 - 1] + " " if i1 else ""
        out.append(f"{ctx}[-{' '.join(x[i1:i2])}-][+{' '.join(y[j1:j2])}+]")
    return "  ".join(out)


def kind(a: str, b: str) -> str:
    """What sort of difference: only the supplied words' brackets, only case,
    only punctuation, or words."""
    if a.replace("[", "").replace("]", "") == b.replace("[", "").replace("]", ""):
        return "supplied"
    if a.lower() == b.lower():
        return "case"
    if a.replace("-", "") == b.replace("-", ""):
        return "hyphens"
    strip = lambda s: re.sub(r"[^\w\s]", "", s.replace("[", "").replace("]", "")).split()
    if strip(a) == strip(b):
        return "punctuation"
    if [w.lower() for w in strip(a)] == [w.lower() for w in strip(b)]:
        return "case+punctuation"
    return "words"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args(argv)
    if args.fetch:
        fetch()
    wit = witness_books()
    books, ours = read_ours()
    out = collections.defaultdict(list)
    counts = collections.Counter()
    for b in books:
        abbr = b["abbr"]
        verses, notes, before, pil = witness(wit[USFM[abbr]])
        counts["pilcrows"] += len(pil)
        mine = {(int(r["chapter"]), int(r["verse"])): r for r in ours[abbr]}
        for cv in sorted(set(verses) - set(mine)):
            out["missing here"].append(f"{abbr} {cv[0]}:{cv[1]}  {verses[cv][:80]}")
        for cv in sorted(set(mine) - set(verses)):
            out["not in the witness"].append(f"{abbr} {cv[0]}:{cv[1]}")
        for cv, r in sorted(mine.items()):
            if cv not in verses:
                continue
            w = verses[cv]
            if cv in before:
                w = before[cv] + " " + w
            if (cv[0], cv[1], "after") in before:
                w = w + " " + before[(cv[0], cv[1], "after")]
            a, z = norm(ours_flat(whole(r))), norm(w)
            counts["verses"] += 1
            if a != z:
                k = kind(a, z)
                counts[f"text {k}"] += 1
                out[f"text: {k}"].append(f"{abbr} {cv[0]}:{cv[1]}  {words_diff(a, z)}")
            n_ours = norm(ours_flat(r["note"]))
            # The witness ends no gloss with a stop; the copy ends each with one,
            # but where it ends in "?" or "etc." already.
            n_wit = norm(" ".join(x if x.endswith(("?", "!", ".")) else x + "."
                                  for x in notes.get(cv, [])))
            if n_ours or n_wit:
                counts["notes"] += 1
                if n_ours != n_wit:
                    if not n_ours:
                        k = "a note the edition lacks"
                    elif not n_wit:
                        k = "a note the witness lacks"
                    else:
                        k = kind(n_ours, n_wit)
                    counts[f"note {k}"] += 1
                    out[f"note: {k}"].append(f"{abbr} {cv[0]}:{cv[1]}  {words_diff(n_ours, n_wit)}"
                                             if n_ours and n_wit else
                                             f"{abbr} {cv[0]}:{cv[1]}  {n_ours or n_wit}")
        for cv, r in sorted(mine.items()):
            for lemma in lemmas(ours_flat(r["note"])):
                if not lemma_in(lemma, ours_flat(whole(r))):
                    counts["note lemma not in its verse"] += 1
                    out["note: lemma not in its verse"].append(
                        f"{abbr} {cv[0]}:{cv[1]}  {lemma!r}  in  {r['note'][:120]}")
    VAR.mkdir(parents=True, exist_ok=True)
    report = VAR / "compare.txt"
    with report.open("w", encoding="utf-8") as fh:
        for k, v in sorted(counts.items()):
            fh.write(f"# {k}: {v:,}\n")
        for k in sorted(out):
            fh.write(f"\n## {k} ({len(out[k]):,})\n")
            fh.write("".join(x + "\n" for x in out[k]))
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v:,}")
    print(f"-> {report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
