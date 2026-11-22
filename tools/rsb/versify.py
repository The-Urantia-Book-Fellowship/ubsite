"""The Synodal's numbering against the KJV's: data/rsb/versification.tsv, from SIL's files.

    .venv/bin/python -m tools.rsb.versify --fetch    fetch the files into var/rsb/vrs/ (config.rsb_vrs())
    .venv/bin/python -m tools.rsb.versify            compose them, set the result against data/rsb/
                                                    and data/kjv/, write var/rsb/versification.tsv
                                                    and var/rsb/review.md
    .venv/bin/python -m tools.rsb.versify --check    fail unless data/rsb/versification.tsv places
                                                    every verse of both, and say how far it is the witness's

SIL's versification files (libpalaso, MIT) each map a numbering to the Hebrew
Bible's (BHS, org.vrs), a line `BOOK c:v-w = BOOK c:v-w` where they differ:
rso the Synodal with its non-canonical books, rsc without them, eng the
English Bibles'.  A Synodal verse is taken through rso to the Hebrew's, and
from there through eng, read backwards, to the English's, which is the KJV's
where the KJV has that verse.  What that makes is set against the two copies
verse by verse, and each chapter's verse lengths are compared, the KJV's with
the Synodal's in each row: one verse off, a chapter's correlation falls from
above 0.9 to below 0.5.  The table is the master once ruled (build/versify.py
reads it); this tool only proposes it and says where the witness and the
lengths disagree, for Tigran.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import statistics
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build import config, versify               # noqa: E402

VRS = ROOT / "var" / "rsb" / "vrs"
OUTDIR = ROOT / "var" / "rsb"
TABLE = ROOT / "data" / "rsb" / "versification.tsv"

SIL = dict(zip(
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM "
    "EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP "
    "COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV".split(),
    "Gen Exo Lev Num Deu Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est Job Psa Pro Ecc Sol Isa Jer Lam "
    "Eze Dan Hos Joe Amo Oba Jon Mic Nah Hab Zep Hag Zec Mal Mat Mar Luk Joh Act Rom 1Co 2Co Gal Eph Phi "
    "Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jam 1Pe 2Pe 1Jo 2Jo 3Jo Jud Rev".split()))

RE_SIDE = re.compile(r"([0-9A-Z]{3}) (\d+):(\d+)(?:-(\d+))?")


def fetch() -> None:
    """Each file into var/rsb/vrs/, refusing other bytes than config names
    names: SIL edits them now and then, and the table was ruled from these."""
    cfg = config.rsb_vrs()
    VRS.mkdir(parents=True, exist_ok=True)
    for name in cfg["files"]:
        with urllib.request.urlopen(cfg["base"] + name, timeout=60) as r:
            body = r.read()
        got = hashlib.sha256(body).hexdigest()
        if got != cfg["sha256"][name]:
            raise SystemExit(f"{name}: sha256 {got}, where config names {cfg['sha256'][name]}")
        path = VRS / name
        path.write_bytes(body)
        print(f"{name}  {len(body):,} bytes  sha256 {got}")


def mappings(name: str) -> list[tuple[tuple, tuple]]:
    """A file's mapping lines, each range taken verse by verse: [(own, org)],
    (abbr or the SIL code, c, v).  A side with a letter (ESG 1:1a) is a book
    the KJV lacks, and is left out."""
    out = []
    for line in (VRS / name).read_text(encoding="utf-8").split("\n"):
        line = line.split("#")[0].strip()
        if "=" not in line:
            continue
        a, b = (x.strip() for x in line.split("="))
        ma, mb = RE_SIDE.fullmatch(a), RE_SIDE.fullmatch(b)
        if not ma or not mb:
            continue
        sa = [(SIL.get(ma[1], ma[1]), int(ma[2]), v) for v in range(int(ma[3]), int(ma[4] or ma[3]) + 1)]
        sb = [(SIL.get(mb[1], mb[1]), int(mb[2]), v) for v in range(int(mb[3]), int(mb[4] or mb[3]) + 1)]
        if len(sa) == len(sb):
            out += list(zip(sa, sb))
        elif len(sa) == 1:
            out += [(sa[0], x) for x in sb]
        elif len(sb) == 1:
            out += [(x, sb[0]) for x in sa]
        else:
            SLIPS.append(f"{name}: `{line}`, {len(sa)} verses to {len(sb)}: left out")
    return out


SLIPS: list[str] = []


def tsv(path: pathlib.Path) -> list[list[str]]:
    return [r.split("\t") for r in path.read_text(encoding="utf-8").split("\n")[1:] if r]


def plain(s: str) -> str:
    """The words whose length is compared: no note, no macro, and none of the
    Synodal's words in brackets, which are the Greek's where the Hebrew, and
    so the KJV, has none (1Ki 2:35's run of eleven lines)."""
    s = re.sub(r"\\fns\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", s)
    s = re.sub(r"\[[^\[\]]*\]", "", s)
    return re.sub(r"\\[a-z]+|[{}\[\]]", "", s)


def copies() -> tuple[dict, dict, dict, dict]:
    """The verses of the 66: ({abbr: [(c, v)]} the Synodal's in its order, the
    same for the KJV's with each psalm's title as (c, 0), and each one's
    length {abbr: {(c, v): n}}, the words alone)."""
    kb = [r[1] for r in tsv(ROOT / "data" / "kjv" / "books.tsv")]
    syn, kjv, slen, klen = {}, {}, {}, {}
    for b in kb:
        kjv[b], klen[b] = [], {}
        for c, v, _, head, text, _, _ in tsv(ROOT / "data" / "kjv" / f"{b}.tsv"):
            c, v = int(c), int(v)
            if head and not re.fullmatch(r"[A-Z]+\.", head) and v == 1:
                kjv[b].append((c, 0))
                klen[b][(c, 0)] = len(plain(head))
            kjv[b].append((c, v))
            klen[b][(c, v)] = len(plain(text))
        syn[b], slen[b] = [], {}
        for c, v, _, head, text in tsv(ROOT / "data" / "rsb" / f"{b}.tsv"):
            s = (int(c), int(v))
            syn[b].append(s)
            slen[b][s] = len(plain(text))
    return syn, kjv, slen, klen


# Where the witness is wrong for this edition, each found where the length
# aligner disagreed and settled by reading the two texts (2026-11-21): a
# Synodal run, the KJV's verses it is ([] the Synodal's alone), and why.  A
# run to a run of the same length is one to one; to one verse, many to one.
READ = [
    ("Neh 7:67-73", "Neh 7:67-73", "the edition has 7:68, the horses, which the Hebrew lacks: as the KJV"),
    ("1Sa 20:42-43", "1Sa 20:42", "«И встал [Давид] и пошел» is the end of the KJV's 20:42"),
    ("Pro 13:14", "", "«[У сына лукавого ничего нет доброго…]», a verse of the Greek, which the Hebrew and the KJV have not"),
    ("Pro 18:8", "", "«[Ленивого низлагает страх…]», a verse of the Greek"),
    ("Isa 3:20-25", "Isa 3:21-26", "rso's line says 3:16-21, a slip; rsc's 3:21-26 is what the verses say"),
    ("Isa 63:19", "Isa 63:19", "the KJV's 64:1 is the Synodal's 64:1, not half of 63:19"),
    ("Isa 64:1", "Isa 64:1", "«О, если бы Ты расторг небеса» is the KJV's 64:1"),
    ("Dan 5:31", "Dan 5:31", "the edition numbers Daniel 5-6 as the KJV does; rso is the Orthodox 6:1"),
    ("Dan 6:1-28", "Dan 6:1-28", "the same"),
    ("Act 19:40", "Act 19:40-41", "its 19:40 ends with the assembly dismissed, the KJV's 19:41"),
    ("2Co 13:12", "2Co 13:12-13", "«Приветствуют вас все святые» is the KJV's 13:13"),
    ("2Co 13:13", "2Co 13:14", "the grace, the KJV's 13:14"),
    ("3Jo 1:15", "3Jo 1:14", "«Мир тебе. Приветствуют тебя друзья» is the end of the KJV's 1:14"),
    ("Rev 20:7", "Rev 20:7-8", "its 20:7 goes on «и выйдет обольщать народы», the KJV's 20:8"),
    ("Rev 20:8-9", "Rev 20:9", "«И вышли на широту земли» and «И ниспал огонь» are the KJV's 20:9"),
    ("Psa 12:6", "Psa 13:5-6", "«воспою Господу, облагодетельствовавшему меня» is the KJV's 13:6"),
    ("Psa 86:1", "Psa 87:0", "the title, «Сынов Кореевых. Псалом. Песнь.»"),
    ("Psa 86:2", "Psa 87:1-2", "«Основание его на горах святых. Господь любит врата Сиона» is 87:1 and 2"),
    ("Psa 89:1", "Psa 90:0", "the title, «Молитва Моисея, человека Божия.»; rso's lines here are a slip, rsc's right"),
    ("Psa 89:2-5", "Psa 90:1-4", "the same"),
    ("Psa 89:6", "Psa 90:5-6", "«как трава, которая утром вырастает, утром цветет» is 90:5 and 6"),
    ("Psa 89:7-17", "Psa 90:7-17", "the same"),
    ("Psa 114:0", "", "«[Аллилуия.]», the Greek's title, which the Hebrew and the KJV have not"),
    ("Psa 114:1-7", "Psa 116:1-7", "rso's line for 115 is a slip (11 verses to 10); the Synodal's 114 and 115 are the KJV's 116"),
    ("Psa 114:8", "Psa 116:8-9", "«Буду ходить пред лицем Господним» is 116:9"),
    ("Psa 115:0", "", "«[Аллилуия.]», the Greek's title"),
    ("Psa 115:1-10", "Psa 116:10-19", "the same"),
    ("Psa 147:0", "", "«[Аллилуия.]», the Greek's title; its 147:1 is the KJV's 147:12"),
    ("Psa 141:0", "Psa 142:0", "the title, «Учение Давида. Молитва его, когда он был в пещере.»; rso's 142:0 a slip, rsc's 142:0-1"),
]


# Where the lengths disagree with the witness and the witness is right, read
# the same day: verses whose lengths mislead (a genealogy, a phrase that one
# text puts at the end of a verse and the other at the head of the next).
CONFIRMED = {
    "Deu": "21:3 21:4", "1Sa": "20:41", "1Ki": "18:33 18:34", "Sol": "1:1", "Eze": "2:1 2:2",
    "Mat": "27:34", "Luk": " ".join(f"3:{v}" for v in range(19, 36)), "Act": "13:31 13:32 24:2 24:3",
    "Rom": "14:24 14:25 14:26 16:1 16:23 16:24", "2Co": "11:10 11:11",
}


def why(line: str) -> str:
    """A line of the table with its reason: the reading that set it right, or
    the witness's, rso through eng; a psalm's title, or the Greek's."""
    syn, kjv, _ = line.split("\t")
    for a, b, w in READ:
        if syn != "-" and versify.addresses(syn, "why")[1][0] in versify.addresses(a, "why")[1] \
                and syn.split()[0] == a.split()[0]:
            return f"{syn}\t{kjv}\tread: {w}"
    if kjv == "own":
        return f"{syn}\t{kjv}\tthe Greek's, a chapter the Hebrew and the KJV have not (rso)"
    if kjv.startswith("+") and " 0:" in syn:
        return f"{syn}\t{kjv}\tthe Greek's opening, which the KJV has not (rso)"
    if kjv.startswith("+") and syn.endswith(":0"):
        return f"{syn}\t{kjv}\ta title the KJV has not (rso)"
    if kjv.startswith("+"):
        return f"{syn}\t{kjv}\tthe Greek's, in brackets, which the KJV has not (rso)"
    if syn == "-":
        return f"{syn}\t{kjv}\tthe Synodal has no verse of it (rso)"
    return f"{syn}\t{kjv}\trso through eng"


def overrides() -> dict:
    """{abbr: {synodal (c, v): [kjv (c, v)]}} from READ."""
    out: dict = {}
    for s, k, _ in READ:
        b, ss = versify.addresses(s, "READ")
        ks = versify.addresses(k, "READ")[1] if k else []
        if k and len(ks) != len(ss) and 1 not in (len(ks), len(ss)):
            raise SystemExit(f"READ: {s} to {k}")
        for i, x in enumerate(ss):
            out.setdefault(b, {})[x] = ([ks[i]] if len(ks) == len(ss) else ks) if ks else []
    return out


def compose(syn: dict, kjv: dict) -> dict:
    """{abbr: {synodal (c, v): [kjv (c, v), ...]}} by rso, then eng read backwards."""
    rso, eng = mappings("rso.vrs.txt"), mappings("eng.vrs.txt")
    to_org: dict = {}
    for a, b in rso:
        to_org.setdefault(a, []).append(b)
    from_org: dict = {}
    eng_mapped = set()
    for a, b in eng:
        from_org.setdefault(b, []).append(a)
        eng_mapped.add(a)
    out = {}
    for book, verses in syn.items():
        kset = set(kjv[book])
        out[book] = {}
        for c, v in verses:
            got = []
            for o in to_org.get((book, c, v), [(book, c, v)]):
                if o[0] != book:
                    continue                                    # DAG, MAN, SUS, BEL: the KJV has none
                es = from_org.get(o) or ([o] if o not in eng_mapped else [])
                got += [(e[1], e[2]) for e in es if e[0] == book and (e[1], e[2]) in kset]
            out[book][(c, v)] = sorted(set(got), key=kjv[book].index)
        out[book].update(overrides().get(book, {}))
    return out


def align(book: str, syn: list, kjv: list, slen: dict, klen: dict) -> dict:
    """{synodal (c, v): [kjv (c, v)]} by the verses' lengths alone, as Gale and
    Church align sentences: the whole book one sequence against the other,
    each step one verse to one, one to two, two to one, or one of either
    alone, its cost how far the lengths are from the book's ratio.  Knows
    nothing of the witness, so that where the two agree each is the other's
    evidence."""
    n, k = len(syn), len(kjv)
    a = [max(slen[book][s], 1) for s in syn]
    b = [max(klen[book][x], 1) for x in kjv]
    ratio = sum(a) / sum(b)
    var = 6.8
    prior = {(1, 1): 0.0, (1, 0): 4.0, (0, 1): 4.0, (2, 1): 2.4, (1, 2): 2.4}

    def cost(ls, lk):
        d = (ls - lk * ratio) / ((lk * ratio + ls) / 2 * var) ** 0.5 if ls and lk else 0.0
        return d * d / 2

    band = max(60, abs(n - k) + 40)
    INF = float("inf")
    best = [dict() for _ in range(n + 1)]
    best[0][0] = (0.0, None)
    for i in range(n + 1):
        lo = max(0, int(i / max(n, 1) * k) - band)
        hi = min(k, int(i / max(n, 1) * k) + band)
        for j in range(lo, hi + 1):
            if i == 0 and j == 0:
                continue
            cand = (INF, None)
            for (di, dj), pen in prior.items():
                pi, pj = i - di, j - dj
                if pi < 0 or pj < 0 or pj not in best[pi]:
                    continue
                c = best[pi][pj][0] + pen + cost(sum(a[pi:i]), sum(b[pj:j]))
                if c < cand[0]:
                    cand = (c, (di, dj))
            if cand[1]:
                best[i][j] = cand
    if k not in best[n]:
        raise SystemExit(f"{book}: no alignment within the band")
    out = {x: [] for x in syn}
    i, j = n, k
    while i or j:
        di, dj = best[i][j][1]
        for x in syn[i - di:i]:
            out[x] = list(kjv[j - dj:j])
        i, j = i - di, j - dj
    return out


def components(book: str, syn: list, kjv: list, m: dict) -> list[tuple[list, list]]:
    """The rows `m` makes of a book, in order: (synodal verses, kjv verses),
    either empty for a row of one text alone."""
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s in syn:
        find(("s", s))
        for k in m[s]:
            parent[find(("s", s))] = find(("k", k))
    for k in kjv:
        find(("k", k))
    comp: dict = {}
    for s in syn:
        comp.setdefault(find(("s", s)), ([], []))[0].append(s)
    for k in kjv:
        comp.setdefault(find(("k", k)), ([], []))[1].append(k)
    kpos = {k: i for i, k in enumerate(kjv)}
    spos = {s: i for i, s in enumerate(syn)}
    # in the KJV's order, a row of the Synodal's alone after the row of the
    # Synodal verse before it
    rows = sorted(comp.values(), key=lambda r: (kpos[r[1][0]], 0) if r[1] else None or (0, 0))
    out, alone = [], [r for r in comp.values() if not r[1]]
    alone.sort(key=lambda r: spos[r[0][0]])
    kept = [r for r in comp.values() if r[1]]
    kept.sort(key=lambda r: kpos[r[1][0]])
    for r in kept:
        out.append(r)
    for r in alone:
        prev = syn[spos[r[0][0]] - 1] if spos[r[0][0]] else None
        at = next((i for i, x in enumerate(out) if prev in x[0]), -1)
        out.insert(at + 1, r)
    return out


def table(syn: dict, kjv: dict, mapped: dict) -> list[str]:
    """The lines of versification.tsv that say `mapped`."""
    lines = []
    for book in kjv:
        m = mapped[book]
        rows = components(book, syn[book], kjv[book], m)
        items = []                                          # (kind, syn list, kjv list)
        for i, (ss, ks) in enumerate(rows):
            if ss and ks:
                if len(ss) > 1 and len(ks) > 1:
                    raise SystemExit(f"{book}: a row of {len(ss)} Synodal verses and {len(ks)} KJV's: {ss} {ks}")
                if (ss, ks) != ([ks[0]], [ks[0]]) or ks[0] != ss[0]:
                    items.append(("moved", ss, ks))
            elif ss:
                c = ss[0][0]
                if c != 0 and not any(x[0] == c for r in rows for x in r[0] if r[1]):
                    items.append(("own", ss, None))
                else:
                    # a title, or a verse 0, stands just before the row it heads;
                    # any other after the row before it
                    before = next((r[1][-1] for r in reversed(rows[:i]) if r[1]), None)
                    after = next((r[1][0] for r in rows[i + 1:] if r[1]), None)
                    if ss[0][1] == 0 and after:
                        before = (after[0], 0) if after[1] <= 1 else kjv[book][kjv[book].index(after) - 1]
                    elif before and before[0] != c and after and after[0] == c:
                        before = (c, 0)
                    items.append(("after", ss, before or (after[0], 0)))
            else:
                items.append(("kjvonly", None, ks))
        lines += runs(book, items)
    return lines


def runs(book: str, items: list) -> list[str]:
    """Lines from the rows, a run of one-to-one rows with one offset joined."""
    def ref(xs):
        c, v = xs[0]
        w = xs[-1][1]
        if any(x[0] != c for x in xs) or [x[1] for x in xs] != list(range(v, w + 1)):
            raise SystemExit(f"{book}: not one run: {xs}")
        return f"{book} {c}:{v}" + (f"-{w}" if w != v else "")

    out, i = [], 0
    while i < len(items):
        kind, ss, ks = items[i]
        j = i + 1
        if kind == "moved" and len(ss) == 1 and len(ks) == 1:
            while (j < len(items) and items[j][0] == "moved" and len(items[j][1]) == 1 == len(items[j][2])
                   and items[j][1][0] == (ss[0][0], ss[0][1] + j - i)
                   and items[j][2][0] == (ks[0][0], ks[0][1] + j - i)):
                j += 1
            out.append(f"{ref([x[1][0] for x in items[i:j]])}\t{ref([x[2][0] for x in items[i:j]])}\t")
        elif kind == "moved":
            out.append(f"{ref(ss)}\t{ref(ks)}\t")
        elif kind in ("own", "after"):
            run = list(ss)
            while (j < len(items) and items[j][0] == kind and items[j][2] == ks
                   and items[j][1][0] == (run[-1][0], run[-1][1] + 1)):
                run += items[j][1]
                j += 1
            to = "own" if kind == "own" else f"+ {book} {ks[0]}:{ks[1]}"
            out.append(f"{ref(run)}\t{to}\t")
        else:
            run = list(ks)
            while (j < len(items) and items[j][0] == "kjvonly"
                   and items[j][2][0] == (run[-1][0], run[-1][1] + 1)):
                run += items[j][2]
                j += 1
            out.append(f"-\t{ref(run)}\t")
        i = j
    return out


def lengths(book: str, syn_row: dict, kjv_row: dict, slen: dict, klen: dict) -> dict:
    """{kjv chapter: (rows with both, correlation)} of the words' lengths."""
    rows: dict = {}
    for s, r in syn_row.items():
        rows.setdefault(r, [0, 0])[0] += slen[book][s]
    for k, r in kjv_row.items():
        rows.setdefault(r, [0, 0])[1] += klen[book][k]
    by: dict = {}
    for r, (a, b) in rows.items():
        if a and b and r[2] == 0:
            by.setdefault(r[0], []).append((a, b))
    out = {}
    for c, xs in by.items():
        if len(xs) >= 4:
            sa, kb = zip(*xs)
            try:
                out[c] = (len(xs), statistics.correlation(sa, kb))
            except statistics.StatisticsError:
                out[c] = (len(xs), 1.0)
    return out


HEAD = "synodal\tkjv\twhy\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true", help="and copy it to data/rsb/ where nothing is left unread")
    args = ap.parse_args(argv)
    if args.fetch:
        fetch()
        return 0
    syn, kjv, slen, klen = copies()
    if args.check:
        rules = versify.read(TABLE)
        low = []
        for b in kjv:
            sr, kr = versify.place(b, syn[b], kjv[b], rules)
            low += [(b, c, n, r) for c, (n, r) in lengths(b, sr, kr, slen, klen).items() if r < 0.8]
        print(f"{TABLE.relative_to(ROOT)}: every verse of both in one row; "
              f"{len(low)} chapters whose lengths correlate below 0.8")
        return 0
    mapped = compose(syn, kjv)
    lines = [why(x) for x in table(syn, kjv, mapped)]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    proposed = OUTDIR / "versification.tsv"
    proposed.write_text(HEAD + "".join(x + "\n" for x in lines), encoding="utf-8")
    rules = versify.read(proposed)
    failed, low, open_ = [], [], []
    for b in kjv:
        try:
            sr, kr = versify.place(b, syn[b], kjv[b], rules)
        except SystemExit as e:
            failed.append(f"- **{b}**: {e}")
            continue
        for c, (n, r) in sorted(lengths(b, sr, kr, slen, klen).items()):
            if r < 0.8:
                low.append(f"{b} {c} ({r:.2f})")
        sure = set(CONFIRMED.get(b, "").split())
        for s_, ks in disagreements(b, syn[b], kjv[b], mapped[b], slen, klen).items():
            if f"{s_[0]}:{s_[1]}" not in sure:
                open_.append(f"- {b} {s_[0]}:{s_[1]}: the table {ks[0]}, the lengths {ks[1]}")
    (OUTDIR / "review.md").write_text(
        "# The Synodal's numbering against the KJV's\n\n"
        f"{len(lines)} lines in var/rsb/versification.tsv, from SIL's rso and eng composed through the "
        f"Hebrew's numbering, {len(READ)} runs read and set right, and {sum(len(v.split()) for v in CONFIRMED.values())} "
        "verses where the lengths misled, read and left.\n\n## The witness's own slips\n\n"
        + ("\n".join(f"- {x}" for x in SLIPS) or "none")
        + "\n\n## Set right by reading\n\n" + "\n".join(f"- {a} = {b or 'the Synodal alone'}: {w}" for a, b, w in READ)
        + "\n\n## Placing failed\n\n" + ("\n".join(failed) or "none")
        + "\n\n## The lengths disagree, not yet read\n\n" + ("\n".join(open_) or "none")
        + f"\n\n## Chapters whose lengths correlate below 0.8 ({len(low)}; poetry of even lines, mostly)\n\n"
        + ", ".join(low) + "\n", encoding="utf-8")
    print(f"var/rsb/versification.tsv: {len(lines)} lines; {len(failed)} books failed to place, "
          f"{len(open_)} verses where the lengths disagree unread (var/rsb/review.md)")
    if args.write and not failed and not open_:
        TABLE.write_text(proposed.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"written to {TABLE.relative_to(ROOT)}")
    return 0


def disagreements(book: str, syn: list, kjv: list, m: dict, slen: dict, klen: dict) -> dict:
    """{synodal verse: (the table's, the lengths')} where the aligner, run
    chapter by chapter within the table's rows, places a verse otherwise."""
    by: dict = {}
    for s_ in syn:
        if m[s_]:
            by.setdefault(m[s_][0][0], []).append(s_)
    out = {}
    for c in sorted({k[0] for k in kjv}):
        ss, ks = by.get(c, []), [k for k in kjv if k[0] == c]
        if not ss:
            continue
        al = align(book, ss, ks, {book: {x: slen[book][x] for x in ss}}, {book: {x: klen[book][x] for x in ks}})
        for s_ in ss:
            if sorted(al[s_]) != sorted(m[s_]):
                out[s_] = (" ".join(f"{x[0]}:{x[1]}" for x in m[s_]) or "-",
                           " ".join(f"{x[0]}:{x[1]}" for x in al[s_]) or "-")
    return out


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
