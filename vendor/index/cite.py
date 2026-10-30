"""The citation grammar of the Index -- one parser, used by every other script.

A citation is what stands inside parentheses at the end of an index entry.  The
closed set was measured over the 37 807 citations of the 2019 printing (CLAUDE.md
section 8); the shape counts below are that census, and any string this module
rejects is either a disambiguator (``(Old Testament)``, ``(planet)``,
``(Tuesday)`` -- parentheses do double duty) or a defect worth reporting.

    31 429  (N:N.N)          1 630  (N:Nsec)         172  (Paper N)
     3 461  (N:N.N-N)          137  (N:N-Nsecs)       30  (Papers N-N)   en dash
     1 065  (N:N.N,N)           28  (N:N,Nsecs)        9  (Papers N, N)
        78  (N:N.N,N-N)         75  (N:N.N,N,N)        5  (Papers N, N, N)
        57  (N:N.N-N,N)          8  (N:N.N-N,N-N)      + (Paper N, prematter)
                                                       + (Paper N, title page)

Three conventions the grammar carries deliberately:

* **The Foreword is paper 0.**  The 1999 edition's own notation section defines
  it as ``F:`` plus a Roman-numeral section (``F:XII.8``); Uversa Press had
  already converted the A-Z index to ``0:12.8`` by 2019 and left zero ``F:``
  forms behind.  :func:`parse` accepts the 1999 form and normalises it, which is
  what the appendices need.
* **``?`` marks editorial uncertainty** and is kept, not stripped: ``(45:4.5?)``,
  ``(123:6.1?)``, ``(128:7.8?)``, ``(39:5.8?)``.
* **Dash discipline is not cosmetic.**  A range *inside* a citation takes a
  hyphen (``48:6.2-4``); a range of whole papers takes an en dash
  (``Papers 78-80`` is set with U+2013).  The 2019 print gets this wrong four
  times and the 1999 appendices get it wrong throughout -- their citations use
  en dashes inside, e.g. ``(133:3.1-4)`` on printed page 446.  Both are
  normalised here and reported, never silently corrected in the source.

Malformed strings are *not* repaired by :func:`parse`, which returns ``None``.
:func:`diagnose` classifies them and proposes a repair for a human to rule on.
"""

import re
import sys
from dataclasses import dataclass, field

EN_DASH = "–"

# Foreword sections are given in Roman numerals in the 1999 notation; the
# Foreword has 12 sections plus an unnumbered introduction (section 0).
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
         "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}

# Qualifiers that follow a paper number instead of a section.
PAPER_QUALIFIERS = ("prematter", "title page")

# A span is "N" or "N-N"; a list of them is comma-separated.  Both dashes are
# accepted on input so the 1999 appendices parse; fmt() always emits a hyphen.
_SPAN = r"\d+(?:[-%s]\d+)?" % EN_DASH
_SPANLIST = r"%s(?:,\s*%s)*" % (_SPAN, _SPAN)

RE_PARA = re.compile(r"^(\d+|F):(\d+|[IVX]+)\.(%s)(\?)?$" % _SPANLIST)
RE_SEC = re.compile(r"^(\d+|F):(%s)(secs?)(\?)?$" % _SPANLIST)
# A paper reference is a list whose items are single papers or ranges, joined by
# commas or "and", optionally followed by a qualifier: the 2019 index really
# prints "Papers 145, 152-154", "Papers 57-98, 114, 121-195" and
# "Papers 32 and 57, prematter".
_PITEM = r"\d+(?:\s*[-%s]\s*\d+)?" % EN_DASH
RE_PAPER = re.compile(r"^Papers?\s+(%s(?:\s*(?:,|and)\s*%s)*)"
                      r"(?:\s*,\s*(%s))?(\?)?$"
                      % (_PITEM, _PITEM, "|".join(PAPER_QUALIFIERS)))

# Loose test for "this paren group was *meant* to be a citation".  Used to tell
# a defect apart from a legitimate disambiguator, so that (62.5sec) is reported
# while (brother of Jesus) is passed over in silence.
RE_LOOKS_LIKE = re.compile(r"^(?:Papers?\s+\d|F[:.]|\d+\s*[:.]\s*\d)")


@dataclass(frozen=True)
class Cite:
    """One parsed citation.

    ``kind`` is ``'para'`` (paper:section.paragraphs), ``'sec'`` (whole
    sections) or ``'paper'`` (whole papers).  ``spans`` keeps the *printed*
    grouping -- a list of ``(lo, hi)`` pairs, ``hi == lo`` for a single number --
    so that fmt() round-trips the original rather than exploding ``2,5-6`` into
    ``2,5,6``.  :meth:`expand` is the flattened form the oracle wants.
    """

    kind: str
    paper: int = 0
    sec: int = 0
    spans: tuple = ()
    papers: tuple = ()
    body: str = ""
    qual: str = ""
    uncertain: bool = False
    raw: str = ""
    flags: tuple = field(default=(), compare=False)

    def expand(self):
        """Every (paper, section, paragraph) this citation points at.

        Section is ``None`` for a whole-paper reference, paragraph is ``None``
        for a whole-section reference -- the two cases the range check in
        srt.py treats as "section must exist" and "paper must exist".
        """
        if self.kind == "paper":
            return [(p, None, None) for p in self.papers]
        if self.kind == "sec":
            return [(self.paper, s, None) for s in _flatten(self.spans)]
        return [(self.paper, self.sec, n) for n in _flatten(self.spans)]

    def __str__(self):
        return fmt(self)


def _flatten(spans):
    out = []
    for lo, hi in spans:
        # An inverted span is a defect, not an empty set: (81:4.813-14) is the
        # printed form of a lost comma in 81:4.13-14.  Yielding both endpoints
        # rather than range(813, 15) == [] keeps it visible to the oracle's
        # range check instead of letting it pass as citing nothing.
        out.extend(range(lo, hi + 1) if hi >= lo else (lo, hi))
    return out


def _spans(text):
    """Parse a comma-separated span list into ((lo, hi), ...).

    Returns the spans and whether any range used an en dash, which is a defect
    inside a citation and the thing that has to be normalised out of the 1999
    appendices.
    """
    out, en = [], False
    for part in text.split(","):
        part = part.strip()
        if EN_DASH in part:
            en = True
        m = re.match(r"^(\d+)(?:[-%s](\d+))?$" % EN_DASH, part)
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        out.append((lo, hi))
    return tuple(out), en


def _inverted(spans):
    return any(hi < lo for lo, hi in spans)


def parse(s):
    """Parse one citation string, without its parentheses.  None if malformed.

    Accepts the 1999 Foreword form (``F:XII.8``) and normalises it to paper 0,
    and accepts en dashes inside ranges, flagging them.  Everything else must
    conform exactly: this function is the definition of "well-formed", so it has
    to stay strict or the diagnostics downstream mean nothing.
    """
    s = s.strip()
    if not s:
        return None

    m = RE_PARA.match(s)
    if m:
        paper, sec, spans, q = m.groups()
        flags = []
        if paper == "F":
            paper, flags = 0, flags + ["foreword-1999-form"]
        if sec in ROMAN:
            sec, flags = ROMAN[sec], flags + ["roman-section"]
        spans, en = _spans(spans)
        if en:
            flags.append("en-dash-in-range")
        if _inverted(spans):
            flags.append("inverted-range")
        if ", " in s:
            flags.append("space-after-comma")
        return Cite(kind="para", paper=int(paper), sec=int(sec), spans=spans,
                    uncertain=bool(q), raw=s, flags=tuple(flags))

    m = RE_SEC.match(s)
    if m:
        paper, spans, plural, q = m.groups()
        flags = []
        if paper == "F":
            paper, flags = 0, flags + ["foreword-1999-form"]
        spans, en = _spans(spans)
        if en:
            flags.append("en-dash-in-range")
        if _inverted(spans):
            flags.append("inverted-range")
        # "sec" for one section, "secs" for more than one.  The 2009 HTML has a
        # single "N:N-Nsec" that breaks this; it is a defect, not a variant.
        if (len(_flatten(spans)) > 1) != (plural == "secs"):
            flags.append("sec-plural-mismatch")
        return Cite(kind="sec", paper=int(paper), spans=spans,
                    uncertain=bool(q), raw=s, flags=tuple(flags))

    m = RE_PAPER.match(s)
    if m:
        body, qual, q = m.groups()
        flags = []
        papers = []
        for item in re.split(r"\s*(?:,|and)\s*", body):
            item = item.strip()
            if not item:
                continue
            if "-" in item:
                flags.append("hyphen-in-paper-range")
            parts = re.split(r"\s*[-%s]\s*" % EN_DASH, item)
            if len(parts) == 2:
                papers.extend(range(int(parts[0]), int(parts[1]) + 1))
            else:
                papers.append(int(item))
        papers = tuple(papers)
        # "Paper" is singular, "Papers" plural; a qualifier is always singular.
        if (len(papers) > 1) != s.startswith("Papers"):
            flags.append("paper-plural-mismatch")
        # The printed body is kept verbatim so that fmt() round-trips forms like
        # "Papers 32 and 57" and "Papers 57-98, 114, 121-195" exactly, rather
        # than flattening them into one canonical shape.
        return Cite(kind="paper", papers=papers, qual=qual or "", body=body.strip(),
                    uncertain=bool(q), raw=s, flags=tuple(flags))

    return None


def fmt(c):
    """Render a Cite back to house form, without parentheses."""
    tail = "?" if c.uncertain else ""
    if c.kind == "paper":
        word = "Papers" if len(c.papers) > 1 else "Paper"
        body = c.body.replace("-", EN_DASH) if c.body else \
            ", ".join(str(p) for p in c.papers)
        return "%s %s%s%s" % (word, body, ", " + c.qual if c.qual else "", tail)
    body = ",".join("%d-%d" % (lo, hi) if hi != lo else str(lo) for lo, hi in c.spans)
    if c.kind == "sec":
        return "%d:%s%s%s" % (c.paper, body, "secs" if len(_flatten(c.spans)) > 1 else "sec", tail)
    return "%d:%d.%s%s" % (c.paper, c.sec, body, tail)


# --- Defect classification ------------------------------------------------
#
# Each rule is (name, pattern, repair), where repair is a re.sub replacement
# applied to the whole string.  These are the malformed forms actually observed
# in the 2019 printing (CLAUDE.md section 9) and in Geoff's appendix draft
# (section 5.2); the repair is a *suggestion* for the review report.

DEFECTS = [
    ("colon-typed-as-dot",   r"^(\d+)\.(\d+)(sec|secs)$",      r"\1:\2\3"),
    ("colon-typed-as-dot",   r"^(\d+)\.(\d+)\.(\d+)$",         r"\1:\2.\3"),
    ("dot-typed-as-colon",   r"^(\d+):(\d+):(\d+.*)$",         r"\1:\2.\3"),
    ("stray-dot-before-sec", r"^(\d+):(\d+)\.(secs?)$",        r"\1:\2\3"),
    ("trailing-dot",         r"^(\d+:\d+secs?)\.$",            r"\1"),
    # "secs" is plural, so the dot in (191:2.5secs) stands where a section range
    # belongs -- CLAUDE.md section 9 rules it (191:2-5secs).  The singular
    # (126:5.7sec) is the opposite defect and genuinely ambiguous: either the
    # "sec" is spurious or the ".7" is, so it goes to candidates() below.
    ("dot-in-section-range", r"^(\d+):(\d+)\.(\d+)secs$",      r"\1:\2-\3secs"),
    ("extra-dot",            r"^(\d+):(\d+)\.(\d+)\.(\d+)$",   r"\1:\2.\3-\4"),
    ("space-after-comma",    r"^(\d+:\d+\.[\d,\s-]*\d)$",      None),
]


def candidates(s):
    """Every well-formed citation a malformed string might have been.

    For the missing-separator class -- ``(106:812)``, ``(30:17-19)``,
    ``(126:5.7sec)`` -- the repair cannot be deduced from the string alone, only
    narrowed.  This enumerates the possibilities so check_citations.py can put
    each past the SRT oracle and keep the ones that can exist; a single survivor
    is a repair, several survivors or none is a question for a human.
    """
    out = []
    # A run of digits after the colon that should carry a dot somewhere:
    # 106:812 -> 106:8.12, 106:81.2.
    m = re.match(r"^(\d+):(\d{2,})((?:[-,%s]\d+)*)(\?)?$" % EN_DASH, s)
    if m:
        paper, run, tail, q = m.groups()
        for i in range(1, len(run)):
            out.append("%s:%s.%s%s%s" % (paper, run[:i], run[i:], tail or "", q or ""))
    # A section list that lost its "secs": (134:2,5) should be (134:2,5secs).
    m = re.match(r"^(\d+):(\d+(?:[-,%s]\d+)+)(\?)?$" % EN_DASH, s)
    if m:
        out.append("%s:%ssecs%s" % (m.group(1), m.group(2), m.group(3) or ""))

    # "sec" hung on a paragraph number: either the sec is spurious or the
    # paragraph is.
    m = re.match(r"^(\d+):(\d+)\.(\d+)sec(\?)?$", s)
    if m:
        paper, sec, para, q = m.groups()
        out.append("%s:%s.%s%s" % (paper, sec, para, q or ""))
        out.append("%s:%ssec%s" % (paper, sec, q or ""))
    return [c for c in out if parse(c) is not None]


def diagnose(s):
    """Classify a malformed citation and propose repairs.

    Returns ``(name, suggestions)`` where *suggestions* is a possibly-empty list
    of well-formed strings, or ``None`` if the string was never meant to be a
    citation at all -- ``(Old Testament)``, ``(brother of Jesus)`` and the other
    parenthetical disambiguators must pass through untouched.

    More than one suggestion means the string alone does not determine the
    repair; the oracle and then a human narrow it.
    """
    s = s.strip()
    if parse(s) is not None:
        return None
    if not RE_LOOKS_LIKE.match(s):
        return None
    for name, pat, repair in DEFECTS:
        if re.match(pat, s):
            fixed = re.sub(r",\s+", ",", s) if repair is None else re.sub(pat, repair, s)
            if parse(fixed) is not None:
                return name, [fixed]
            break
    cands = candidates(s)
    return ("missing-separator" if cands else "unrecognised"), cands


# --- Scanning entry text --------------------------------------------------

RE_PAREN = re.compile(r"\(([^()]*)\)")


def find_all(text):
    """Every parenthesised group in *text* that is or was meant to be a citation.

    Yields ``(start, end, raw, cite)`` in source order, where ``cite`` is None
    for a malformed one.  Groups that are plainly disambiguators are skipped, so
    a caller can strip citations from an entry without losing ``(planet)``.
    """
    for m in RE_PAREN.finditer(text):
        raw = m.group(1)
        c = parse(raw)
        if c is None and not RE_LOOKS_LIKE.match(raw.strip()):
            continue
        yield m.start(), m.end(), raw, c


def key(c):
    """A comparison key ignoring uncertainty and printed grouping.

    Two citations compare equal when they point at the same paragraphs, which is
    what the Horn-Dreier drift analysis and the PDF/HTML alignment need.
    """
    return (c.kind, tuple(c.expand()))


def _runs(numbers):
    """Sorted, distinct paragraph numbers as maximal runs: 2,15,16 -> (2,2),(15,16)."""
    out = []
    for n in sorted(set(numbers)):
        if out and out[-1][1] + 1 == n:
            out[-1][1] = n
        else:
            out.append([n, n])
    return tuple((lo, hi) for lo, hi in out)


def normal_run(cites):
    """An entry's citations in house form: one citation per paper:section.

    The house form is the 2019's own majority, measured there: it gathers one
    section's paragraphs into one citation 1 292 times and splits them over
    several 25 times -- ``(0:1.2,16) (0:1.15)`` on printed page 55 -- and it
    writes two consecutive paragraphs as a range 1 973 times and with a comma
    81.  So a section's paragraphs go into the first of its citations, sorted,
    each paragraph once, and consecutive ones as a range: ``0:1.2,15-16``
    (Tigran, 2026-10-21).

    Paragraph citations only, by that ruling.  A section list (``54:4,5secs``)
    and a section cited beside a paragraph inside it (``(84:2sec) (84:2.3)``)
    pass through as printed, and so do an uncertain citation and an inverted
    range, whose paragraph set is not what it says.  *cites* is parsed
    citations in printed order; ``None`` (a malformed one) passes through too.
    """
    out, members = [], {}
    for c in cites:
        if (c is None or c.kind != "para" or c.uncertain
                or "inverted-range" in c.flags):
            out.append(c)
            continue
        k = (c.paper, c.sec)
        if k not in members:
            members[k] = []
            out.append(k)
        members[k].append(c)
    for i, k in enumerate(out):
        if not isinstance(k, tuple):
            continue
        group = members[k]
        spans = _runs(n for c in group for _p, _s, n in c.expand())
        if len(group) == 1 and group[0].spans == spans:
            out[i] = group[0]
        else:
            body = Cite(kind="para", paper=k[0], sec=k[1], spans=spans)
            out[i] = Cite(kind="para", paper=k[0], sec=k[1], spans=spans,
                          raw=fmt(body))
    return out


def book_order(cites):
    """An entry's citations in book order: by paper, then section.

    Of the A-Z's 5 880 lines whose citations name more than one paper or
    section, seven did not run so -- `ascension plan > described as > helping
    those just behind (35:4.1) (37:10.5) (55:2.11) (30:3.9)' -- and the 2010
    EPUB prints all seven the same, so they are the 1999's slips and not a
    convention (Tigran, 2026-10-28, from Paper 37's reading).

    A whole-paper citation is not reordered: it leads its run, `(Paper 77)
    (37:9.11) (38:9.1)', on 73 lines of the A-Z and trails it on two, so the
    order asked about is the rest's.  Within one section the printed order stands, `(84:2sec)
    (84:2.3)' among them: that is normal_run's business.  *cites* is parsed
    citations in printed order; ``None`` (a malformed one) stays where it is.
    """
    def where(c):
        return (c.paper, c.spans[0][0] if c.kind == "sec" else c.sec)
    slots = [i for i, c in enumerate(cites) if c is not None and c.kind != "paper"]
    out = list(cites)
    for i, c in zip(slots, sorted((cites[i] for i in slots), key=where)):
        out[i] = c
    return out


def main(argv):
    """Parse each argument (or line of stdin) and print what it is."""
    items = argv[1:] or [ln.strip() for ln in sys.stdin if ln.strip()]
    for s in items:
        s = s.strip("()")
        c = parse(s)
        if c:
            note = " flags=%s" % ",".join(c.flags) if c.flags else ""
            print("OK    %-22s -> %-22s %s%s" % (s, fmt(c), c.expand()[:4], note))
        else:
            d = diagnose(s)
            if d is None:
                print("SKIP  %-22s    (not a citation)" % s)
            else:
                print("BAD   %-22s -> %-22s %s" % (s, " | ".join(d[1]) or "?", d[0]))


if __name__ == "__main__":
    main(sys.argv)
