"""The translations shown beside the text, joined to our numbering.

ROADMAP item 15, step 2.  Each translation is a master read at a commit
(build/config.py), one paper to a file (build/readers/translation.py), and every
one of its paragraphs is stored under OUR paragraph, the press's numbering,
which the English uses (Tigran, 2026-10-26).  Where a translation numbers
otherwise, tests/known-tr-numbering.tsv says how, and the build requires
exactly that list:

  * its addresses, once the list is applied, must be exactly ours, paper by
    paper: none left over, none missing, none twice.  A slot the list calls a
    separator ("-") holds no words;
  * its separators must stand where ours do, but for tests/known-tr-separators.tsv;
  * where our paragraph and its both open with a numbered list label, the
    numbers agree: a run joined one off would fail at its first list.

English and Russian cannot be compared word for word, as build/foundation.py
compares two Englishes, so these three are what holds a join to the text.

A paragraph is translated when it has words: ud leaves the rest empty, and
writes «Бла-бла...» in a skeleton paper's first.  A translated paragraph with
no Cyrillic in it fails: English left in a translation is a defect to fix,
not to show.  A paper's title and author, and a section's title, are stored as
the translation writes them, for each paper it translates in part or whole.

A translator's note (ud's \\fnst) stands at its place in the paragraph's text,
numbered through its paper, its marker in the paragraph's HTML, and is set as
build/study.py sets a study note, by its own table (build/tr_macros.py
UD_NOTES), with the works it cites from its paper's bibliography.  A
\\bibref whose words disagree with its target is set as its TeX sets it, the
words linking the target, and must be exactly tests/known-tr-bibrefs.tsv, a
slip to mend in the translation.  Each paragraph and note is hyphenated as its
own TeX would set it: hyph-ru, hyphenmins 2/2, and the translation's own
exception list (build/hyphen.py).
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import tomllib

from . import study
from .expand import Expander, Note, Span, _raw
from .hyphen import RUSSIAN, Hyphenator
from .readers import translation as reader
from .readers._io import read_at_rev
from .render import render, strip_tags
from .tr_macros import SUBS, TABLES, UD_NOTES, VULGAR

ROOT = pathlib.Path(__file__).resolve().parent.parent
META = ROOT / "data" / "translations.toml"
KNOWN = ROOT / "tests" / "known-tr-numbering.tsv"
KNOWN_SEPS = ROOT / "tests" / "known-tr-separators.tsv"
KNOWN_LABELS = ROOT / "tests" / "known-tr-labels.tsv"
KNOWN_BIBREFS = ROOT / "tests" / "known-tr-bibrefs.tsv"

# How each translation's TeX is read, beyond its paper files: where its own
# hyphenation list is, and the Foreword's title, which urantia-ru's \uforeword
# takes from its style rather than writing.
#
# And where its style sets the Acknowledgment's heading otherwise than the paper
# file writes it: ud's p000.tex writes \usection{БЛАГОДАРНОСТЬ}, and ud.sty's
# \usection sets in italic the one title that is its \ackn,
# \ifx\secname\ackn\itshape.  urantia-ru writes its own italic, \bibemph.
STYLE = {
    "ud": {"hyphenation": "ud.sty", "ackn": "ud.sty"},
    "urantia-ru": {"hyphenation": "tex/urantia-hyphen-ru.tex",
                   "foreword": ("urantia-ru.sty", "forewordtoc")},
}
# Words that stand in for a paragraph not yet translated.
PLACEHOLDERS = {"Бла-бла..."}
# Characters a translation has that the site sets otherwise, each declared,
# with the paragraphs it is in, until the translation is mended: the build
# names each place.
SUBSTITUTE = {"urantia-ru": {"　": " "}}       # an ideographic space: 44:3.5, 53:4.6, 70:10.12
# The same in a translator's note, by its words, since its character may be
# right elsewhere in a note (in \textgreek): ud's at 0:5.12 writes Galen's
# century in Greek capital iotas, which UB Goudy has not, for the Roman II.
NOTE_SUBSTITUTE = {"ud": {"Галена ΙΙ века": "Галена II века"}}
RE_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
RE_LABEL = re.compile(r"\d+\.")
RE_REF = re.compile(r"(\d+):(\d+)\.(\d+)")

Key = tuple[int, int, int]


@dataclasses.dataclass(slots=True)
class TPara:
    key: Key                     # ours
    src: str                     # its own address, as written
    text: str
    spans: list[Span]
    shy: list[int]               # where a word may break (build/hyphen.py)
    notes: list[tuple[int, str]]  # (offset in text, the note as written)
    html_hy: str = ""            # with the notes' markers, once _notes() has set them
    set_notes: list[dict] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(slots=True)
class Built:
    key: str
    meta: dict
    commit: str
    paras: list[TPara]
    headings: list[tuple[int, int | None, str, str, str]]   # paper, section, kind, text, html
    seps: int
    sources: list[dict]          # the works its notes cite: paper_n, key, text, html


def meta() -> dict[str, dict]:
    """data/translations.toml, each entry checked for its fields."""
    with open(META, "rb") as fh:
        raw = tomllib.load(fh)
    for k, v in raw.items():
        missing = {"title", "lang", "by", "label"} - set(v)
        if missing or set(v["by"]) != {"en", "ru"} or not isinstance(v["label"], str):
            raise SystemExit(f"translation: data/translations.toml [{k}] wants title, lang, label,"
                             f" and by in en and ru")
    return raw


def _ref(s: str) -> Key:
    m = RE_REF.fullmatch(s)
    if not m:
        raise SystemExit(f"translation: {s!r} is no paragraph reference")
    return tuple(map(int, m.groups()))


def load_known(path: pathlib.Path = KNOWN) -> dict[str, list[tuple[str, str, str, str]]]:
    out: dict[str, list] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            k, *row = line.split("\t")
            out.setdefault(k, []).append(tuple(row))
    return out


def _mapping(rows) -> tuple[dict[Key, Key | None], dict[tuple[int, int], Key]]:
    """The runs as {their key: our key, or None}, and {(paper, section): our
    key} for a section's title standing inside it."""
    m: dict[Key, Key | None] = {}
    titles: dict[tuple[int, int], Key] = {}
    for a, b, c, d in rows:
        if a.startswith("title "):
            p, s = map(int, a[6:].split(":"))
            titles[(p, s)] = _ref(c)
            continue
        ta, tb = _ref(a), _ref(b)
        if ta[:2] != tb[:2]:
            raise SystemExit(f"translation: a run across sections, {a}-{b}")
        if c == "-":
            for n in range(ta[2], tb[2] + 1):
                m[(*ta[:2], n)] = None
            continue
        oa, ob = _ref(c), _ref(d)
        if oa[:2] != ob[:2] or ob[2] - oa[2] != tb[2] - ta[2]:
            raise SystemExit(f"translation: {a}-{b} and {c}-{d} are not runs of one length")
        for i in range(tb[2] - ta[2] + 1):
            m[(*ta[:2], ta[2] + i)] = (*oa[:2], oa[2] + i)
    return m, titles


def _squeeze(text: str, spans: list[Span], notes: list[Note]) -> tuple[str, list[Span], list[Note]]:
    """The text with each run of spaces made one, and none at its ends: ud writes
    "вселенной  и" once or twice.  Spans and notes keep their places."""
    if "  " not in text and text == text.strip(" "):
        return text, spans, notes
    keep, at, out = [], 0, []
    for i, c in enumerate(text):
        drop = c == " " and (not out or out[-1] == " ")
        keep.append(at)
        if not drop:
            out.append(c)
            at += 1
    keep.append(at)
    while out and out[-1] == " ":
        out.pop()
    n = len(out)
    move = lambda x: min(keep[x], n)
    return ("".join(out),
            [Span(move(s.start), move(s.end), s.kind, s.attr) for s in spans],
            [dataclasses.replace(t, offset=move(t.offset)) for t in notes])


def _expander(key: str, report, where: str) -> Expander:
    table, unbraced, italic = TABLES[key]
    from latex_tokenizer import TokenStream          # on the path once expand is imported

    def li(exp, opts, args, tok):
        start = exp.n
        exp._expand(TokenStream(args[0]))
        if exp.n > start:
            exp.spans.append(Span(start, exp.n, "listmark"))
        exp._emit(" ")

    def fnst(exp, opts, args, tok):
        exp.notes.append(Note(exp.n, "translator", _raw(args[0]), "", []))

    def bibfrac(exp, opts, args, tok):
        n, d = _raw(args[0]).strip(), _raw(args[1]).strip()
        if not (n.isdigit() and d.isdigit()):
            report.hard("tr-fraction", f"{where}:{tok.line}", f"\\bibfrac{{{n}}}{{{d}}} is not two numbers")
        elif (n, d) in VULGAR:
            exp._emit(VULGAR[(n, d)])
        else:
            if exp.out and exp.out[-1][-1:].isdigit():
                exp._emit("\u2060")
            start = exp.n
            exp._emit(f"{n}\u2044{d}")
            exp.spans.append(Span(start, exp.n, "frac"))

    return Expander(table, set(), report, where, unbraced, italic,
                    calls={"li": li, "fnst": fnst, "bibfrac": bibfrac}, subs=SUBS, forbid_comments=True)


def _expand(key: str, body: str, report, where: str):
    ex = _expander(key, report, where).run(body)
    for ch, to in SUBSTITUTE.get(key, {}).items():
        if ch in ex.text:
            report.warn("tr-substituted", where, f"U+{ord(ch):04X} set as {to!r}: mend it in the translation")
            ex.text = ex.text.replace(ch, to)
    return _squeeze(ex.text, ex.spans, ex.notes)


def build(key: str, repo: dict, ours: dict[Key, dict], report) -> Built:
    """One translation, read at its commit, joined to `ours`:
    {(paper, section, n): {"sep": bool, "label": str | None}} for every paragraph."""
    info = meta()[key]
    style = STYLE[key]
    foreword = None
    if "foreword" in style:
        f, name = style["foreword"]
        m = re.search(r"\\def\\" + name + r"\{([^{}]*)\}", read_at_rev(repo["path"], f, repo["at"]))
        if not m:
            report.hard("tr-foreword-untitled", f"{key}:{f}", f"no \\def\\{name}")
        foreword = m.group(1) if m else None
    papers = reader.read(key, repo["tex"], repo["at"], report, foreword)
    hyph = Hyphenator(hyphenation(key, repo, report), RUSSIAN)
    mapping, titles = _mapping(load_known().get(key, []))
    used: set[Key] = set()
    used_titles: set[tuple[int, int]] = set()

    paras: list[TPara] = []
    headings = []
    theirs_seps: set[str] = set()
    labels_differ = []
    for n, paper in papers.items():
        where = f"{key}:p{n:03d}.tex"
        image: dict[Key, Key] = {}
        before_sep = False                       # a numbered separator awaits its paragraph
        got_any = False
        for q in paper.paras:
            k = (n, *q.key)
            o = mapping.get(k, k)
            if k in mapping:
                used.add(k)
            src = f"{n}:{q.section}.{q.n}"
            if o is None:                        # a separator it numbers
                if q.body not in ("", reader.SEPARATOR):
                    report.hard("tr-separator-has-words", f"{where}:{q.line}",
                                f"{src} is declared a separator and holds {q.body[:40]!r}")
                before_sep = True
                continue
            if o in image.values():
                report.hard("tr-numbering-twice", f"{where}:{q.line}",
                            f"{src} and another are both our {o[0]}:{o[1]}.{o[2]}")
            image[k] = o
            if before_sep:
                theirs_seps.add(_fmt(o))
                before_sep = False
            if o not in ours:
                continue                         # reported below, with the rest
            text, spans, notes = _expand(key, q.body, report, f"{where}:{q.line}")
            if not text or text in PLACEHOLDERS:
                continue
            if not RE_CYRILLIC.search(text):
                report.hard("tr-not-russian", f"{where}:{q.line}", f"{src} has no Cyrillic: {text[:50]!r}")
                continue
            got_any = True
            if "­" in text:
                report.hard("soft-hyphen-in-text", f"{where}:{q.line}", "the text itself has a U+00AD")
            lead = next((x for x in spans if x.kind == "listmark" and x.start == 0), None)
            theirs_label, our_label = lead and text[:lead.end], ours[o]["label"]
            if (theirs_label and our_label and RE_LABEL.fullmatch(theirs_label)
                    and RE_LABEL.fullmatch(our_label) and theirs_label != our_label):
                labels_differ.append((src, theirs_label, our_label))
            paras.append(TPara(o, src, text, spans, hyph.points(text, spans),
                               [(t.offset, t.raw) for t in notes]))
        for at, before in paper.seps:
            theirs_seps.add("end" if before is None else _fmt(mapping.get((n, *before), (n, *before))))
        # The paper's addresses, once joined, are exactly ours.
        want = {k for k in ours if k[0] == n}
        have = set(image.values())
        for (p, s), o in titles.items():
            if p == n:
                have.add(o)
        for o in sorted(want - have):
            report.hard("tr-numbering-missing", where, f"no paragraph of it is our {_fmt(o)}")
        for k, o in sorted(image.items()):
            if o not in want:
                report.hard("tr-numbering-extra", where,
                            f"its {_fmt(k)} would be our {_fmt(o)}, which we do not have")
        # Its headings, for a paper it translates.
        by_sec: dict[int, list] = {}
        for h in paper.sections:
            if h.before is not None:
                by_sec.setdefault(h.before[0], []).append(h)
        if got_any:
            for kind, h in (("title", paper.title), ("author", paper.author)):
                if h is not None:
                    headings.append(_heading(key, n, None, kind, h, report, where))
        done_secs = {p.key[1] for p in paras if p.key[0] == n}
        for s, hs in sorted(by_sec.items()):
            if len(hs) > 1:
                if (n, s) not in titles or len(hs) > 2:
                    report.hard("tr-title-twice", f"{where}:{hs[1].line}",
                                f"section {n}:{s} has {len(hs)} titles, and the list declares no heading in it")
                    continue
                used_titles.add((n, s))
                o = titles[(n, s)]
                text, spans, notes = _expand(key, hs[1].body, report, f"{where}:{hs[1].line}")
                if notes:
                    report.hard("tr-note-in-heading", f"{where}:{hs[1].line}", "a note in a heading")
                if "ackn" in STYLE[key]:
                    spans = _ackn(key, repo, hs[1].body, text, spans, report, f"{where}:{hs[1].line}")
                if text and o in ours:
                    paras.append(TPara(o, f"title {n}:{s}", text, spans, [], []))
            if s in done_secs:
                headings.append(_heading(key, n, s, "section", hs[0], report, where))
    for k in sorted(set(mapping) - used):
        report.hard("tr-numbering-gone", _fmt(k),
                    f"{KNOWN.name} declares {key}'s {_fmt(k)}, which it does not have")
    for p, s in sorted(set(titles) - used_titles):
        report.hard("tr-numbering-gone", f"{p}:{s}", f"{KNOWN.name} declares a title inside {key}'s"
                    f" {p}:{s}, which has none")
    known = {tuple(r) for k, *r in _rows(KNOWN_LABELS) if k == key}
    for x in sorted(set(labels_differ) - known):
        report.hard("tr-label-differs", f"{key} {x[0]}",
                    f"its list label {x[1]} where ours is {x[2]}, not in {KNOWN_LABELS.name}")
    for x in sorted(known - set(labels_differ)):
        report.hard("tr-label-gone", f"{key} {x[0]}",
                    f"{KNOWN_LABELS.name} declares its label {x[1]} for our {x[2]}, and that is no longer so")
    _separators(key, theirs_seps, {_fmt(k) for k, v in ours.items() if v["sep"]}, report)
    paras.sort(key=lambda p: p.key)
    sources = _notes(key, paras, papers, mapping, ours, hyph, report)
    return Built(key, info, repo["commit"], paras, headings, len(theirs_seps), sources)


# Each translation with notes: how they are set (build/study.py expand).
NOTES = {"ud": UD_NOTES}


def _textbf(exp, opts, args, tok):
    from latex_tokenizer import TokenStream          # on the path once expand is imported
    start = exp.n
    exp._expand(TokenStream(args[0]))
    exp.spans.append(Span(start, exp.n, "strong"))


def set_note(key: str, tex: str, refs, bib: dict, where: str, report, hyph=None,
             ref_of=None, odd: list | None = None) -> tuple[str, str, list[str]]:
    """A translator's note, or a work it cites, set as build/study.py sets a
    study note: by the translation's own table and quotes, its Hebrew turned,
    and with no warning of long ties, which are the translator's to set."""
    return study.expand(tex, refs, bib, where, report, hyph, table=NOTES[key], subs=SUBS,
                        ref_of=ref_of, textheb=True, odd=odd, calls={"textbf": _textbf}, ties=False)


def _notes(key, paras, papers, mapping, ours, hyph, report) -> list[dict]:
    """Each paragraph's notes set, numbered 1.. through its paper in reading
    order, and its HTML with their markers; the works they cite, once a paper.

    A \\bibref's target is as the translation numbers it: where that is not
    ours, it is not linked but fails, since its words would be its numbering
    and its link ours.  None does (2026-10-26)."""
    refs = {_fmt(k) for k in ours}
    ref_of = lambda p, s, n: None if (p, s, n) in mapping else _fmt((p, s, n))
    sources: dict[tuple[int, str], dict] = {}
    odd: list[tuple[str, str, str]] = []
    num: dict[int, int] = {}
    for p in paras:
        n = p.key[0]
        if p.notes and key not in NOTES:
            report.hard("tr-notes-unset", f"{key} {_fmt(p.key)}", "a note, and no table to set it by")
            p.notes = []
        bib = dict(papers[n].sources) if n in papers else {}
        markers = []
        for k, (at, tex) in enumerate(p.notes):
            num[n] = num.get(n, 0) + 1
            where = f"{key} {_fmt(p.key)} note {num[n]}"
            src = tex                            # stored as written
            for was, to in NOTE_SUBSTITUTE.get(key, {}).items():
                if was in src:
                    report.warn("tr-substituted", where, f"{was!r} set as {to!r}: mend it in the translation")
                    src = src.replace(was, to)
            got: list[tuple[str, str]] = []
            text, html_hy, cites = set_note(key, src, refs, bib, where, report, hyph, ref_of, got)
            odd += [(_fmt(p.key), words, target) for words, target in got]
            if "\\" in text:
                report.hard("tr-note-backslash", where, "a backslash in what the note says")
            for c in cites:
                if c in bib and (n, c) not in sources:
                    sources[(n, c)] = {"paper_n": n, "key": c, "tex": bib[c]}
            nkey = f"tn_{key}_{p.key[0]}_{p.key[1]}_{p.key[2]}_{k}"
            markers.append(Span(at, at, "fnref", {"kind": "translator", "key": nkey, "n": num[n]}))
            p.set_notes.append({"num": num[n], "at": at, "key": nkey, "tex": tex, "text": text,
                                "html_hy": html_hy, "cites": cites})
        p.html_hy = render(p.text, p.spans + markers, shy=p.shy)
    known = {tuple(r) for k, *r in _rows(KNOWN_BIBREFS) if k == key}
    for x in sorted(set(odd) - known):
        report.hard("tr-bibref-differs", f"{key} {x[0]}",
                    f"a \\bibref shows {x[1]} and links {x[2]}, not in {KNOWN_BIBREFS.name}")
    for x in sorted(known - set(odd)):
        report.hard("tr-bibref-gone", f"{key} {x[0]}",
                    f"{KNOWN_BIBREFS.name} declares a \\bibref showing {x[1]} for {x[2]}, and that is no longer so")
    out = []
    for (n, c), src in sorted(sources.items()):
        text, html, _ = set_note(key, src["tex"], refs, {}, f"{key} p{n:03d} \\bibitem{{{c}}}", report,
                                 ref_of=ref_of)
        out.append({"paper_n": n, "key": c, "text": text, "html": html})
    return out


def _ackn(key, repo, body, text, spans, report, where):
    """The Acknowledgment's heading as the translation's style sets it: in
    italic, where its \\usection italicises the title that is its \\ackn.  A
    heading there that is not its \\ackn would be set as an ordinary numbered
    section, which none is, and fails."""
    f = STYLE[key]["ackn"]
    sty = read_at_rev(repo["path"], f, repo["at"])
    m = re.search(r"\\def\\ackn\{([^{}]*)\}", sty)
    if not m or body.strip() != m.group(1):
        report.hard("tr-ackn", where, f"the heading {body!r} is not {f}'s \\ackn"
                    + (f" {m.group(1)!r}" if m else ", which it does not define"))
        return spans
    if "\\ifx\\secname\\ackn\\itshape" in sty and not any(
            x.kind == "em" and x.start == 0 and x.end == len(text) for x in spans):
        spans = [Span(0, len(text), "em"), *spans]
    return spans


def hyphenation(key: str, repo: dict, report) -> list[str]:
    """The translation's own \\hyphenation list, at the commit read."""
    f = STYLE[key]["hyphenation"]
    return reader.read_hyphenation(read_at_rev(repo["path"], f, repo["at"]), f"{key}:{f}", report)


def _heading(key, paper, section, kind, h, report, where):
    text, spans, notes = _expand(key, h.body, report, f"{where}:{h.line}")
    if notes:
        report.hard("tr-note-in-heading", f"{where}:{h.line}", "a note in a heading")
    if not RE_CYRILLIC.search(text):
        report.hard("tr-not-russian", f"{where}:{h.line}", f"a {kind} with no Cyrillic: {text[:50]!r}")
    return (paper, section, kind, text, render(text, spans))


def _fmt(k: Key) -> str:
    return f"{k[0]}:{k[1]}.{k[2]}"


def _rows(path: pathlib.Path) -> list[list[str]]:
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _separators(key: str, theirs: set[str], ours: set[str], report) -> None:
    want = {(at, who) for k, at, who in _rows(KNOWN_SEPS) if k == key}
    got = {(x, "theirs") for x in theirs - ours} | {(x, "ours") for x in ours - theirs}
    for at, who in sorted(got - want):
        report.hard("tr-separator-undeclared", f"{key} {at}",
                    f"a separator only {who} has, not in {KNOWN_SEPS.name}")
    for at, who in sorted(want - got):
        report.hard("tr-separator-gone", f"{key} {at}",
                    f"{KNOWN_SEPS.name} declares a separator only {who} has, and that is no longer so")


def ours(con) -> dict[Key, dict]:
    """Every paragraph of ours, with whether a separator stands before it and its
    list label, if it opens with one."""
    out = {}
    for pid, p, s, n, sep, text in con.execute(
            "SELECT id, paper_n, section_n, para_n, sep_before, text FROM paragraph"):
        out[(p, s, n)] = {"id": pid, "sep": sep is not None, "label": None, "text": text}
    by_id = {v["id"]: v for v in out.values()}
    for pid, a, b in con.execute("SELECT paragraph_id, start, end FROM span WHERE kind='listmark' AND start=0"):
        by_id[pid]["label"] = by_id[pid]["text"][a:b]
    return out


def store(con, built: list[Built], ours_: dict[Key, dict]) -> None:
    for i, b in enumerate(built):
        m = b.meta
        con.execute("INSERT INTO translation VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (b.key, m["lang"], m["title"], len(b.paras), sum(len(p.notes) for p in b.paras),
                     b.commit, i, m["by"]["en"], m["by"]["ru"], m["label"]))
        source_id = {}
        for s in b.sources:
            cur = con.execute("INSERT INTO tr_source (translation, paper_n, key, text, html) VALUES (?,?,?,?,?)",
                              (b.key, s["paper_n"], s["key"], s["text"], s["html"]))
            source_id[(s["paper_n"], s["key"])] = cur.lastrowid
        for p in b.paras:
            pid = ours_[p.key]["id"]
            con.execute("INSERT INTO tr_paragraph VALUES (?,?,?,?,?)",
                        (b.key, pid, None if p.src == _fmt(p.key) else p.src, p.text, p.html_hy))
            for nt in p.set_notes:
                cur = con.execute(
                    "INSERT INTO tr_note (translation, paragraph_id, num, at, key, tex, text, html_hy)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (b.key, pid, nt["num"], nt["at"], nt["key"], nt["tex"], nt["text"], nt["html_hy"]))
                con.executemany("INSERT INTO tr_cite VALUES (?,?,?)",
                                [(cur.lastrowid, source_id[(p.key[0], c)], j) for j, c in enumerate(nt["cites"])
                                 if (p.key[0], c) in source_id])
        con.executemany("INSERT INTO tr_heading VALUES (?,?,?,?,?,?)",
                        [(b.key, *h) for h in b.headings])


def roundtrip(con, report) -> None:
    """Each stored paragraph's HTML, its soft hyphens taken out and its tags
    stripped, is its text: the contract every renderer here keeps."""
    for k, pid, text, hy in con.execute("SELECT translation, paragraph_id, text, html_hy FROM tr_paragraph"):
        if strip_tags(hy.replace("­", "")) != text:
            report.hard("tr-roundtrip", f"{k} {pid}", "its HTML is not its text")
