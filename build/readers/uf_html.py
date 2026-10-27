"""Read the Urantia Foundation's HTML edition of the book, in any language.

Pure: the zip's bytes -> dataclasses.  The Foundation publishes the book, and
each of its translations, as a zip of HTML from one generator: the English SRT
(build/foundation.py, from the press repo) and the Russian translation's 2024
release (build/translation.py) have the same 16,222 ids, the same blocks and
the same fourteen paragraph classes.  So one reader serves every language, and
nothing here is English or Russian.

A paper's file is the one whose <h1> has the id U{n}_0_0; the file names are
in the edition's language ("06-Paper001.html", "06-Документ001.html") and are
never read.  Its body is a closed set of blocks, and anything else in it fails:

  <div class="container">, </div>, <hr />     the page's frame
  <p class="title">, <p class="ctr">         the book's name, the links to turn the page
  <p class="paper">Документ 1</p>            its word for a Paper, and the number
  <h1 id="U1_0_0">, <h2 id="U1_1_0">         the paper's title, a section's
  <p id="U1_0_1" class="btn">                a paragraph

A paragraph begins with its reference and its 1955 page, <small>1:0.1
(21.1)</small>, which must be its id's.  Eleven entries are printed without a
reference, each marked by an F after its id (U0_12_10F): ten separators, which
are stars alone and stand before the paragraph after them, and 0:12.10, the
Acknowledgment's heading, which is a paragraph (build/foundation.py says why).
The body after the reference is kept as written, HTML: its inline markup is the
caller's to read.
"""

from __future__ import annotations

import bisect
import dataclasses
import html
import io
import re
import zipfile

RE_TITLE = re.compile(r'<h1 id="U(\d+)_0_0">(.*?)</h1>', re.S)
RE_BODY = re.compile(r"<body>(.*)</body>", re.S)
# The blocks a paper's body is made of, in the order they come; group 1 names
# the kind, and what is not one of them is caught by the last alternative.
RE_BLOCK = re.compile(
    r'(?P<frame><div class="container">|</div>|<hr />)'
    r'|<p class="(?P<pcls>title|ctr|paper)">(?P<pbody>.*?)</p>'
    r'|<h(?P<h>[12]) id="U(?P<hp>\d+)_(?P<hs>\d+)_0">(?P<hbody>.*?)</h[12]>'
    r'|<p id="U(?P<p>\d+)_(?P<s>\d+)_(?P<n>\d+)(?P<bare>F?)" class="(?P<cls>[a-z0-9]+)">(?P<body>.*?)</p>'
    r'|(?P<stray>\S[^<]*|<[^>]*>)', re.S)
CLASSES = frozenset({"btn", "bts", "btl", "bte",       # prose: none, small, large, extra space after
                     "l2n", "l2s", "l3n", "l3s",       # a list's item, at two depths
                     "p1n", "p2n", "p1l", "p2l",       # verse, set in once or twice
                     "fln", "fll"})                    # an entry printed without a reference
RE_SMALL = re.compile(r"\s*<small>([^<]*)</small>\s*")
RE_PAGE = re.compile(r" \((\d+\.\d+)\)$")
RE_STARS = re.compile(r"\*(?: \*)+")
RE_TAG = re.compile(r"<[^>]+>")
RE_PAPERWORD = re.compile(r"(\S+) (\d+)")

Key = tuple[int, int, int]


def fmt(k: Key | None) -> str:
    return "-" if k is None else f"{k[0]}:{k[1]}.{k[2]}"


@dataclasses.dataclass(slots=True)
class Para:
    key: Key                 # as the Foundation numbers it
    bare: bool               # printed without a reference: an F id
    cls: str                 # its class, one of CLASSES
    page: str | None         # its 1955 page, "21.1", as printed; None where it is not
    body: str                # its HTML after the reference, as written, stripped
    name: str                # the file
    line: int

    @property
    def text(self) -> str:
        """Its words, the tags taken out: what build/foundation.py compares."""
        return html.unescape(RE_TAG.sub("", self.body)).strip()


@dataclasses.dataclass(slots=True)
class Heading:
    section: int             # by its id: 0 for the paper's title
    body: str                # its HTML, as written
    line: int
    before: Key | None = None  # the paragraph it stands before; None for the title


@dataclasses.dataclass(slots=True)
class Paper:
    n: int
    name: str
    title: Heading
    word: str | None         # its p.paper's word for a Paper; None where it has none (the Foreword)
    sections: list[Heading]
    paras: list[Para]        # in the order printed, the separators apart
    seps: list[tuple[Key, str, int]]   # (the paragraph after it, its stars, line)


# What the edition says of itself, on its cover page: its text's id, which
# names the language and the release, UF-RUS-001-1997-1.5, and the stamp of
# the version, UF-202412132348, its date and time.
RE_TEXT_ID = re.compile(r"\bUF-[A-Z]{3}-\d{3}-\d{4}-\d+(?:\.\d+)*")
RE_STAMP = re.compile(r"\bUF-\d{12}\b")


def release(data: bytes) -> tuple[set[str], set[str]]:
    """The text ids and the version stamps its pages give."""
    ids, stamps = set(), set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith(".html"):
                src = z.read(name).decode("utf-8")
                ids.update(RE_TEXT_ID.findall(src))
                stamps.update(RE_STAMP.findall(src))
    return ids, stamps


def read(data: bytes, report) -> dict[int, Paper]:
    """{n: Paper} for each paper in the zip, in order."""
    out: dict[int, Paper] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".html"):
                continue
            src = z.read(name).decode("utf-8")
            m = RE_TITLE.search(src)
            if not m:
                continue                         # the front matter, the parts, the contents
            n = int(m.group(1))
            if n in out:
                report.hard("uf-paper-twice", name, f"paper {n} is also {out[n].name}")
                continue
            out[n] = _paper(n, name, src, report)
    return dict(sorted(out.items()))


def _paper(n: int, name: str, src: str, report) -> Paper:
    body = RE_BODY.search(src)
    lines = [m.start() for m in re.finditer("\n", src)]
    at = lambda i: bisect.bisect_left(lines, i) + 1
    title = word = None
    sections: list[Heading] = []
    paras: list[Para] = []
    seps: list[tuple[Key, str, int]] = []
    seen: set[Key] = set()
    waiting: list[Heading] = []                  # section titles awaiting their paragraph
    star = None                                  # a separator awaiting its paragraph
    for m in RE_BLOCK.finditer(src, body.start(1), body.end(1)):
        where = f"{name}:{at(m.start())}"
        if m.group("stray"):
            report.hard("uf-html-unread", where, m.group("stray")[:70])
        elif m.group("pcls") == "paper":
            w = RE_PAPERWORD.fullmatch(m.group("pbody").strip())
            if not w or int(w.group(2)) != n or word is not None:
                report.hard("uf-paper-word", where, f"{m.group('pbody')!r} in paper {n}'s file")
            else:
                word = w.group(1)
        elif m.group("h"):
            p, s = int(m.group("hp")), int(m.group("hs"))
            if p != n or (m.group("h") == "1") != (s == 0):
                report.hard("uf-heading-misplaced", where, f"<h{m.group('h')}> U{p}_{s}_0 in paper {n}'s file")
            elif s == 0:
                title = Heading(0, m.group("hbody").strip(), at(m.start()))
            else:
                sections.append(h := Heading(s, m.group("hbody").strip(), at(m.start())))
                waiting.append(h)
        elif m.group("p"):
            k = (int(m.group("p")), int(m.group("s")), int(m.group("n")))
            cls, raw, bare = m.group("cls"), m.group("body"), bool(m.group("bare"))
            if k[0] != n:
                report.hard("uf-paper-mismatch", where, f"{fmt(k)} in paper {n}'s file")
                continue
            if cls not in CLASSES:
                report.hard("uf-html-unread", where, f"{fmt(k)}: a paragraph of class {cls!r}")
                continue
            page = None
            if bare:
                text = html.unescape(RE_TAG.sub("", raw)).strip()
                if RE_STARS.fullmatch(text):
                    if star:
                        report.hard("uf-separator-twice", fmt(k), f"{name}: two in a row")
                    star = (text, at(m.start()))     # a separator: see above
                    continue
                rest = raw.strip()
            else:
                small = RE_SMALL.match(raw)
                if not small or not small.group(1).startswith(fmt(k) + " "):
                    report.hard("uf-paragraph-unlabelled", fmt(k),
                                f"{name}: no <small>{fmt(k)} …</small> before the text")
                    continue
                pg = RE_PAGE.search(small.group(1))
                if not pg:
                    report.hard("uf-paragraph-no-page", fmt(k),
                                f"{name}: no 1955 page in {small.group(1)!r}")
                else:
                    page = pg.group(1)
                rest = raw[small.end():].strip()
            if k in seen:
                report.hard("uf-paragraph-duplicate", fmt(k), f"{name}: {fmt(k)} twice")
                continue
            seen.add(k)
            paras.append(Para(k, bare, cls, page, rest, name, at(m.start())))
            for h in waiting:
                h.before = k
            waiting = []
            if star:
                seps.append((k, *star))
                star = None
    if star:
        report.hard("uf-separator-at-end", name, "a separator with no paragraph after it")
    for h in waiting:
        report.hard("uf-heading-at-end", f"{name}:{h.line}", "a section title with no paragraph after it")
    if title is None:
        report.hard("uf-paper-untitled", name, f"no <h1> for paper {n}")
        title = Heading(0, "", 0)
    return Paper(n, name, title, word, sections, paras, seps)
