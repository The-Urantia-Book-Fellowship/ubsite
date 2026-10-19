"""The British Study Edition's notes, one reviewed paper at a time.

The edition's 404 `\\fnst` notes are not imported: each is read, checked and
edited by hand (Tigran, 2026-10-18), so that a note asserts as fact nothing a
reader could not check, and a paper reaches the site only with its reviewed copy,
data/study/NNN.toml.  A paper without one has no study notes.  The rules of
that review are data/study/README.md; this module holds a copy to them where
a machine can:

  * Every `\\fnst` and `\\bibitem` of the paper, as the edition has them at the
    commit build/config.py pins, is in the copy exactly once: carried, as a
    [[note]] or [[source]], or [[dropped]] with the reason.  Each names its
    original by `origin`, 16 hex digits of the SHA-256 of what it was made
    from, so a note the editor changes upstream fails the build until it is
    reviewed again, and so does a note added.  A source the edition lacks may
    be added, `origin = "none"`, where the review finds the work a note quotes:
    Ellen G. White's, which Paper 1's notes quote and the edition does not list.
    So may a note, where what the review found is not the editor's to sign:
    at 2:1.1 the note on "touching" is Tigran's, and Block's finding that the
    paragraph's verses are Nave's a note of its own, credited to Block
    (Tigran, 2026-10-19).
  * The copy names the chart of Matthew Block's it was checked against, the
    address `../block-sources/MANIFEST.tsv` gives the paper's chart, or "none".
    A chart revised since, or a chart where there was none, fails the build:
    a note on a human source is never older than the chart it relies on.  It
    names the chart's date too, `chart_date`, as Block dates it on its first
    page, which the card's credit gives (Tigran, 2026-10-19): the address's
    month is when it was uploaded, 2023-07 for a chart of March 14, 2023.  The
    build reads no PDF, so it holds the date only to be no later than that
    month, which all 139 dated charts were (2026-10-19); tests/test_study.py
    holds it to the chart itself.
  * A note credited to Block that corrects his chart from the original says
    what it gives for his, `corrects`, and the card's credit says so (Tigran,
    2026-10-19): at 2:7.6, p. 788 for his 610.  Only such a note may.
  * A note stands in the press text after the words its `after` gives, which
    occur once in the paragraph and end a word.  The study text is British
    and metricated (23:3.2 "299,789 kilometres" for "186,280 miles"), so an
    offset in it says nothing about the press's.

A note becomes a footnote of kind 'study' on its paragraph, appended after the
press's own notes: `footnote.ord`, and with it every 1955 reading's key and
its /…#note… link, must never move because a study note came before it.  Its
marker carries a number, from 1 in each paper in reading order.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import hashlib
import pathlib
import re
import tomllib

from . import texmath
from .expand import Expander, Note, Span, _raw
from .problems import Report
from .readers import study as reader
from .render import render, strip_tags
from .study_macros import ITALIC_OPENERS, SUBS, TABLE

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "study"
RE_FILE = re.compile(r"\d{3}\.toml")
RE_TARGET = re.compile(r"p(\d+) (\d+):(\d+)")
RE_MONTH = re.compile(r"/uploads/(\d{4})/(\d{2})/")
SENTINEL = 0xE000                    # a private-use character stands for each $...$
# A hyphen that begins a word, a suffix's or an ending's ("the Latin suffix
# -tia", "-el/-al"): a browser may break a line after any hyphen, and left
# "-" alone at a line's end (Tigran, 2026-10-18).  Held to its letters.
RE_LEADING_HYPHEN = re.compile(r"(?:^|(?<=[\s(\[/“‘]))-[^\W\d_]+")
# Words joined by ties (~, \,) break as one, and a long run of them leaves a
# gap at the end of the line before it: "Sir~Arthur~S.\,Eddington" did
# (Tigran, 2026-10-18).  A tie goes after a title or an abbreviation (Dr~, p.~)
# and inside a reference (Psalms~104:2), never through a whole name.
# Measured between the places a line may break anyway: a space, a dash, a slash.
RE_TIED = re.compile(r"[^\s\u00a0\u202f—–/-]+(?:[\u00a0\u202f][^\s\u00a0\u202f—–/-]+)+")
TIED_MAX = 24

KEYS = {"paper", "chart", "chart_date", "study", "reviewed", "source", "note", "dropped"}
SOURCE_KEYS = {"key", "origin", "tex"}
NOTE_KEYS = {"at", "after", "origin", "tex", "credit", "corrects"}
DROPPED_KEYS = {"at", "key", "origin", "why"}
ADDED = "none"                       # the origin of a note or source the review added


@dataclasses.dataclass
class Curated:
    paper: int
    path: pathlib.Path
    sha256: str
    chart: str
    chart_date: datetime.date | None
    sources: list[dict]
    notes: list[dict]
    dropped: list[dict]


@dataclasses.dataclass
class Built:
    """What attach() made: the rows store() writes once the text is loaded."""
    papers: list[dict]
    sources: list[dict]
    notes: list[dict]


def load_curated(report, root: pathlib.Path = DATA) -> dict[int, Curated]:
    out: dict[int, Curated] = {}
    if not root.is_dir():
        return out
    for f in sorted(root.iterdir()):
        if f.suffix != ".toml":
            continue
        where = f"data/study/{f.name}"
        if not RE_FILE.fullmatch(f.name):
            report.hard("study-file-name", where, "a paper's notes are data/study/NNN.toml")
            continue
        raw = f.read_bytes()
        try:
            doc = tomllib.loads(raw.decode("utf-8"))
        except tomllib.TOMLDecodeError as e:
            report.hard("study-toml", where, str(e))
            continue
        bad = (set(doc) - KEYS
               | {f"source.{k}" for s in doc.get("source", []) for k in set(s) - SOURCE_KEYS}
               | {f"note.{k}" for s in doc.get("note", []) for k in set(s) - NOTE_KEYS}
               | {f"dropped.{k}" for s in doc.get("dropped", []) for k in set(s) - DROPPED_KEYS})
        if bad:
            report.hard("study-unknown-key", where, ", ".join(sorted(bad)))
            continue
        missing = ({k for k in ("paper", "chart") if k not in doc}
                   | {f"source.{k}" for s in doc.get("source", []) for k in SOURCE_KEYS - set(s)}
                   | {f"note.{k}" for s in doc.get("note", []) for k in NOTE_KEYS - {"credit", "corrects"} - set(s)}
                   | {f"dropped.{k}" for s in doc.get("dropped", []) for k in ("origin", "why")
                      if k not in s}
                   | {"dropped.at or dropped.key" for s in doc.get("dropped", [])
                      if ("at" in s) == ("key" in s)})
        if missing:
            report.hard("study-missing-key", where, ", ".join(sorted(missing)))
            continue
        if doc["paper"] != int(f.stem):
            report.hard("study-file-paper", where, f"says paper {doc['paper']}")
            continue
        dated = doc.get("chart_date")
        if (dated is None) != (doc["chart"] == "none"):
            report.hard("study-chart-date", where,
                        "a chart is named with its date, chart_date = YYYY-MM-DD, and none without")
            continue
        if dated is not None and type(dated) is not datetime.date:
            report.hard("study-chart-date", where, f"chart_date = {dated!r} is not a date")
            continue
        out[doc["paper"]] = Curated(doc["paper"], f, hashlib.sha256(raw).hexdigest(),
                                    doc["chart"], dated, doc.get("source", []), doc.get("note", []),
                                    doc.get("dropped", []))
    return out


def attach(papers, curated: dict[int, Curated], repo: dict, block: dict, report,
           hyphenator=None) -> Built:
    """Account for each admitted paper's notes and put them on the press text.

    Appends to each paragraph's `ex.notes` and `ex.spans`, before load_text
    renders it, so that one render gives `html` and `html_hy` with the markers.
    """
    built = Built([], [], [])
    if not curated:
        return built
    originals = reader.read(repo["tex"], repo["at"], sorted(curated), report)
    paras = {q.ref: q for p in papers for q in p.paragraphs}
    order = {q.ref: i for i, q in enumerate(q for p in papers for q in p.paragraphs)}
    for n, cur in sorted(curated.items()):
        where = f"data/study/{cur.path.name}"
        orig = originals.get(n)
        if orig is None:
            report.hard("study-paper-absent", where,
                        f"the edition has no p{n:03d}.tex at {repo['at'][:7]}")
            continue
        _account(cur, orig, where, report)
        dated = _chart(cur, block, where, report)
        sources = _sources(cur, paras, where, report)
        notes = _notes(cur, paras, order, sources, orig, where, report, hyphenator)
        built.papers.append({"paper_n": n, "file_sha256": cur.sha256, "study_commit": repo["at"],
                             "block_url": None if cur.chart == "none" else cur.chart,
                             "block_date": dated, "n_notes": len(notes),
                             "n_dropped": sum(1 for d in cur.dropped if "at" in d)})
        built.sources.extend(sources.values())
        built.notes.extend(notes)
    one_work_one_key(built.sources, report)
    return built


def one_work_one_key(sources: list[dict], report) -> None:
    """A key names one work in every paper, and a work has one key: the
    Bibliography (/lists/bibliography) lists a work once, by its key, with every
    note that cites it, in whichever paper (Tigran, 2026-10-19)."""
    html_of: dict[str, tuple[int, str]] = {}
    key_of: dict[str, tuple[int, str]] = {}
    for s in sources:
        where = f"data/study/{s['paper_n']:03d}.toml {s['key']}"
        n, html = html_of.setdefault(s["key"], (s["paper_n"], s["html"]))
        if html != s["html"]:
            report.hard("study-source-key", where,
                        f"Paper {n} has {s['key']} for another work, or words it differently")
        n, key = key_of.setdefault(s["html"], (s["paper_n"], s["key"]))
        if key != s["key"]:
            report.hard("study-source-key", where, f"Paper {n} has this work as {key}")


def _account(cur: Curated, orig, where: str, report) -> None:
    """Each original carried or dropped exactly once, and nothing else claimed."""
    have_n = collections.Counter(x.origin for x in orig.notes)
    have_s = collections.Counter(x.origin for x in orig.sources)
    ref_of = {x.origin: x.ref for x in orig.notes}
    key_of = {x.origin: x.key for x in orig.sources}
    got_n = collections.Counter([x["origin"] for x in cur.notes if x["origin"] != ADDED]
                                + [x["origin"] for x in cur.dropped if "at" in x])
    got_s = collections.Counter([x["origin"] for x in cur.sources if x["origin"] != ADDED]
                                + [x["origin"] for x in cur.dropped if "key" in x])
    for o in sorted(have_n - got_n):
        report.hard("study-unaccounted", where,
                    f"the edition's note {o} at {ref_of[o]} is neither carried nor dropped")
    for o in sorted(got_n - have_n):
        report.hard("study-origin-unknown", where,
                    f"no note of the edition is {o}: changed upstream since it was reviewed,"
                    " or claimed twice")
    for o in sorted(have_s - got_s):
        report.hard("study-unaccounted", where,
                    f"the edition's source {key_of[o]} ({o}) is neither carried nor dropped")
    for o in sorted(got_s - have_s):
        report.hard("study-origin-unknown", where,
                    f"no \\bibitem of the edition is {o}: changed upstream, or claimed twice")
    for x in cur.notes + [d for d in cur.dropped if "at" in d]:
        if x["origin"] in ref_of and ref_of[x["origin"]] != x["at"]:
            report.hard("study-moved", where,
                        f"{x['origin']} is the edition's note at {ref_of[x['origin']]},"
                        f" not at {x['at']}")
    for d in cur.dropped:
        if "key" in d and d["origin"] in key_of and key_of[d["origin"]] != d["key"]:
            report.hard("study-moved", where,
                        f"{d['origin']} is the edition's {key_of[d['origin']]}, not {d['key']}")


def _chart(cur: Curated, block: dict, where: str, report) -> str | None:
    """The date of the chart the notes were checked against, 'YYYY-MM-DD', or None."""
    if block["charts"] is None:
        report.hard("block-manifest-missing", str(block["path"]),
                    "no MANIFEST.tsv: refresh with ../explore-tools/block_fetch.py")
        return None
    row = block["charts"].get(cur.paper)
    if cur.chart == "none":
        if row:
            report.hard("block-chart-new", where,
                        f"Block has charted Paper {cur.paper} since it was reviewed"
                        f" ({row['url']}): review its notes against the chart")
        return None
    if not row or row["url"] != cur.chart:
        report.hard("block-chart-revised", where,
                    f"reviewed against {cur.chart}; the manifest now lists"
                    f" {row['url'] if row else 'no chart'}: review its notes against it")
        return None
    m = RE_MONTH.search(cur.chart)
    if not m:
        report.hard("block-chart-month", where, f"no /uploads/YYYY/MM/ in {cur.chart}")
        return None
    d = cur.chart_date
    if (d.year, d.month) > (int(m[1]), int(m[2])):
        report.hard("study-chart-date", where,
                    f"chart_date = {d} is after the chart was uploaded, {m[1]}-{m[2]}")
        return None
    return d.isoformat()


def _sources(cur: Curated, paras, where: str, report) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in cur.sources:
        if s["key"] in out:
            report.hard("study-source-twice", where, s["key"])
            continue
        text, html, _ = expand(s["tex"], paras, {}, f"{where} {s['key']}", report)
        out[s["key"]] = {"paper_n": cur.paper, "key": s["key"],
                         "origin": None if s["origin"] == ADDED else s["origin"],
                         "text": text, "html": html, "cited": 0}
    return out


def _notes(cur: Curated, paras, order, sources, orig, where, report,
           hyphenator=None) -> list[dict]:
    body_of = {x.origin: x.body for x in orig.notes}
    out: list[dict] = []
    last = None
    per_para: collections.Counter = collections.Counter()
    for i, nt in enumerate(cur.notes, 1):
        at = f"{where} note {i} ({nt['at']})"
        # Set first, so that what it cites is counted even if it cannot be placed.
        text, html, cites = expand(nt["tex"], paras, sources, at, report)
        html_hy = expand(nt["tex"], paras, sources, at, Report(), hyphenator)[1] if hyphenator else html
        for c in cites:
            if c in sources:
                sources[c]["cited"] += 1
        q = paras.get(nt["at"])
        if q is None or q.paper != cur.paper:
            report.hard("study-no-paragraph", at, f"Paper {cur.paper} has no {nt['at']}")
            continue
        a = _anchor(q.ex.text, nt["after"], at, report)
        if a is None:
            continue
        place = (order[q.ref], a)
        if last is not None and place < last:
            report.hard("study-order", at, "notes are listed in the order of the text")
        last = place
        credit = nt.get("credit")
        if credit == "block" and cur.chart == "none":
            report.hard("study-credit", at, "credited to Block's chart, and the paper has none")
        corrects = None
        if "corrects" in nt:
            if credit != "block":
                report.hard("study-corrects", at, "corrects Block's chart, and is not credited to it")
            ctext, corrects, ccites = expand(nt["corrects"], paras, sources, at, report)
            if ccites or not ctext.strip():
                report.hard("study-corrects", at, "`corrects` says what it gives for Block's, citing nothing")
        k = per_para[q.ref]
        per_para[q.ref] += 1
        num = len(out) + 1
        key = f"st{q.paper}_{q.section}_{q.n}_{k}"
        hs = bool(cites) or credit == "block"
        q.ex.notes.append(Note(a, "study", nt["tex"], text, [], html, html_hy))
        q.ex.spans.append(Span(a, a, "fnref", {"kind": "study", "key": key, "n": num, "hs": hs}))
        out.append({"paper_n": cur.paper, "ref": q.ref, "ord": len(q.ex.notes) - 1,
                    "num": num, "key": key, "after": nt["after"],
                    "origin": None if nt["origin"] == ADDED else nt["origin"],
                    "edited": int(nt["tex"].strip() != body_of.get(nt["origin"], "").strip()),
                    "human_source": int(hs), "credit": credit, "corrects": corrects,
                    "cites": cites})
    for s in sources.values():
        if not s["cited"]:
            report.hard("study-source-uncited", where,
                        f"{s['key']} is carried and no note cites it: drop it, with the reason")
    return out


def _anchor(text: str, after: str, where: str, report) -> int | None:
    """The offset just after `after`, which occurs once and is whole words."""
    if not after or after != after.strip():
        report.hard("study-after", where, f"{after!r}: no leading or trailing space")
        return None
    i = text.find(after)
    if i < 0:
        report.hard("study-after", where, f"{after!r} is not in the paragraph")
        return None
    if text.find(after, i + 1) >= 0:
        report.hard("study-after", where, f"{after!r} occurs more than once: say more")
        return None
    a = i + len(after)
    if (i > 0 and text[i - 1].isalnum() and after[0].isalnum()) or \
            (a < len(text) and text[a - 1].isalnum() and text[a].isalnum()):
        report.hard("study-after", where, f"{after!r} begins or ends inside a word")
        return None
    return a


def expand(tex: str, paras, sources: dict, where: str, report,
           hyphenator=None) -> tuple[str, str, list[str]]:
    """A note's or a source's TeX -> (text, html, the keys it cites, in order).

    `$...$` is taken out first, each replaced by one private-use character, and
    put back as MathML into the rendered HTML; so math inside a macro's
    argument stays where it was.  `text` is what the HTML says, tags stripped,
    which makes the round trip hold by construction.  With a `hyphenator`, the
    HTML carries the book's soft hyphens (build/hyphen.py), and `text` is
    still what it says without them.
    """
    if any(SENTINEL <= ord(c) < SENTINEL + 0x1000 for c in tex):
        report.hard("study-private-use", where, "the TeX holds a private-use character")
        return "", "", []
    dollars = reader.unescaped(tex, "$")
    if len(dollars) % 2:
        report.hard("study-math-unpaired", where, "an odd number of $")
        return "", "", []
    maths, pieces, last = [], [], 0
    for a, b in zip(dollars[::2], dollars[1::2]):
        pieces += [tex[last:a], chr(SENTINEL + len(maths))]
        maths.append(tex[a + 1:b])
        last = b + 1
    src = "".join(pieces) + tex[last:]
    cites: list[str] = []

    def cite(exp, opts, args, tok):
        key = _raw(args[0]).strip() if args else ""
        if key not in sources:
            report.hard("study-cite-unknown", where, f"\\cite{{{key}}}: no such source in the paper")
        if key not in cites:
            cites.append(key)
        exp._emit(f"[{cites.index(key) + 1}]")

    def bibref(exp, opts, args, tok):
        target = _raw(args[0]).strip() if args else ""
        m = RE_TARGET.fullmatch(target)
        if not m:
            report.hard("study-bibref", where, f"\\bibref target {target!r}")
            return
        ref = f"{int(m[1])}:{int(m[2])}.{int(m[3])}"
        shown = (opts[0] or ref).strip() if opts else ref
        href = "/" + ref
        if shown != ref:
            r = re.fullmatch(re.escape(ref) + r"--(\d+)", shown)
            end = f"{int(m[1])}:{int(m[2])}.{r[1]}" if r else None
            if not r or end not in paras or int(r[1]) <= int(m[3]):
                report.hard("study-bibref", where, f"shows {shown!r} for {target!r}")
                return
            href = f"/{ref}-{r[1]}"
        if ref not in paras:
            report.hard("study-bibref", where, f"{ref}: no such paragraph")
            return
        start = exp.n
        exp._text(shown)
        exp.spans.append(Span(start, exp.n, "link", {"href": href}))

    def myurl(exp, opts, args, tok):
        url = _raw(args[0]).strip() if args else ""
        start = exp.n
        exp._emit(url)
        exp.spans.append(Span(start, exp.n, "link", {"href": url}))

    def bibfrac(exp, opts, args, tok):
        exp._emit(f"{_raw(args[0]).strip()}/{_raw(args[1]).strip()}")

    exp = Expander(TABLE, set(), report, where, italic_openers=ITALIC_OPENERS,
                   calls={"cite": cite, "bibref": bibref, "myurl": myurl, "bibfrac": bibfrac},
                   subs=SUBS, forbid_comments=True)
    ex = exp.run(src)
    ex.spans += [Span(m.start(), m.end(), "nobreak") for m in RE_LEADING_HYPHEN.finditer(ex.text)]
    for m in RE_TIED.finditer(ex.text):
        run = m.group().strip("()[],.;:")
        name = len(re.split("[\u00a0\u202f]", run)) >= 3 and not re.search(r"\d:\d", run)
        if name or len(run) > TIED_MAX:
            report.warn("study-long-tie", where,
                        f"{m.group()!r} cannot break: tie after a title or an abbreviation only")
    for i in range(len(maths)):
        if ex.text.count(chr(SENTINEL + i)) != 1:
            report.hard("study-math-lost", where, f"${maths[i]}$ did not survive its macro")
    html = render(ex.text, ex.spans, shy=hyphenator.points(ex.text, ex.spans) if hyphenator else ())
    for i, m in enumerate(maths):
        try:
            html = html.replace(chr(SENTINEL + i), texmath.convert(m))
        except texmath.MathError as e:
            report.hard("study-math", where, f"${m}$: {e}")
    return strip_tags(html).replace("\u00ad", ""), html, cites


def store(con, built: Built) -> None:
    """The study_* rows, once load_text has made each note its footnote."""
    con.executemany(
        "INSERT INTO study_paper VALUES (:paper_n, :file_sha256, :study_commit, :block_url,"
        " :block_date, :n_notes, :n_dropped)", built.papers)
    source_id = {}
    for i, s in enumerate(built.sources, 1):
        con.execute("INSERT INTO study_source VALUES (?,?,?,?,?,?)",
                    (i, s["paper_n"], s["key"], s["origin"], s["text"], s["html"]))
        source_id[(s["paper_n"], s["key"])] = i
    for nt in built.notes:
        (fid,) = con.execute(
            "SELECT f.id FROM footnote f JOIN paragraph p ON p.id = f.paragraph_id"
            " WHERE p.ref = ? AND f.ord = ? AND f.kind = 'study'", (nt["ref"], nt["ord"])).fetchone()
        con.execute("INSERT INTO study_note VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (fid, nt["paper_n"], nt["num"], nt["key"], nt["origin"], nt["after"],
                     nt["edited"], nt["human_source"], nt["credit"], nt["corrects"]))
        con.executemany("INSERT INTO study_cite VALUES (?,?,?)",
                        [(fid, source_id[(nt["paper_n"], k)], j)
                         for j, k in enumerate(nt["cites"]) if (nt["paper_n"], k) in source_id])
