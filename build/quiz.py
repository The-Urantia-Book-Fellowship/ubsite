"""The quiz: its questions, data/quiz/NNN.toml, in the database.

The questions began as The British Study Edition's Cosmic Citizenship Quiz,
its tex/quiz.tex, which the build read from 2026-10-28.  On 2026-11-22 Tigran
gave the edition up ("its essence will migrate into ubsite"), and the quiz was
converted once into data/quiz/ (tools/quiz/convert.py), the master since.  The
site asks it one question at a time, at the end of each paper that has
questions and at /quiz (Tigran, 2026-10-28).  This module reads the files,
makes the rows those pages read, and holds them (data/quiz/README.md):

  * A file to each paper that has questions, each question with its id for
    ever, given once and never reused, as a headword keeps its slug: the
    browser and the board remember answers by it.  An id taken out stays in
    its paper's `gone`.  The paper's questions are asked in the file's order.
  * `v` is the layout of a question's answers, 1 unless the file says: the
    browser and the board store an answer by its position, so when the
    answers' number, order or rightness changes, v is raised, and an answer
    given under the old layout is never marked against the new.
    tests/test_quiz.py holds both against the last commit.
  * A question's answers are shown in a new order each time it is asked
    (Tigran, 2026-11-22: "why not also shuffle the answers of each
    question?"), but where their order means something: yes and no, numbers
    that rise, the days of the week, or an answer that names the others,
    "Both", "All three" (fixed_order(); `fixed` in the database).  `shuffle =
    true` or `false` in a question's file overrules that.  An answer is kept
    by its place in the file whatever order it was shown in.
  * The text is TeX in the book's own spelling, set with the study edition's
    macros (build/quiz_macros.py, trap 1) and its expander (build/study.py);
    the right answers are named by their words.
  * The word gate: every word the site shows is a word of the book (its
    search index), or a word data/quiz/words.tsv allows and says why.  What is
    neither is a slip, and so is a date in the British order, a "~" for about,
    a question asked twice: tests/known-quiz-slips.tsv lists those not yet
    mended, and must list exactly those.  An allowed word nothing uses fails,
    and so does one the book has after all.  A metric unit where the press
    gives miles (trap 31) and a time on the 24-hour clock are no slips: Tigran
    kept them (2026-11-22), and the units' words pass the gate (UNIT_WORDS).
  * What answers a question: one or more passages of the text, `refs`, in the
    order shown, each a paragraph and words quoted from it, which occur there
    once and are whole words, or a paragraph or a run of one section's
    paragraphs shown whole (Tigran, 2026-10-29, of 13:1.1 and 13:2.7-8); or
    a study note, `note`, by the origin build/study.py keys notes by, which the
    quiz shows once its paper's notes are reviewed and the paragraph until
    then, never an unreviewed note; or nothing, `state = 'none'`.  `state =
    'drop'` keeps a question out, and a question with none of these is not
    yet reviewed.  No length is refused: over SHOWN_WARN characters shown
    under one question the build warns, so that a section given by a slip is
    noticed.
"""

from __future__ import annotations

import collections
import dataclasses
import pathlib
import re
import sqlite3
import tomllib

from . import quiz_macros, study
from .readers import study as study_reader
from .readers.study import digest
from .render import render, strip_tags

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "quiz"
WORDS = DATA / "words.tsv"
SLIPS = ROOT / "tests" / "known-quiz-slips.tsv"

# The states a question's row may have: '-' not yet reviewed, and the rest as
# its file says (`refs` is 'text', `note` 'note').
STATES = ("-", "text", "note", "none", "drop")
WHY = ("name", "english", "distractor", "abbreviation")
SLIP_KINDS = ("word", "date", "tilde", "duplicate")
TOP_KEYS = frozenset({"paper", "gone", "question"})
KEYS = frozenset({"id", "v", "q", "a", "right", "refs", "note", "state", "shuffle"})
ANSWERS = range(2, 10)
RE_FILE = re.compile(r"(\d{3})\.toml")
# A paragraph, or a run of one section's paragraphs, "0:3.2-8", as the site's
# addresses write it: a list given an item to a paragraph answers as a whole.
RE_PARAS = re.compile(r"(\d+):(\d+)\.(\d+)(?:-(\d+))?")
# A passage as a ruling words it: "1:1.2 «quoted words»", or a reference alone,
# shown whole.
RE_PASSAGE = re.compile(r"(\d+:\d+\.\d+(?:-\d+)?)(?: «(.+)»)?")
# A study note: its paragraph and its origin.
RE_NOTE = re.compile(r"(\d+:\d+\.\d+) ([0-9a-f]{16})")
# What `refs` holds for a paragraph, or a run of them, shown whole (Tigran,
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
# What the site may not show.
RE_BRITISH_DATE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)? (?:{MONTHS})\b|\d[   ]?A\.D\.")
# The metric units' words, which the word gate lets pass (Tigran, 2026-11-22:
# "Keep metric units and 24h times").
# What keeps a question's answers in their written order (fixed_order): an
# answer of a few words that names the others; a number an answer begins with,
# perhaps after "about" or the like; the days of the week.
RE_OTHERS = re.compile(r"(?:both|neither|all three|all four|all five|all of them|all of these|none of these"
                       r"|none of them|all the others)\b", re.I)
RE_LEADING = re.compile(r"(?:(?:about|over|under|nearly|almost|more than|less than|at least|some|~|≈)\s*)?"
                        r"(\d[\d,]*(?:\.\d+)?)", re.I)
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
UNIT_WORDS = frozenset({"km", "cm", "mm", "m", "ly", "kg", "kilometre", "kilometres",
                        "metre", "metres", "centimetre", "centimetres", "s"})


@dataclasses.dataclass(slots=True)
class Question:
    """A question of data/quiz/, as its file has it."""
    id: int
    paper: int
    ord: int                       # its place in its paper's file, from 1
    v: int
    tex: str
    answers: list[tuple[str, bool]]      # (TeX, right), in the order shown
    state: str
    refs: list                     # [(ref, quote)]: each passage, its words or WHOLE; a note's paragraph and origin
    where: str                     # "data/quiz/001.toml id 58", for a message
    shuffle: bool | None = None    # its file's `shuffle`, overruling fixed_order(); None where it says nothing


@dataclasses.dataclass(slots=True)
class Built:
    """What build() made of data/quiz/: the rows store() writes, once the
    text and its search index are loaded."""
    repo: dict                                 # the study edition, for a note's origin
    questions: list[dict]
    answers: list[dict]
    slips: list[tuple[str, int, str]]          # (kind, id, what), as found
    words: dict[str, str]                      # data/quiz/words.tsv: word -> why
    gone: list[int]


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


def passages(refs, where: str, report) -> list[tuple[str, str]]:
    """`refs` as (ref, quote) pairs, each quote the words or WHOLE."""
    out = []
    if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
        report.hard("quiz-refs", where, "refs: a list of passages, '1:1.2 «quoted words»' or '0:3.2-8'")
        return out
    for r in refs:
        m = RE_PASSAGE.fullmatch(r)
        run = m and RE_PARAS.fullmatch(m[1])
        if not m:
            report.hard("quiz-refs", where, f"{r[:60]!r}: '1:1.2 «quoted words»', or a reference alone, shown whole")
        elif run[4] and (m[2] is not None or int(run[4]) <= int(run[3])):
            report.hard("quiz-refs", where, f"a run of paragraphs, {m[1]}, is shown whole, its last after its first")
        else:
            out.append((m[1], WHOLE if m[2] is None else m[2]))
    return out


def load(report, data: pathlib.Path = DATA) -> tuple[list[Question], list[int]]:
    """Every question of data/quiz/, paper by paper, and the ids gone."""
    out: list[Question] = []
    gone: list[int] = []
    for path in sorted(data.glob("*.toml")):
        m = RE_FILE.fullmatch(path.name)
        at = f"data/quiz/{path.name}"
        if not m:
            report.hard("quiz-file", at, "a paper's file is named NNN.toml")
            continue
        try:
            d = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            report.hard("quiz-file", at, str(e))
            continue
        paper = int(m[1])
        if set(d) - TOP_KEYS or d.get("paper") != paper:
            report.hard("quiz-file", at, f"paper = {paper}, gone and [[question]], nothing else")
            continue
        g = d.get("gone", [])
        if not isinstance(g, list) or not all(isinstance(i, int) and i > 0 for i in g):
            report.hard("quiz-file", at, "gone: a list of ids")
        else:
            gone += g
        for n, x in enumerate(d.get("question", []), 1):
            qid = x.get("id")
            where = f"{at} id {qid}"
            if not isinstance(qid, int) or qid < 1 or set(x) - KEYS:
                report.hard("quiz-question", where, f"its keys are {', '.join(sorted(KEYS))}: {sorted(set(x) - KEYS)}")
                continue
            v, tex, answers, right = x.get("v", 1), x.get("q"), x.get("a"), x.get("right")
            if not isinstance(v, int) or v < 1:
                report.hard("quiz-question", where, "v counts from 1")
            if not isinstance(tex, str) or not tex.strip():
                report.hard("quiz-question", where, "q, the question")
                continue
            if not isinstance(answers, list) or not all(isinstance(a, str) and a.strip() for a in answers) \
                    or len(answers) not in ANSWERS or len(set(answers)) != len(answers):
                report.hard("quiz-answers", where, f"a: {ANSWERS.start} to {ANSWERS.stop - 1} answers, none twice")
                continue
            if not isinstance(right, list) or not right or len(set(right)) != len(right) \
                    or not set(right) <= set(answers):
                report.hard("quiz-right", where, "right: one or more of its answers, word for word")
                continue
            kinds = [k for k in ("refs", "note", "state") if k in x]
            state, refs = "-", []
            if len(kinds) > 1:
                report.hard("quiz-question", where, f"refs, note or state, one of them: {', '.join(kinds)}")
            elif kinds == ["refs"]:
                state, refs = "text", passages(x["refs"], where, report)
            elif kinds == ["note"]:
                mn = RE_NOTE.fullmatch(x["note"]) if isinstance(x["note"], str) else None
                if not mn:
                    report.hard("quiz-note", where, "note: its paragraph and its origin, '32:2.12 8fbb4aa5e5c51c7f'")
                else:
                    state, refs = "note", [(mn[1], mn[2])]
            elif kinds == ["state"]:
                if x["state"] not in ("none", "drop"):
                    report.hard("quiz-question", where, "state: 'none' or 'drop'")
                else:
                    state = x["state"]
            shuffle = x.get("shuffle")
            if shuffle is not None and not isinstance(shuffle, bool):
                report.hard("quiz-question", where, "shuffle: true or false")
                shuffle = None
            out.append(Question(qid, paper, n, v, tex, [(a, a in right) for a in answers], state, refs, where,
                                shuffle))
    ids = [q.id for q in out] + gone
    twice = sorted(i for i, c in collections.Counter(ids).items() if c > 1)
    if twice:
        report.hard("quiz-ids", "data/quiz/", f"ids given twice: {twice}")
    return out, gone


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


def fixed_order(answers: list[str]) -> bool:
    """Whether answers, as shown, keep their written order: yes and no; three
    or more numbers that rise, one answer at most without (\"unknown\"); the
    days of the week in order; or an answer of three words at most that names
    the others ("Both", "All three", "All of them")."""
    a = [x.strip() for x in answers]
    if all(re.match(r"(?:yes|no)\b", x, re.I) for x in a):
        return True
    nums = [m and float(m[1].replace(",", "")) for m in (RE_LEADING.match(x) for x in a)]
    known = [n for n in nums if n is not None]
    if len(known) >= 3 and len(known) >= len(a) - 1 and known == sorted(known):
        return True
    if [x.lower() for x in a] == list(DAYS[:len(a)]):
        return True
    return any(RE_OTHERS.match(x) and len(x.split()) <= 3 for x in a)


# -- the build -----------------------------------------------------------------------

def build(report, repo: dict) -> Built | None:
    """The quiz as data/quiz/ has it, expanded; `repo` is the study edition,
    where a question answered by a note not yet reviewed finds its note."""
    questions, gone = load(report)
    if not questions:
        report.hard("quiz-absent", "data/quiz/", "no question")
        return None
    used = macros_used(questions)
    known = set(quiz_macros.TABLE) | quiz_macros.MATH
    for name in sorted(used - known):
        report.hard("quiz-macro-unknown", "data/quiz/", f"\\{name}: not in build/quiz_macros.py")
    for name in sorted(set(quiz_macros.TABLE) - used):
        report.hard("quiz-macro-unused", "build/quiz_macros.py", f"\\{name}: no question uses it")
    built = Built(repo, [], [], [], load_words(report), gone)
    seen: dict[str, int] = {}
    for q in questions:
        text, html = expand(q.tex, q.where, report)
        mask = sum(1 << i for i, (_, r) in enumerate(q.answers) if r)
        shown = []
        for n, (tex, right) in enumerate(q.answers):
            at, ah = expand(tex, q.where, report)
            shown.append(at)
            built.answers.append({"question_id": q.id, "n": n, "text": at, "html": ah,
                                  "right": int(right)})
        fixed = fixed_order(shown) if q.shuffle is None else not q.shuffle
        built.questions.append({
            "id": q.id, "paper_n": q.paper, "ord": q.ord, "v": q.v, "mask": mask,
            "multi": int(bin(mask).count("1") > 1), "fixed": int(fixed), "text": text, "html": html,
            "state": q.state, "refs": q.refs, "where": q.where})
        same = digest(" ".join([q.tex, *(f"{a} {int(r)}" for a, r in q.answers)]))
        if same in seen:
            built.slips.append(("duplicate", q.id, str(seen[same])))
        seen.setdefault(same, q.id)
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
            for m in RE_BRITISH_DATE.finditer(shown):
                built.slips.append(("date", q["id"], _plain(m.group())))
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


def check_slips(built: Built, report, path: pathlib.Path = SLIPS) -> None:
    known = load_slips(report, path)
    found = set(built.slips)
    where = {q["id"]: q["where"] for q in built.questions}
    for kind, qid, what in sorted(found - known):
        report.hard(f"quiz-slip-{kind}", where.get(qid, f"id {qid}"),
                    f"{what!r}, new: mend it (data/quiz/README.md), or list it in tests/{path.name}")
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
        where = q["where"]
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
        con.execute("INSERT INTO quiz_question VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (q["id"], q["paper_n"], q["ord"], q["v"], q["mask"],
                     q["multi"], q["fixed"], q["text"], q["html"], q["state"], fid))
        con.executemany("INSERT INTO quiz_ref VALUES (?,?,?,?,?,?,?)",
                        [(q["id"], n, pid, last, quote, at, qh) for n, pid, last, quote, at, qh in rows])
    con.executemany("INSERT INTO quiz_answer VALUES (:question_id, :n, :text, :html, :right)",
                    built.answers)
    con.execute("INSERT INTO quiz_paper SELECT paper_n, COUNT(*) FROM quiz_question"
                " WHERE state != 'drop' GROUP BY paper_n")


def _note_origins(built: Built, report) -> dict[str, str]:
    """{origin: ref} of every note of the edition, reviewed or not, for the
    questions that name one; read only when a question does."""
    if not any(q["state"] == "note" for q in built.questions):
        return {}
    papers = study_reader.read(built.repo["tex"], built.repo["at"], range(0, 197), report)
    return {n.origin: n.ref for p in papers.values() for n in p.notes}
