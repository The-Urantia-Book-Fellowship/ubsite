"""The SRT Committee's reasons for the changes to the 1955 text.

The Fellowship and the Foundation formed a joint committee (2007-09, again in
2014-15) to settle every proposed change to the 1955 text, and the Fellowship
publishes what it decided and why (config.srt()).  The press prints a
1955 reading (`\\fnc`) wherever the text departs from the first printing; this
gives each of those its reason, as the committee wrote it.

The page is kept as a snapshot of its two tables (tools/srt/snapshot.py), and
this reads only the snapshot.  Each row is one place in the book, named by its
anchor on the page ("U41_4_4") and by its reference in the FOUNDATION's
numbering, which is mapped to ours through uf_paragraph (build/foundation.py).
A row holds one change or several -- 134:3.3 has three -- and each becomes an
`srt_item`:

  1955 text   the passage as the page quotes it, the changed words underlined
              (-> `chg`).  It pairs a note with its change and is never shown:
              the page has errors of its own, and misquotes 1955 itself
              (85:4.1, 90:2.9).  What 1955 printed is the press's note alone.
  Review      what was proposed (kept as text; not shown)
  decision    Adopted, Rejected, No action required or taken, Informational,
              No decision made -- or none of its own, when the cell only says
              "See SRT note for 89:3.1 above", and then it is that note's
  reasons     what follows the decision, links rewritten to our paragraphs

A row's changes are divided by a dashed rule, or in a few rows by "also..."
between blank lines, and its decision cell is divided the same way or by blank
lines.  The two cells must divide into as many parts, or the decision cell into
one that speaks for all.  Anything the reader does not recognise -- a tag, a
label, a link -- is a hard failure.

Each 1955 note is then paired with the change it shows: the one among its
paragraph's whose underlined words and the note's own overlap.  What does not
pair one to one must be declared in tests/known-srt-deltas.tsv, exactly.
"""

from __future__ import annotations

import dataclasses
import difflib
import html
import html.parser
import pathlib
import re

from .render import render

ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RULE = re.compile(r'\s*(?:<div class="c1">\s*<p>- - - - - -</p>\s*</div>|<p>- - - - - -</p>)\s*')
ALSO = re.compile(r"(?:\s*<br>)+\s*also\.\.\.(?:\s*<br>)+\s*")
BLANKS = re.compile(r"(?:\s*<br>){3,}\s*")
BR = re.compile(r"\s*<br>\s*")
HEADER = re.compile(r"<!--.*?fetched:\s*(\S+).*?-->", re.S)

RE_NAME = re.compile(r'<a name="([^"]+)"></a>')
RE_PAGE = re.compile(r"\((\d+\.\d+)\)")
RE_REF = re.compile(r"^(\d+):(\d+)\.(\d+)$")
# A link to a place in the book: an entry on the page itself ("#U43_1_6"), or a
# paragraph of the Foundation's text.  Both name the Foundation's reference.
RE_BOOK = re.compile(r"^(?:https://www\.urantia\.org/urantia-book-standardized/[\w-]+)?#U(\d+)_(\d+)_(\d+)$")
RE_SEE = re.compile(r'\bsee\b[^<]*?<a href="#(U\d+_\d+_\d+)">([^<]*)</a>', re.I)

# The decision a cell opens with, as the page spells it, and what it means.
VERDICTS = {
    "Adopted": ("adopted", "Adopted"),
    "Rejected": ("rejected", "Rejected"),
    "No action required": ("no-action", "No action required"),
    "No action taken": ("no-action", "No action taken"),
    "Informational": ("informational", "Informational"),
    "Informatonal": ("informational", "Informational"),        # sic, 1 row
    "No decision made": ("no-decision", "No decision made"),
    "No decision made; recommend against": ("no-decision", "No decision made; recommend against"),
}
RE_VERDICT = re.compile(r"^<em>(" + "|".join(sorted(map(re.escape, VERDICTS), key=len, reverse=True))
                        + r")(:*)\s*([^<]*)</em>\s*")
RE_THEN = re.compile(r"^<em>1955 text:\s*([^<]*)</em>\s*")
RE_REVIEW = re.compile(r"^<em>Review:</em>;?\s*")


@dataclasses.dataclass(slots=True)
class Span:
    start: int
    end: int
    kind: str
    attr: dict | None = None


@dataclasses.dataclass(slots=True)
class Item:
    name: str               # the row's anchor on the page: the link to it
    n: int                  # this change's place under its anchor, from 1
    label: str              # the row's place as the page names it: "41:4.4", "Contents xiii"
    page: str | None        # its 1955 page and paragraph, "460.1"
    then: str               # the cell's HTML, one part of it
    review: str
    verdict: str | None     # as VERDICTS has it; None for a bare "See SRT note …"
    why: str                # the reasons' HTML
    see: tuple[str, str] | None   # the row it refers the reader to: its anchor, and its
                                  # reference as the link's words give it


class _Text(html.parser.HTMLParser):
    """A cell's HTML -> (text, spans), in the closed vocabulary the page uses."""

    def __init__(self, link):
        super().__init__(convert_charrefs=True)
        self.link, self.out, self.spans, self.open = link, [], [], []

    def _len(self):
        return sum(map(len, self.out))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "br":
            self.handle_data(" ")
            return
        if tag == "em":
            kind, attr = "em", None
        elif tag == "sup":
            kind, attr = "sup", None
        elif tag == "span" and a.get("style") == "text-decoration: underline;":
            kind, attr = "chg", None
        elif tag == "a" and "href" in a:
            kind, attr = "link", a["href"]           # resolved at </a>, with its words
        elif tag == "a" and "name" in a:
            kind, attr = None, None
        else:
            raise ValueError(f"<{tag} {a}> in a cell")
        self.open.append((tag, kind, attr, self._len()))

    def handle_endtag(self, tag):
        if tag == "br":
            return
        if not self.open or self.open[-1][0] != tag:
            raise ValueError(f"</{tag}> closes nothing open")
        _, kind, attr, start = self.open.pop()
        if kind == "link":
            href = self.link(attr, "".join(self.out)[start:].strip())
            kind, attr = ("link", {"href": href}) if href else (None, None)
        if kind and self._len() > start:
            self.spans.append(Span(start, self._len(), kind, attr))

    def handle_data(self, data):
        data = re.sub(r"\s+", " ", data)
        if data.startswith(" ") and (not self.out or "".join(self.out).endswith(" ")):
            data = data[1:]
        self.out.append(data)

    def result(self):
        if self.open:
            raise ValueError(f"<{self.open[-1][0]}> never closed")
        text = "".join(self.out)
        lead = len(text) - len(text.lstrip(" "))
        text = text.strip(" ")
        spans = []
        for s in self.spans:
            a, b = max(s.start - lead, 0), min(s.end - lead, len(text))
            if b > a:
                spans.append(Span(a, b, s.kind, s.attr))
        return text, spans


def to_text(fragment: str, link) -> tuple[str, list[Span]]:
    p = _Text(link)
    p.feed(fragment)
    p.close()
    return p.result()


def _then_review(part: str, where: str) -> tuple[str, str]:
    """One change's half of the middle cell: its 1955 text and the proposal."""
    then, review, field = [], [], None
    for line in BR.split(part.strip()):
        if not line.strip():
            continue
        m = RE_THEN.match(line)
        if m:
            if then:
                raise ValueError(f"{where}: two 1955 texts in one change")
            field = then
            line = html.escape(m.group(1), quote=False) + " " + line[m.end():] if m.group(1) else line[m.end():]
        elif RE_REVIEW.match(line):
            field = review
            line = line[RE_REVIEW.match(line).end():]
        elif field is None:
            raise ValueError(f"{where}: {line[:60]!r} before any 1955 text")
        field.append(line.strip())
    if not then:
        raise ValueError(f"{where}: no 1955 text")
    return " ".join(then), " ".join(review)


def _verdict(part: str, where: str) -> tuple[str | None, str]:
    """A decision part: its verdict and the reasons after it."""
    part = re.sub(r"^(?:\s*<br>)+", "", part).strip()
    m = RE_VERDICT.match(part)
    if m:
        words = m.group(3).strip()
        rest = part[m.end():]
        # "<em>Adopted: Y rays</em> changed to <em>gamma rays.</em>": the first
        # words of the reasons share the label's italics.
        return m.group(1), (f"<em>{words}</em> {rest}" if words else rest).strip()
    if re.match(r"^See\b", part):
        return None, part
    raise ValueError(f"{where}: a decision that opens {part[:60]!r}")


def parse(snapshot: str) -> list[Item]:
    items: list[Item] = []
    for row in ROW.findall(snapshot):
        cells = [c.strip() for c in CELL.findall(row)]
        if len(cells) != 3:
            raise ValueError(f"a row of {len(cells)} cells: {row[:80]!r}")
        if cells[0] == "<strong>1955 text</strong>":            # a table's head
            continue
        place = cells[0]
        name = RE_NAME.search(place)
        href = re.search(r'href="[^"#]*#([^"]+)"', place)
        name = name.group(1) if name else href.group(1) if href else None
        label = re.sub(r"<[^>]+>", " ", re.sub(r"\(\d+\.\d+\)", "", place))
        label = re.sub(r"\s+", " ", label).strip()
        if not name or not label:
            raise ValueError(f"a row with no anchor or no place: {place!r}")
        page = RE_PAGE.search(place)
        changes = [p for p in RULE.split(ALSO.sub("<p>- - - - - -</p>", cells[1])) if p.strip()]
        decisions = [p for p in RULE.split(BLANKS.sub("<p>- - - - - -</p>", cells[2])) if p.strip()]
        where = f"{label} ({name})"
        if len(decisions) == 1:
            decisions = decisions * len(changes)
        if len(decisions) != len(changes):
            raise ValueError(f"{where}: {len(changes)} changes and {len(decisions)} decisions")
        # 42:6.7 has two rows under one anchor: a change is numbered within its anchor.
        first = sum(1 for x in items if x.name == name)
        for i, (c, d) in enumerate(zip(changes, decisions), first + 1):
            then, review = _then_review(c, where)
            verdict, why = _verdict(d, where)
            see = RE_SEE.search(why)
            if verdict is None and not see:
                raise ValueError(f"{where}: no decision, and no note referred to")
            items.append(Item(name, i, label, page.group(1) if page else None, then, review,
                              verdict, why, see.groups() if see else None))
    return items


def fetched(snapshot: str) -> str:
    m = HEADER.match(snapshot)
    if not m:
        raise ValueError("the snapshot has no header naming when it was fetched")
    return m.group(1)


def load_known(path: pathlib.Path) -> set[tuple[str, str, str]]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            kind, ref, words, *_ = line.split("\t")
            out.add((kind, ref, words))
    return out


def _words(t: str) -> list[str]:
    return re.findall(r"[\w’']+", t.casefold())


def _overlap(w: str, u: str) -> bool:
    if not u:
        return False
    return w in u or u in w or bool({x for x in _words(w) if len(x) > 2}
                                    & {x for x in _words(u) if len(x) > 2})


def _follows(before: list[str], ctx: list[str]) -> bool:
    """Do the words `ctx` stand at the end of `before`, allowing for the change?"""
    if not ctx:
        return False
    n = len(ctx)
    return any(before[i:i + n] == ctx for i in range(max(0, len(before) - n - 4), len(before) - n + 1))


def _norm(t: str) -> str:
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip()


def load(con, src: dict, report, known: pathlib.Path, hyphenator=None) -> dict:
    """Fill srt_item and footnote.srt_item_id.  Returns counts for the build's stats."""
    snapshot = src["path"].read_text(encoding="utf-8")
    try:
        items = parse(snapshot)
    except ValueError as e:
        report.hard("srt-unreadable", src["path"].name, str(e))
        return {}

    # The Foundation's reference -> our paragraph and our section.
    para = {u: (pid, ref) for pid, ref, u in con.execute(
        "SELECT p.id, p.ref, u.ref FROM paragraph p JOIN uf_paragraph u ON u.paragraph_id = p.id"
        " WHERE u.ref IS NOT NULL")}
    sect = {u: f"{p}:{n}" for p, n, u in con.execute(
        "SELECT s.paper_n, s.n, u.ref FROM section s JOIN uf_section u ON u.section_id = s.id"
        " WHERE u.ref IS NOT NULL")}

    # What does not pair one to one, or does not resolve, as (kind, place, what):
    # compared at the end with what tests/known-srt-deltas.tsv declares.
    got: set[tuple[str, str, str]] = set()
    here = [""]

    def place(p: str, s: str, n: str) -> str | None:
        """Our href for the Foundation's p:s.n, a section when n is 0."""
        if n != "0":
            hit = para.get(f"{p}:{s}.{n}")
            return f"/{hit[1]}" if hit else None
        if s == "0":
            return f"/{p}"
        return f"/{sect[f'{p}:{s}']}" if f"{p}:{s}" in sect else None

    def link(href: str, words: str) -> str | None:
        """Our href for one of the page's; None for a link to nowhere, shown as text.

        A link that names a reference goes where its words say.  The page
        slips: 46:5.24 links "73:7.4" to 73:0.4, which there is not, and
        136:3.5's "24:1.11" goes to 24:1.1.  Each such is declared.
        """
        m = RE_BOOK.match(href)
        if m:
            said = re.match(r"^(\d+):(\d+)(?:\.(\d+))?$", words)
            if said and said.groups("0") != m.groups():
                got.add(("link-words-differ", here[0], f"{words} {href}"))
                return place(*said.groups("0"))
            to = place(*m.groups())
            if not to:
                got.add(("bad-link", here[0], f"{words} {href}"))
            return to
        if href.startswith("#"):                    # another entry: on the page itself
            return src["url"] + href
        if href.startswith(("https://", "http://")):
            return href
        raise ValueError(f"a link to {href!r}")

    rows, ids, labels, bad, marked = [], {}, {}, 0, {}
    for i, it in enumerate(items, 1):
        where = f"{it.label} ({it.name})"
        here[0] = it.label
        try:
            then_t, then_s = to_text(it.then, link)
            why_t, why_s = to_text(it.why, link)
            review_t, _ = to_text(it.review, link)
            # The words underlined, which a note is paired with, and the three
            # before them, which tell apart two changes of the same word.
            chg = [s for s in then_s if s.kind == "chg"]
            marked[i] = (" ".join(_norm(then_t[s.start:s.end]) for s in chg),
                         _words(then_t[:chg[0].start])[-3:] if chg else [])
        except ValueError as e:
            report.hard("srt-unreadable", where, str(e))
            bad += 1
            continue
        m = RE_REF.match(it.label)
        pid = None
        if m:
            hit = para.get(it.label)
            if not hit:
                report.hard("srt-no-paragraph", where, "the Foundation has no such paragraph")
                continue
            pid = hit[0]
        code = VERDICTS[it.verdict][0] if it.verdict else None
        shown = VERDICTS[it.verdict][1] if it.verdict else None
        rows.append([i, it.name, it.n, it.label, pid, it.page, code, shown, then_t,
                     render(then_t, then_s), review_t or None, why_t, render(why_t, why_s), it.see,
                     # The reasons as a 1955 card sets them, justified, breaking
                     # where the book would (hyphen.py), as the text does.
                     render(why_t, why_s, shy=hyphenator.points(why_t, why_s) if hyphenator else ())])
        ids.setdefault(it.name, i)
        labels.setdefault(it.label, i)
    if bad:
        return {}

    # "See SRT note for 89:3.1": that row's first change.  A change with no
    # decision of its own takes that one's.
    by_id = {r[0]: r for r in rows}
    for r in rows:
        see = r[13]
        r[13] = (labels.get(see[1]) or ids.get(see[0])) if see else None
        if see and r[13] is None:
            report.hard("srt-see-nowhere", f"{r[3]} ({r[1]})", f"refers to {see}, no row of the page")
            bad += 1
        elif r[6] is None:
            r[6], r[7] = by_id[r[13]][6], by_id[r[13]][7]
            if r[6] is None:
                report.hard("srt-see-undecided", f"{r[3]} ({r[1]})", f"{see} has no decision either")
                bad += 1
    if bad:
        return {}
    # A change whose decision is all it says ("Adopted", 134:3.3's second and
    # third) shares the reasons given for the first under its anchor.
    for r in rows:
        if not r[11] and r[13] is None and r[2] > 1:
            r[13] = ids[r[1]]
    # A row may refer to one further down the page: the references go in after.
    con.executemany("INSERT INTO srt_item VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)",
                    [r[:13] + [r[14]] for r in rows])
    con.executemany("UPDATE srt_item SET see_id=? WHERE id=?",
                    [(r[13], r[0]) for r in rows if r[13] is not None])

    # Each 1955 note, to the change it shows.
    by_para: dict[int, list] = {}
    for r in rows:
        if r[4] is not None:
            by_para.setdefault(r[4], []).append(r)
    claimed: set[int] = set()
    pairs = []
    for fid, pid, ref, words, anchor, ptext in con.execute(
            "SELECT f.id, f.paragraph_id, p.ref, f.text, f.anchor, p.text FROM footnote f"
            " JOIN paragraph p ON p.id = f.paragraph_id"
            " WHERE f.kind = 'variant-1955' ORDER BY p.ord, f.ord"):
        cands = by_para.get(pid, [])
        w = _norm(words)
        # The note's words and the change's underlined ones overlap: one holds
        # the other ("sixty" in "sixty thousand"), or they share a word
        # ("times Bering", "Bering Strait").
        hit = [r for r in cands if _overlap(w, marked[r[0]][0])]
        if len(hit) > 1:
            # Two changes of one word (172:5.2's two "whom"): the words before
            # each, as the committee quotes them, stand just before the note.
            before = _words(ptext[max(0, anchor - len(words) - 80):anchor])
            hit = [r for r in hit if _follows(before, marked[r[0]][1])] or hit
        if len(hit) > 1:
            got.add(("ambiguous", ref, words))         # the first is taken
            hit = hit[:1]
        if not hit:
            # Spelt otherwise by one side: 90:2.9's press note has the 1955
            # "Teuskwatowa", as the printing has, and the committee misquotes
            # it as "Teuskwatawa".
            near = [r for r in cands if marked[r[0]][0] and difflib.SequenceMatcher(
                None, w, marked[r[0]][0]).ratio() >= 0.8]
            if len(near) == 1:
                got.add(("spelt-otherwise", ref, words))
                hit = near
        if not hit and len(cands) == 1:
            # One note, one change: there is nothing to choose, though the page
            # may have underlined nothing (112:1.7 says "[only Vertical in italics]").
            hit = cands
        if not hit:
            got.add(("no-entry", ref, words))
            continue
        r = hit[0]
        pairs.append((r[0], fid))
        claimed.add(r[0])
        if r[6] != "adopted":
            got.add(("not-adopted", ref, words))
    for r in rows:
        if r[6] == "adopted" and r[4] is not None and r[0] not in claimed:
            ref = con.execute("SELECT ref FROM paragraph WHERE id=?", (r[4],)).fetchone()[0]
            got.add(("unclaimed", ref, _norm(r[8])))
    con.executemany("UPDATE footnote SET srt_item_id=? WHERE id=?", pairs)

    want = load_known(known)
    for k in sorted(got - want):
        report.hard("srt-undeclared", k[1], f"{k[0]}: {k[2]!r} -- not in {known.name}")
    for k in sorted(want - got):
        report.hard("srt-declared-gone", k[1], f"{known.name} declares {k[0]}: {k[2]!r}, and it is not")
    return {"srt_items": len(rows), "srt_notes": len(pairs), "srt_fetched": fetched(snapshot)}
