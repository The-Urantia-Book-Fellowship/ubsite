"""The British Study Edition's quiz, its 819 questions, in the database.

`tex/quiz.tex` is the Cosmic Citizenship Quiz the edition's PDF sets at its end
(build/readers/quiz.py reads it).  The site asks it one question at a time, at
the end of each paper that has questions and at /quiz (Tigran, 2026-10-28).
This module makes the rows those pages read, and holds them to the edition and
to the reviews:

  * Each question has an id for ever, its line in data/quiz/questions.tsv,
    given once and never reused, as a headword keeps its slug: the browser
    and the board remember answers by it.  A line names its question by
    `origin`, 16 hex digits of the SHA-256 of the question as written, so a
    question edited upstream fails the build until the ledger says what it is
    now (data/quiz/README.md).  Questions with the same origin are paired with
    lines in order: quiz.tex asks one question twice (137, its lines 5932 and
    5942), and that is two questions.
  * `v` is the layout of a question's answers, which the browser and the board
    store by position: a ruling that the answers changed moves it, and an
    answer given under the old one is never marked against the new.
  * The text is the edition's, British, set beside the press's American:
    data/quiz/american.tsv rewrites its spelling, word for word and closed,
    and a date is put in the book's order ("25 March 7 B.C." is "March 25,
    7 B.C.", "4 April 30 A.D." is "April 4, A.D. 30"), with the no-break space
    the book sets beside the era.  Both act on the TeX, before it is expanded.
  * The word gate: every word the site shows, after both, is a word of the
    book (its search index), or a word data/quiz/words.tsv allows and says
    why.  What is neither is a slip of the edition's, and so is a metric unit
    where the press gives miles (trap 31), a date left British, a time on the
    24-hour clock, the duplicate: tests/known-quiz-slips.tsv lists those not
    yet mended upstream, and must list exactly those.  A table entry nothing
    uses fails, and so does an allowed word the book has after all.
  * A reviewed question names what answers it: one or more passages of the
    text (`text`), in the order ruled, each a paragraph and the words quoted
    from it, which occur there once and are whole words, or a paragraph or a
    run of one section's paragraphs shown whole (data/quiz/references.tsv;
    Tigran, 2026-10-29, ruling 13:1.1 and 13:2.7-8 for the forbidden spheres);
    or a study note (`note`), by the origin build/study.py keys notes by,
    which the quiz shows once its paper's notes are reviewed and the
    paragraph until then, never an unreviewed note; or nothing (`none`).
    `drop` keeps a question out; `gone` keeps the id of one deleted upstream.
    No length is refused: over SHOWN_WARN characters shown under one question
    the build warns, so that a section ruled by a slip is noticed.

Nothing here is the press's: the quiz is the study edition's lineage, set with
its macros (build/quiz_macros.py, trap 1) and its expander (build/study.py).
"""

from __future__ import annotations

import collections
import dataclasses
import pathlib
import re
import sqlite3

from . import quiz_macros, study
from .readers import quiz as reader
from .readers import study as study_reader
from .render import render, strip_tags

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "quiz"
LEDGER = DATA / "questions.tsv"
REFERENCES = DATA / "references.tsv"
AMERICAN = DATA / "american.tsv"
WORDS = DATA / "words.tsv"
SLIPS = ROOT / "tests" / "known-quiz-slips.tsv"

COLUMNS = ("id", "paper", "origin", "v", "state")
REF_COLUMNS = ("id", "n", "ref", "quote")
STATES = ("-", "text", "note", "none", "drop", "gone")
WHY = ("name", "english", "distractor", "abbreviation")
SLIP_KINDS = ("word", "unit", "date", "time", "tilde", "duplicate")
RE_REF = re.compile(r"(\d+):(\d+)\.(\d+)")
# A paragraph, or a run of one section's paragraphs, "0:3.2-8", as the site's
# addresses write it: a list given an item to a paragraph answers as a whole.
RE_PARAS = re.compile(r"(\d+):(\d+)\.(\d+)(?:-(\d+))?")
RE_HEX = re.compile(r"[0-9a-f]{16}")
# A `quote` that shows the paragraph, or the run of them, whole (Tigran,
# 2026-10-29, of 0:3.2-8's seven Absolutes).  No length is refused since his
# ruling of 13:1.5-6, about 850 characters, the same day: over SHOWN_WARN
# characters shown under one question, the build warns.
WHOLE = "¶"
SHOWN_WARN = 1000
# The style a quoted passage keeps from its paragraph: the red letter, italics,
# and what goes with the words; never a marker, a link or a list's label.
QUOTE_KINDS = frozenset({"em", "redletter", "supplied", "sup", "sc", "ul", "nobreak"})

MONTHS = ("January|February|March|April|May|June|July|August|September|October"
          "|November|December")
WEEKDAY = r"(?:Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)day"
_SEP = r"(?:\\,|~| )"
_ORD = r"(\d{1,2})(?:\\ts\{(?:st|nd|rd|th)\})?"
# A day, its month and a year, with the era: "25 March 7 B.C.", "Tuesday 4
# April 30 A.D.", "11\ts{th} February, 2\,B.C.".
# A year, its thousands set off by commas: "37,000".
_YEAR = r"(\d{1,3}(?:,\d{3})+|\d+)"
RE_DAY_DATE = re.compile(rf"(?:({WEEKDAY}),? )?{_ORD} ({MONTHS}),? {_YEAR}{_SEP}(B\.C\.|A\.D\.)")
# A year alone: "300 A.D.", "76\,A.D.", "37,000 B.C.".
RE_YEAR = re.compile(rf"(?<![\d,]){_YEAR}{_SEP}(B\.C\.|A\.D\.)")
# What the site may not show once the rewrites are done.
RE_BRITISH_DATE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)? (?:{MONTHS})\b|\d[ \u00a0\u202f]?A\.D\.")
RE_TIME = re.compile(r"(?<![\d:])(?:[01]\d|2[0-3]):(?:00|15|30|45)(?![\d:])")
RE_UNIT = re.compile(r"\d[\d,.]*[\s\u00a0\u202f]?(km/s|km|cm|mm|m|ly|kg|kilometres?|metres?|centimetres?)"
                     r"(?![A-Za-z])")
UNIT_WORDS = frozenset({"km", "cm", "mm", "m", "ly", "kg", "kilometre", "kilometres",
                        "metre", "metres", "centimetre", "centimetres", "s"})


@dataclasses.dataclass(slots=True)
class Line:
    """A line of data/quiz/questions.tsv."""
    id: int
    paper: int
    origin: str
    v: int
    state: str
    refs: list                   # [(ref, quote)]: each passage, its words or WHOLE; a note's paragraph and origin
    lineno: int


@dataclasses.dataclass(slots=True)
class Built:
    """What build() made from the edition: the rows store() writes, once the
    text and its search index are loaded."""
    repo: dict
    questions: list[dict]
    answers: list[dict]
    slips: list[tuple[str, int, str]]          # (kind, id, what), as found
    american: dict[str, str]                   # data/quiz/american.tsv: british -> american
    american_used: set[str]
    words: dict[str, str]                      # data/quiz/words.tsv: word -> why


# -- the data files ------------------------------------------------------------

def _rows(path: pathlib.Path):
    """(line number, fields) of a TSV, past its comments and its header."""
    if not path.exists():
        return
    header = True
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.startswith("#"):
            continue
        if header:
            header = False
            continue
        yield n, raw.split("\t")


def load_ledger(report, path: pathlib.Path = LEDGER, refs_path: pathlib.Path | None = None) -> list[Line]:
    """The lines of data/quiz/questions.tsv, each with its references from
    data/quiz/references.tsv (beside it, unless `refs_path` says where)."""
    out: list[Line] = []
    where = f"data/quiz/{path.name}"
    if not path.exists():
        report.hard("quiz-ledger", where, "absent: tools/quiz/apply.py new makes it")
        return out
    refs_path = refs_path or path.with_name("references.tsv")
    refs: dict[int, list[tuple[int, str, str, int]]] = collections.defaultdict(list)
    rwhere = f"data/quiz/{refs_path.name}"
    for n, f in _rows(refs_path):
        at = f"{rwhere}:{n}"
        if len(f) != len(REF_COLUMNS) or not f[0].isdigit() or not f[1].isdigit():
            report.hard("quiz-ledger", at, f"{'/'.join(REF_COLUMNS)}, id and n numbers")
            continue
        refs[int(f[0])].append((int(f[1]), f[2], f[3], n))
    for n, f in _rows(path):
        at = f"{where}:{n}"
        if len(f) != len(COLUMNS):
            report.hard("quiz-ledger", at, f"{len(f)} fields, not {len(COLUMNS)}: {'/'.join(COLUMNS)}")
            continue
        try:
            line = Line(int(f[0]), int(f[1]), f[2], int(f[3]), f[4], [], n)
        except ValueError:
            report.hard("quiz-ledger", at, "id, paper and v are numbers")
            continue
        if line.state not in STATES:
            report.hard("quiz-ledger", at, f"state {line.state!r}: one of {', '.join(STATES)}")
        if not RE_HEX.fullmatch(line.origin):
            report.hard("quiz-ledger", at, f"origin {line.origin!r}: 16 hex digits")
        if line.v < 1:
            report.hard("quiz-ledger", at, "v counts from 1")
        rows = sorted(refs.pop(line.id, []))
        if [k for k, *_ in rows] != list(range(1, len(rows) + 1)):
            report.hard("quiz-ledger", f"{rwhere}", f"id {line.id}: its references are numbered 1, 2, 3 ... in order")
        want = line.state in ("text", "note")
        if want != bool(rows):
            report.hard("quiz-ledger", at, f"state {line.state} {'needs' if want else 'takes no'}"
                                           f" references in {rwhere}")
        if line.state == "note" and len(rows) != 1:
            report.hard("quiz-ledger", at, "a note is one reference: its paragraph, and its origin in `quote`")
        for k, ref, quote, rn in rows:
            rat = f"{rwhere}:{rn}"
            m = RE_PARAS.fullmatch(ref)
            if not m:
                report.hard("quiz-ledger", rat, f"ref {ref!r}: a paragraph, 32:2.11, or a run of them, 0:3.2-8")
            elif line.state == "note" and not RE_HEX.fullmatch(quote):
                report.hard("quiz-ledger", rat, "a note is named by its origin, 16 hex digits, in `quote`")
            elif m[4] and (line.state != "text" or quote != WHOLE or int(m[4]) <= int(m[3])):
                report.hard("quiz-ledger", rat, f"a run of paragraphs, {ref}, is text shown whole ({WHOLE}),"
                                                " its last after its first")
            elif not quote:
                report.hard("quiz-ledger", rat, f"{ref}: the words quoted, or {WHOLE} for the paragraph whole")
            line.refs.append((ref, quote))
        out.append(line)
    for qid, rows in refs.items():
        report.hard("quiz-ledger", f"{rwhere}:{rows[0][3]}", f"id {qid} is no line of {where}")
    ids = [x.id for x in out]
    if ids != list(range(1, len(ids) + 1)):
        report.hard("quiz-ledger-ids", where, "ids run 1, 2, 3 ... in order, none twice, none missing")
    return out


def load_american(report, path: pathlib.Path = AMERICAN) -> dict[str, str]:
    out: dict[str, str] = {}
    for n, f in _rows(path):
        at = f"data/quiz/{path.name}:{n}"
        if len(f) != 2 or not all(f) or f[0] != f[0].lower() or f[0] in out:
            report.hard("quiz-american", at, "british<TAB>american, the British in lower case, once")
            continue
        out[f[0]] = f[1]
    return out


def load_words(report, path: pathlib.Path = WORDS) -> dict[str, str]:
    out: dict[str, str] = {}
    for n, f in _rows(path):
        at = f"data/quiz/{path.name}:{n}"
        if len(f) != 2 or f[1] not in WHY or f[0] != f[0].lower() or f[0] in out:
            report.hard("quiz-words", at, f"word<TAB>why, the word in lower case, once; why one of {', '.join(WHY)}")
            continue
        out[f[0]] = f[1]
    return out


def load_slips(report, path: pathlib.Path = SLIPS) -> set[tuple[str, int, str]]:
    out: set[tuple[str, int, str]] = set()
    for n, f in _rows(path):
        at = f"tests/{path.name}:{n}"
        if len(f) < 3 or f[0] not in SLIP_KINDS or not f[1].isdigit():
            report.hard("quiz-slips", at, f"kind<TAB>id<TAB>what[<TAB>note]; kind one of {', '.join(SLIP_KINDS)}")
            continue
        out.add((f[0], int(f[1]), f[2]))
    return out


# -- the text --------------------------------------------------------------------

def americanize(tex: str, table: dict[str, str], used: set[str]) -> str:
    """Each British word or phrase of the table, whole, in any case, the case
    kept: Centre is Center.  Never a command's name: \\centre is not a word."""
    for brit, am in table.items():
        rx = re.compile(r"(?<![\\A-Za-z])" + re.escape(brit).replace(r"\ ", "[ ~]") + r"(?![A-Za-z])",
                        re.IGNORECASE)

        def sub(m, am=am, brit=brit):
            used.add(brit)
            w = m.group()
            if w.isupper() and len(w) > 1:
                return am.upper()
            if w[0].isupper():
                return am[0].upper() + am[1:]
            return am
        tex = rx.sub(sub, tex)
    return tex


def dates(tex: str) -> str:
    """A date in the book's order, its era beside the year with a tie, as the
    book sets it (122:8.1 "August 21, 7 B.C.", 124:6.1 "April 9, A.D. 7")."""
    def day(m):
        weekday, d, month, year, era = m.groups()
        when = f"{year}~B.C." if era == "B.C." else f"A.D.~{year}"
        return (f"{weekday}, " if weekday else "") + f"{month} {int(d)}, {when}"

    def year(m):
        y, era = m.groups()
        return f"{y}~B.C." if era == "B.C." else f"A.D.~{y}"
    return RE_YEAR.sub(year, RE_DAY_DATE.sub(day, tex))


def expand(tex: str, where: str, report) -> tuple[str, str]:
    text, html, _ = study.expand(tex, {}, {}, where, report, table=quiz_macros.TABLE,
                                 subs=quiz_macros.SUBS, ties=False)
    return text, html


def macros_used(questions) -> set[str]:
    out: set[str] = set()
    for q in questions:
        for tex in (q.tex, *(a for a, _ in q.answers)):
            plain = re.sub(r"\$[^$]*\$", " ", tex)
            out.update(re.findall(r"\\([A-Za-z]+|.)", plain))
    return out


# -- the build -----------------------------------------------------------------------

def reconcile(questions, ledger: list[Line], report) -> list[Line | None]:
    """The ledger's line for each question, by origin, in order of occurrence."""
    live = collections.defaultdict(collections.deque)
    for x in ledger:
        if x.state != "gone":
            live[x.origin].append(x)
    out: list[Line | None] = []
    for q in questions:
        at = f"quiz.tex:{q.line}"
        x = live[q.origin].popleft() if live[q.origin] else None
        if x is None:
            report.hard("quiz-unledgered", at,
                        f"Paper {q.paper}'s question {q.ord} ({q.origin}) is in no line of"
                        " data/quiz/questions.tsv: new, or edited upstream (tools/quiz/apply.py new)")
        elif x.paper != q.paper:
            report.hard("quiz-ledger-paper", at, f"line {x.lineno} (id {x.id}) says Paper {x.paper}")
        out.append(x)
    for xs in live.values():
        for x in xs:
            report.hard("quiz-ledger-gone", f"data/quiz/questions.tsv:{x.lineno}",
                        f"id {x.id} ({x.origin}) is no question of the edition now:"
                        " mark it gone, or give it the origin of its question as edited")
    return out


def build(repo: dict, report) -> Built | None:
    """The quiz as the edition has it at the commit config pins, expanded,
    each question with its ledger line.  None if the edition has no quiz."""
    questions = reader.read(repo["tex"], repo["at"], report)
    if questions is None:
        report.hard("quiz-absent", "quiz.tex", f"the study edition has none at {repo['at'][:7]}")
        return None
    used = macros_used(questions)
    known = set(quiz_macros.TABLE) | quiz_macros.STRUCTURE | quiz_macros.MATH
    for name in sorted(used - known):
        report.hard("quiz-macro-unknown", "quiz.tex", f"\\{name}: not in build/quiz_macros.py")
    for name in sorted(set(quiz_macros.TABLE) - used):
        report.hard("quiz-macro-unused", "build/quiz_macros.py", f"\\{name}: quiz.tex uses it no more")
    ledger = load_ledger(report)
    american = load_american(report)
    words = load_words(report)
    lines = reconcile(questions, ledger, report)
    built = Built(repo, [], [], [], american, set(), words)
    seen: dict[str, int] = {}
    for q, x in zip(questions, lines):
        if x is None:
            continue
        where = f"quiz.tex:{q.line}"

        def setting(tex):
            return expand(dates(americanize(tex, american, built.american_used)), where, report)
        text, html = setting(q.tex)
        mask = q.mask
        built.questions.append({
            "id": x.id, "paper_n": q.paper, "ord": q.ord, "line": q.line, "origin": q.origin,
            "v": x.v, "mask": mask, "multi": int(bin(mask).count("1") > 1),
            "text": text, "html": html, "state": x.state, "refs": x.refs, "lineno": x.lineno})
        for n, (tex, right) in enumerate(q.answers):
            at, ah = setting(tex)
            built.answers.append({"question_id": x.id, "n": n, "text": at, "html": ah,
                                  "right": int(right)})
        if q.origin in seen:
            built.slips.append(("duplicate", x.id, str(seen[q.origin])))
        seen.setdefault(q.origin, x.id)
    for brit in sorted(set(american) - built.american_used):
        report.hard("quiz-american-unused", "data/quiz/american.tsv", f"{brit!r}: no question has it")
    _gates(built)
    return built


def _gates(built: Built) -> None:
    """The slips a reader would see, found in what the site shows; the word
    gate, which needs the book's search index, is store()'s."""
    by_q = collections.defaultdict(list)
    for a in built.answers:
        by_q[a["question_id"]].append(a["text"])
    for q in built.questions:
        for shown in [q["text"], *by_q[q["id"]]]:
            for m in RE_UNIT.finditer(shown):
                built.slips.append(("unit", q["id"], _plain(m.group())))
            for m in RE_BRITISH_DATE.finditer(shown):
                built.slips.append(("date", q["id"], _plain(m.group())))
            for m in RE_TIME.finditer(shown):
                built.slips.append(("time", q["id"], m.group()))
            if "~" in shown:
                built.slips.append(("tilde", q["id"], "~"))


def _plain(s: str) -> str:
    """What a slip's words are written as in tests/known-quiz-slips.tsv: plain spaces."""
    return s.replace("\u00a0", " ").replace("\u202f", " ")


def _tokens(con, texts: dict[int, str]) -> dict[int, list[str]]:
    """Each text's words as the book's search index sees them, its tokenizer's."""
    con.execute("DROP TABLE IF EXISTS temp.quiz_words")
    con.execute("CREATE VIRTUAL TABLE temp.quiz_words USING fts5(t,"
                " tokenize='unicode61 remove_diacritics 2')")
    con.executemany("INSERT INTO temp.quiz_words(rowid, t) VALUES (?,?)", texts.items())
    con.execute("CREATE VIRTUAL TABLE temp.quiz_vocab USING fts5vocab(temp, quiz_words, instance)")
    out: dict[int, list[str]] = collections.defaultdict(list)
    for term, doc in con.execute("SELECT term, doc FROM temp.quiz_vocab ORDER BY doc, offset"):
        out[doc].append(term)
    con.execute("DROP TABLE temp.quiz_vocab")
    con.execute("DROP TABLE temp.quiz_words")
    return out


def book_vocabulary(con) -> set[str]:
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.book_vocab"
                " USING fts5vocab(main, paragraph_fts, row)")
    out = {t for (t,) in con.execute("SELECT term FROM temp.book_vocab")}
    con.execute("DROP TABLE temp.book_vocab")
    return out


def word_gate(con, built: Built, report) -> None:
    vocab = book_vocabulary(con)
    allowed = _tokens(con, dict(enumerate(built.words, 1)))
    for i, w in enumerate(built.words, 1):
        toks = allowed.get(i, [])
        if toks != [w]:
            report.hard("quiz-words", "data/quiz/words.tsv", f"{w!r} is {len(toks)} words to the index: {toks}")
        elif w in vocab:
            report.hard("quiz-words", "data/quiz/words.tsv", f"{w!r} is a word of the book: no need to allow it")
    used_allowed: set[str] = set()
    texts = collections.defaultdict(list)
    for q in built.questions:
        texts[q["id"]].append(q["text"])
    for a in built.answers:
        texts[a["question_id"]].append(a["text"])
    for qid, toks in _tokens(con, {k: "\n".join(v) for k, v in texts.items()}).items():
        for t in dict.fromkeys(toks):
            if any(c.isdigit() for c in t) or t in vocab or t in UNIT_WORDS:
                continue
            if t in built.words:
                used_allowed.add(t)
                continue
            built.slips.append(("word", qid, t))
    for w in sorted(set(built.words) - used_allowed):
        report.hard("quiz-words-unused", "data/quiz/words.tsv", f"{w!r}: no question has it")
    # What the table writes is the book's own spelling, which is its point.
    am = sorted(set(built.american.values()))
    for i, toks in _tokens(con, dict(enumerate(am, 1))).items():
        for t in toks:
            if t not in vocab and not any(c.isdigit() for c in t):
                report.hard("quiz-american", "data/quiz/american.tsv",
                            f"{am[i - 1]!r}: {t!r} is no word of the book")


def check_slips(built: Built, report, path: pathlib.Path = SLIPS) -> None:
    known = load_slips(report, path)
    found = set(built.slips)
    line_of = {q["id"]: q["line"] for q in built.questions}
    for kind, qid, what in sorted(found - known):
        report.hard(f"quiz-slip-{kind}", f"quiz.tex:{line_of.get(qid, '?')}",
                    f"id {qid}: {what!r}, new; mend it upstream, or rule it"
                    f" (data/quiz/README.md), or list it in tests/{path.name}")
    for kind, qid, what in sorted(known - found):
        report.hard("quiz-slip-mended", f"tests/{path.name}",
                    f"{kind} {qid} {what!r} is no longer there: take its line out")


def _anchor(text: str, quote: str, where: str, report) -> int | None:
    """Where `quote` begins in the paragraph: once, and whole words."""
    if not quote or quote != quote.strip():
        report.hard("quiz-quote", where, f"{quote!r}: no leading or trailing space")
        return None
    i = text.find(quote)
    if i < 0:
        report.hard("quiz-quote", where, f"{quote[:50]!r}... is not in the paragraph")
        return None
    if text.find(quote, i + 1) >= 0:
        report.hard("quiz-quote", where, f"{quote[:50]!r}... occurs more than once: say more")
        return None
    e = i + len(quote)
    if (i > 0 and text[i - 1].isalnum() and quote[0].isalnum()) or \
            (e < len(text) and text[e - 1].isalnum() and text[e].isalnum()):
        report.hard("quiz-quote", where, f"{quote[:50]!r}... begins or ends inside a word")
        return None
    return i


def paragraphs(ref: str) -> list[str]:
    """The paragraphs a reference names: "0:3.2-8" -> 0:3.2 ... 0:3.8."""
    m = RE_PARAS.fullmatch(ref)
    if not m or not m[4]:
        return [ref]
    return [f"{m[1]}:{m[2]}.{n}" for n in range(int(m[3]), int(m[4]) + 1)]


def _whole(texts: dict[str, str], ref: str, where: str, report) -> list[str] | None:
    """The paragraphs shown whole for `ref`, each there, together short enough."""
    refs = paragraphs(ref)
    missing = [r for r in refs if r not in texts]
    if missing:
        report.hard("quiz-ref", where, f"{', '.join(missing)}: no such paragraph")
        return None
    return refs


def _quote_html(con, pid: int, text: str, at: int, quote: str) -> str:
    """The quoted words as the paragraph sets them, its red letter and italics."""
    e = at + len(quote)
    spans = []
    for s, t, kind in con.execute('SELECT start, "end", kind FROM span WHERE paragraph_id = ?'
                                  " ORDER BY ord", (pid,)):
        if kind in QUOTE_KINDS and t > at and s < e:
            spans.append(_Span(max(s, at) - at, min(t, e) - at, kind))
    return render(quote, spans)


@dataclasses.dataclass(slots=True)
class _Span:
    start: int
    end: int
    kind: str
    attr: dict | None = None


def store(con: sqlite3.Connection, built: Built, report) -> None:
    """The quiz_* rows: after the text, its spans, the study notes and the
    search index are loaded, which the references and the word gate read."""
    word_gate(con, built, report)
    check_slips(built, report)
    para = {r: (i, t, p) for i, r, t, p in con.execute("SELECT id, ref, text, paper_n FROM paragraph")}
    notes = {o: (fid, ref) for fid, o, ref in con.execute(
        "SELECT n.footnote_id, n.origin, p.ref FROM study_note n JOIN footnote f ON f.id = n.footnote_id"
        " JOIN paragraph p ON p.id = f.paragraph_id WHERE n.origin IS NOT NULL")}
    originals = _note_origins(built, report)
    texts = {r: t for r, (_, t, _) in para.items()}
    for q in built.questions:
        where = f"data/quiz/questions.tsv:{q['lineno']}"
        fid = None
        rows = []                                  # quiz_ref: (n, pid, last, quote, at, qh)
        if q["state"] == "text":
            for n, (ref, quote) in enumerate(q["refs"], 1):
                if quote == WHOLE:
                    refs = _whole(texts, ref, where, report)
                    if not refs:
                        continue
                    shown = "\n".join(texts[r] for r in refs)
                    qh = "<br>\n".join(_quote_html(con, para[r][0], texts[r], 0, texts[r]) for r in refs)
                    rows.append((n, para[refs[0]][0], para[refs[-1]][0] if len(refs) > 1 else None, shown, 0, qh))
                elif ref not in para:
                    report.hard("quiz-ref", where, f"{ref}: no such paragraph")
                else:
                    at = _anchor(texts[ref], quote, where, report)
                    if at is not None:
                        rows.append((n, para[ref][0], None, quote, at,
                                     _quote_html(con, para[ref][0], texts[ref], at, quote)))
        elif q["state"] == "note":
            (ref, origin), = q["refs"]
            if ref not in para:
                report.hard("quiz-ref", where, f"{ref}: no such paragraph")
            else:
                ref_of_note = originals.get(origin)
                if ref_of_note is None:
                    report.hard("quiz-note", where, f"{origin}: no note of the edition has that origin now")
                elif ref_of_note != ref:
                    report.hard("quiz-note", where, f"the note {origin} stands at {ref_of_note}, not {ref}")
                elif origin in notes:
                    fid = notes[origin][0]
                # The paragraph, which the quiz shows until the note is reviewed.
                rows.append((1, para[ref][0], None, texts[ref], 0,
                             _quote_html(con, para[ref][0], texts[ref], 0, texts[ref])))
        for n, pid, last, quote, at, qh in rows:
            if strip_tags(qh) != quote:
                report.hard("quiz-quote-roundtrip", where, "the quote's HTML says other words")
        shown = sum(len(r[3]) for r in rows)
        if shown > SHOWN_WARN:
            report.warn("quiz-long", where, f"{shown} characters shown under the question, over {SHOWN_WARN}")
        con.execute("INSERT INTO quiz_question VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (q["id"], q["paper_n"], q["ord"], q["line"], q["origin"], q["v"], q["mask"],
                     q["multi"], q["text"], q["html"], q["state"], fid))
        con.executemany("INSERT INTO quiz_ref VALUES (?,?,?,?,?,?,?)",
                        [(q["id"], n, pid, last, quote, at, qh) for n, pid, last, quote, at, qh in rows])
    con.executemany("INSERT INTO quiz_answer VALUES (:question_id, :n, :text, :html, :right)",
                    built.answers)
    con.execute("INSERT INTO quiz_paper SELECT paper_n, COUNT(*) FROM quiz_question"
                " WHERE state != 'drop' GROUP BY paper_n")


def _note_origins(built: Built, report) -> dict[str, str]:
    """{origin: ref} of every note of the edition, reviewed or not, for the
    lines that name one; read only when a line does."""
    if not any(q["state"] == "note" for q in built.questions):
        return {}
    papers = study_reader.read(built.repo["tex"], built.repo["at"], range(0, 197), report)
    return {n.origin: n.ref for p in papers.values() for n in p.notes}
