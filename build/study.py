"""The British Study Edition's notes, one reviewed paper at a time.

The edition's 404 `\\fnst` notes are not imported: each is read, checked and
edited by hand (Tigran, 2026-10-18), so that a note asserts nothing a reader
could not check, and a paper reaches the site only with its reviewed copy,
data/study/NNN.toml.  A paper without one has no study notes.  The rules of
that review are data/study/README.md; this module holds a copy to them where
a machine can:

  * Every `\\fnst` and `\\bibitem` of the paper, as the edition has them at the
    commit build/config.py pins, is in the copy exactly once: carried, as a
    [[note]] or [[source]], or [[dropped]] with the reason.  Each names its
    original by `origin`, 16 hex digits of the SHA-256 of what it was made
    from, so a note the editor changes upstream fails the build until it is
    reviewed again, and so does a note added.
  * The copy names the chart of Matthew Block's it was checked against, the
    address `../block-sources/MANIFEST.tsv` gives the paper's chart, or "none".
    A chart revised since, or a chart where there was none, fails the build:
    a note on a human source is never older than the chart it relies on.
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
import hashlib
import pathlib
import re
import tomllib

from . import texmath
from .expand import Expander, Note, Span, _raw
from .readers import study as reader
from .render import render, strip_tags
from .study_macros import ITALIC_OPENERS, SUBS, TABLE

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "study"
RE_FILE = re.compile(r"\d{3}\.toml")
RE_TARGET = re.compile(r"p(\d+) (\d+):(\d+)")
RE_MONTH = re.compile(r"/uploads/(\d{4})/(\d{2})/")
SENTINEL = 0xE000                    # a private-use character stands for each $...$

KEYS = {"paper", "chart", "study", "reviewed", "source", "note", "dropped"}
SOURCE_KEYS = {"key", "origin", "tex"}
NOTE_KEYS = {"at", "after", "origin", "tex", "credit"}
DROPPED_KEYS = {"at", "key", "origin", "why"}


@dataclasses.dataclass
class Curated:
    paper: int
    path: pathlib.Path
    sha256: str
    chart: str
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
                   | {f"note.{k}" for s in doc.get("note", []) for k in NOTE_KEYS - {"credit"} - set(s)}
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
        out[doc["paper"]] = Curated(doc["paper"], f, hashlib.sha256(raw).hexdigest(),
                                    doc["chart"], doc.get("source", []), doc.get("note", []),
                                    doc.get("dropped", []))
    return out


def attach(papers, curated: dict[int, Curated], repo: dict, block: dict, report) -> Built:
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
        month = _chart(cur, block, where, report)
        sources = _sources(cur, paras, where, report)
        notes = _notes(cur, paras, order, sources, month, orig, where, report)
        built.papers.append({"paper_n": n, "file_sha256": cur.sha256, "study_commit": repo["at"],
                             "block_url": None if cur.chart == "none" else cur.chart,
                             "block_month": month, "n_notes": len(notes),
                             "n_dropped": sum(1 for d in cur.dropped if "at" in d)})
        built.sources.extend(sources.values())
        built.notes.extend(notes)
    return built


def _account(cur: Curated, orig, where: str, report) -> None:
    """Each original carried or dropped exactly once, and nothing else claimed."""
    have_n = collections.Counter(x.origin for x in orig.notes)
    have_s = collections.Counter(x.origin for x in orig.sources)
    ref_of = {x.origin: x.ref for x in orig.notes}
    key_of = {x.origin: x.key for x in orig.sources}
    got_n = collections.Counter([x["origin"] for x in cur.notes]
                                + [x["origin"] for x in cur.dropped if "at" in x])
    got_s = collections.Counter([x["origin"] for x in cur.sources]
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
    """The month of the chart the notes were checked against, 'YYYY-MM', or None."""
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
    return f"{m[1]}-{m[2]}"


def _sources(cur: Curated, paras, where: str, report) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in cur.sources:
        if s["key"] in out:
            report.hard("study-source-twice", where, s["key"])
            continue
        text, html, _ = expand(s["tex"], paras, {}, f"{where} {s['key']}", report)
        out[s["key"]] = {"paper_n": cur.paper, "key": s["key"], "origin": s["origin"],
                         "text": text, "html": html, "cited": 0}
    return out


def _notes(cur: Curated, paras, order, sources, month, orig, where, report) -> list[dict]:
    body_of = {x.origin: x.body for x in orig.notes}
    out: list[dict] = []
    last = None
    per_para: collections.Counter = collections.Counter()
    for i, nt in enumerate(cur.notes, 1):
        at = f"{where} note {i} ({nt['at']})"
        # Set first, so that what it cites is counted even if it cannot be placed.
        text, html, cites = expand(nt["tex"], paras, sources, at, report)
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
        k = per_para[q.ref]
        per_para[q.ref] += 1
        num = len(out) + 1
        key = f"st{q.paper}_{q.section}_{q.n}_{k}"
        hs = bool(cites) or credit == "block"
        q.ex.notes.append(Note(a, "study", nt["tex"], text, [], html))
        q.ex.spans.append(Span(a, a, "fnref", {"kind": "study", "key": key, "n": num, "hs": hs}))
        out.append({"paper_n": cur.paper, "ref": q.ref, "ord": len(q.ex.notes) - 1,
                    "num": num, "key": key, "origin": nt["origin"], "after": nt["after"],
                    "edited": int(nt["tex"].strip() != body_of.get(nt["origin"], "").strip()),
                    "human_source": int(hs), "credit": credit, "cites": cites})
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


def expand(tex: str, paras, sources: dict, where: str, report) -> tuple[str, str, list[str]]:
    """A note's or a source's TeX -> (text, html, the keys it cites, in order).

    `$...$` is taken out first, each replaced by one private-use character, and
    put back as MathML into the rendered HTML; so math inside a macro's
    argument stays where it was.  `text` is what the HTML says, tags stripped,
    which makes the round trip hold by construction.
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
    for i in range(len(maths)):
        if ex.text.count(chr(SENTINEL + i)) != 1:
            report.hard("study-math-lost", where, f"${maths[i]}$ did not survive its macro")
    html = render(ex.text, ex.spans)
    for i, m in enumerate(maths):
        try:
            html = html.replace(chr(SENTINEL + i), texmath.convert(m))
        except texmath.MathError as e:
            report.hard("study-math", where, f"${m}$: {e}")
    return strip_tags(html), html, cites


def store(con, built: Built) -> None:
    """The study_* rows, once load_text has made each note its footnote."""
    con.executemany(
        "INSERT INTO study_paper VALUES (:paper_n, :file_sha256, :study_commit, :block_url,"
        " :block_month, :n_notes, :n_dropped)", built.papers)
    source_id = {}
    for i, s in enumerate(built.sources, 1):
        con.execute("INSERT INTO study_source VALUES (?,?,?,?,?,?)",
                    (i, s["paper_n"], s["key"], s["origin"], s["text"], s["html"]))
        source_id[(s["paper_n"], s["key"])] = i
    for nt in built.notes:
        (fid,) = con.execute(
            "SELECT f.id FROM footnote f JOIN paragraph p ON p.id = f.paragraph_id"
            " WHERE p.ref = ? AND f.ord = ? AND f.kind = 'study'", (nt["ref"], nt["ord"])).fetchone()
        con.execute("INSERT INTO study_note VALUES (?,?,?,?,?,?,?,?,?)",
                    (fid, nt["paper_n"], nt["num"], nt["key"], nt["origin"], nt["after"],
                     nt["edited"], nt["human_source"], nt["credit"]))
        con.executemany("INSERT INTO study_cite VALUES (?,?,?)",
                        [(fid, source_id[(nt["paper_n"], k)], j)
                         for j, k in enumerate(nt["cites"]) if (nt["paper_n"], k) in source_id])
