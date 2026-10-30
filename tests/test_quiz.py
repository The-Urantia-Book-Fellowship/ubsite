"""The quiz (build/quiz.py, build/readers/quiz.py, tools/quiz/).

The reader on made-up files, so each refusal is seen to refuse; the rewrites
of spelling and dates on the forms quiz.tex has; the ledger, whose ids are
kept for ever; and a ruling read from a review as tools/quiz/apply.py reads it.
"""

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "quiz"))

from build import quiz  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import quiz as reader  # noqa: E402

import apply  # noqa: E402


def quiz_tex(body: dict[int, str] | None = None) -> str:
    """A quiz.tex with every paper, and `body[n]` after paper n's \\qpaper."""
    body = body or {}
    return "\\quizheader\n\n" + "".join(f"\\qpaper{{{n}}}{{Title}}\n\n{body.get(n, '')}"
                                       for n in range(197))


ONE = "\\qstart{What is the name of our own world?}\n{Mars}{0}\n{Urantia}{1}\n\\qstop\n\n"


def codes(src: str) -> list[str]:
    r = Report()
    reader.parse(src, r)
    return [p.code for p in r.problems]


class Reader(unittest.TestCase):
    def test_a_good_file(self):
        r = Report()
        qs = reader.parse(quiz_tex({0: ONE, 32: ONE + ONE}), r)
        self.assertEqual(r.problems, [])
        self.assertEqual([(q.paper, q.ord) for q in qs], [(0, 1), (32, 1), (32, 2)])
        self.assertEqual(qs[0].answers, (("Mars", False), ("Urantia", True)))
        self.assertEqual(qs[0].mask, 0b10)
        self.assertEqual(qs[1].origin, qs[2].origin)

    def test_refusals(self):
        self.assertIn("quiz-no-right", codes(quiz_tex({0: ONE.replace("{1}", "{0}")})))
        self.assertIn("quiz-answers", codes(quiz_tex({0: "\\qstart{Q?}\n{only}{1}\n\\qstop\n"})))
        self.assertIn("quiz-comment", codes(quiz_tex({0: ONE.replace("Mars", "Mars % red")})))
        self.assertIn("quiz-stray", codes(quiz_tex({0: ONE + "a line nothing claims\n"})))
        self.assertIn("quiz-answer", codes(quiz_tex({0: ONE.replace("{Mars}{0}", "{Mars}{2}")})))
        self.assertIn("quiz-unclosed", codes(quiz_tex({0: ONE.replace("\\qstop\n", "")})))
        self.assertIn("quiz-papers", codes(quiz_tex().replace("\\qpaper{196}{Title}\n", "")))
        self.assertIn("quiz-header", codes(quiz_tex().replace("\\quizheader\n", "")))

    def test_braces_are_counted(self):
        r = Report()
        qs = reader.parse(quiz_tex({1: "\\qstart{Is \\bibemph{this} it?}\n{a {b} c}{1}\n{d}{0}\n\\qstop\n"}), r)
        self.assertEqual(r.problems, [])
        self.assertEqual((qs[0].tex, qs[0].answers[0][0]), ("Is \\bibemph{this} it?", "a {b} c"))

    def test_the_edition_at_its_pinned_commit(self):
        from build import config
        st = config.load()["study"]
        r = Report()
        qs = reader.read(st["tex"], st["at"], r)
        self.assertEqual(r.problems, [])
        self.assertEqual(len(qs), 817)
        self.assertEqual(sum(bin(q.mask).count("1") > 1 for q in qs), 51)


class Text(unittest.TestCase):
    def test_dates_in_the_books_order(self):
        for tex, want in [
                ("25 March 7 B.C.", "March 25, 7~B.C."),
                ("Midnight, Tuesday 4 April 30 A.D.", "Midnight, Tuesday, April 4, A.D.~30"),
                ("11\\ts{th} February, 2\\,B.C.", "February 11, 2~B.C."),
                ("76\\,A.D.", "A.D.~76"),
                ("37,000 B.C.", "37,000~B.C."),
                ("by 19,000 B.C.?", "by 19,000~B.C.?"),
                # A slip of the edition's stays as it is, for the gate to find.
                ("21 August 7.~B.C.", "21 August 7.~B.C.")]:
            self.assertEqual(quiz.dates(tex), want, tex)

    def test_american_spelling(self):
        used = set()
        table = {"centre": "center", "manmade": "man-made"}
        got = quiz.americanize("Centre, centres, \\centre{x}, CENTRE, manmade", table, used)
        self.assertEqual(got, "Center, centres, \\centre{x}, CENTER, man-made")
        self.assertEqual(used, {"centre", "manmade"})


class Ledger(unittest.TestCase):
    def test_ids_are_kept_since_the_last_commit(self):
        """A question's id and paper never change: the board keeps answers by
        id.  Lines may be added, and a line's other fields ruled on."""
        old = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:data/quiz/questions.tsv"],
                             capture_output=True, text=True)
        if old.returncode != 0:
            self.skipTest("not committed yet")
        def ids(text):
            return [tuple(line.split("\t")[:2]) for line in text.splitlines()
                    if line and not line.startswith(("#", "id\t"))]
        now = ids((ROOT / "data" / "quiz" / "questions.tsv").read_text(encoding="utf-8"))
        then = ids(old.stdout)
        self.assertEqual(now[:len(then)], then)

    def load(self, state, refs):
        """A ledger of one question with these references, loaded."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "questions.tsv"
            path.write_text(f"id\tpaper\torigin\tv\tstate\n1\t0\t{'a' * 16}\t1\t{state}\n", encoding="utf-8")
            (path.with_name("references.tsv")).write_text(
                "id\tn\tref\tquote\n" + "".join(f"1\t{n}\t{ref}\t{q}\n" for n, (ref, q) in enumerate(refs, 1)),
                encoding="utf-8")
            r = Report()
            lines = quiz.load_ledger(r, path)
        return r.problems, lines

    def test_a_run_of_paragraphs_is_shown_whole(self):
        for ref, quote, ok in (("0:3.2-8", quiz.WHOLE, True), ("0:3.2", quiz.WHOLE, True),
                               ("0:3.2-8", "The First Source", False), ("0:3.8-2", quiz.WHOLE, False),
                               ("0:3", "The First Source", False)):
            problems, _ = self.load("text", [(ref, quote)])
            self.assertEqual(problems == [], ok, (ref, quote, problems))

    def test_several_passages(self):
        """A question may be answered by several passages, in the order ruled
        (Tigran, 2026-10-29: 13:1.1 and 13:2.7-8); a note by one."""
        problems, lines = self.load("text", [("13:1.1", quiz.WHOLE), ("13:2.7-8", quiz.WHOLE), ("13:1.5", "The secrets")])
        self.assertEqual(problems, [])
        self.assertEqual(lines[0].refs, [("13:1.1", "¶"), ("13:2.7-8", "¶"), ("13:1.5", "The secrets")])
        self.assertNotEqual(self.load("note", [("13:1.1", "a" * 16), ("13:1.2", "b" * 16)])[0], [])
        self.assertNotEqual(self.load("text", [])[0], [])
        self.assertNotEqual(self.load("none", [("13:1.1", quiz.WHOLE)])[0], [])
        self.assertEqual(self.load("none", [])[0], [])

    def test_no_length_is_refused(self):
        """Since 13:1.5-6, about 850 characters (Tigran, 2026-10-29): the
        build warns over SHOWN_WARN, never refuses."""
        r = Report()
        texts = {"1:1.1": "a" * 2000, "1:1.2": "b" * 2000}
        self.assertEqual(quiz._whole(texts, "1:1.1-2", "w", r), ["1:1.1", "1:1.2"])
        self.assertEqual(r.problems, [])
        self.assertIsNone(quiz._whole({**texts, "1:1.3": "c"}, "1:1.1-4", "w", r))
        self.assertEqual([p.code for p in r.problems], ["quiz-ref"])
        self.assertEqual(quiz.SHOWN_WARN, 1000)

    def test_reconcile_pairs_duplicates_in_order(self):
        qs = reader.parse(quiz_tex({5: ONE + ONE}), Report())
        lines = [quiz.Line(1, 5, qs[0].origin, 1, "-", [], 1),
                 quiz.Line(2, 5, qs[0].origin, 1, "-", [], 2)]
        r = Report()
        got = quiz.reconcile(qs, lines, r)
        self.assertEqual([x.id for x in got], [1, 2])
        self.assertEqual(r.problems, [])
        r = Report()
        quiz.reconcile(qs[:1], lines, r)
        self.assertEqual([p.code for p in r.problems], ["quiz-ledger-gone"])


class Ruling(unittest.TestCase):
    ITEM = {"q": 1, "proposed": "1", "ruling": None,
            "candidates": {"1": "text 32:2.11 «From Jerusem»", "2": "note 32:2.12 8fbb4aa5e5c51c7f",
                           "3": "text 0:3.2-8", "4": "text 0:3.2", "5": "text 13:1.1 «The words» and 13:2.7-8"}}
    W = quiz.WHOLE

    def rule(self, ruling, notes=("8fbb4aa5e5c51c7f",), **kw):
        return apply.decide({**self.ITEM, **kw, "ruling": ruling}, lambda ref: list(notes))

    def test_rulings(self):
        one = ("text", [("32:2.11", "From Jerusem")])
        self.assertEqual(self.rule("yes"), one)
        self.assertEqual(self.rule("Yes."), one)
        self.assertEqual(self.rule("2"), ("note", [("32:2.12", "8fbb4aa5e5c51c7f")]))
        self.assertEqual(self.rule("none"), ("none", []))
        self.assertEqual(self.rule("drop"), ("drop", []))
        self.assertEqual(self.rule("text 32:2.9 «At the last registry»"), ("text", [("32:2.9", "At the last registry")]))
        self.assertEqual(self.rule("note 32:2.12"), ("note", [("32:2.12", "8fbb4aa5e5c51c7f")]))
        self.assertEqual(self.rule("drop until we include the Existential-Flower illustration"), ("drop", []))
        # Tigran's ruling on 6 Q1, 2026-10-29.
        self.assertEqual(self.rule("No, the correct candidate is 1, quite obviously."), one)
        self.assertEqual(self.rule("candidate 2"), ("note", [("32:2.12", "8fbb4aa5e5c51c7f")]))

    def test_a_reference_alone_is_shown_whole(self):
        # Tigran's ruling on the Foreword's seven Absolutes, 2026-10-29.
        for r in ("No, the correct reference is 0:3.2-8", "text 0:3.2-8", "0:3.2-8", "no: 0:3.2–8."):
            self.assertEqual(self.rule(r), ("text", [("0:3.2-8", self.W)]), r)
        self.assertEqual(self.rule("text 0:3.2"), ("text", [("0:3.2", self.W)]))
        # His ruling on 12 Q8, 2026-10-29.
        self.assertEqual(self.rule("The correct reference is 12:5.6-9"), ("text", [("12:5.6-9", self.W)]))
        self.assertEqual(self.rule("No, it is 32:2.9 «At the last registry»"), ("text", [("32:2.9", "At the last registry")]))
        self.assertEqual(quiz.paragraphs("0:3.2-4"), ["0:3.2", "0:3.3", "0:3.4"])
        self.assertEqual(quiz.paragraphs("32:2.11"), ["32:2.11"])

    def test_several_passages(self):
        """His rulings on 13 Q1 and Q10, 2026-10-29: several passages, in order."""
        two = ("text", [("13:1.1", self.W), ("13:2.7-8", self.W)])
        self.assertEqual(self.rule("13:1.1 and 13:2.7-8"), two)
        self.assertEqual(self.rule("No, the correct references are 13:1.1 and 13:2.7-8"), two)
        self.assertEqual(self.rule("text 13:1.1, 13:2.7-8"), two)
        self.assertEqual(self.rule("13:1.5-6"), ("text", [("13:1.5-6", self.W)]))
        self.assertEqual(self.rule("13:1.5 «The secrets of Divinington» and 13:1.6 and 13:2.7 «closed»"),
                         ("text", [("13:1.5", "The secrets of Divinington"), ("13:1.6", self.W), ("13:2.7", "closed")]))
        self.assertEqual(self.rule("5"), ("text", [("13:1.1", "The words"), ("13:2.7-8", self.W)]))
        self.assertEqual(self.rule("yes", proposed="5"), ("text", [("13:1.1", "The words"), ("13:2.7-8", self.W)]))
        self.assertEqual(self.rule("4 and 1"), ("text", [("0:3.2", self.W), ("32:2.11", "From Jerusem")]))
        self.assertEqual(self.rule("1, 3"), ("text", [("32:2.11", "From Jerusem"), ("0:3.2-8", self.W)]))
        self.assertEqual(apply.references("1:1.1 «see 2:2.2 there» and 3:3.3"),
                         [("1:1.1", "see 2:2.2 there"), ("3:3.3", self.W)])

    def test_a_candidate_shown_whole(self):
        """A second reading proposes a run as a candidate, "3. text 0:3.2-8",
        and a ruling names it by number, or says yes to it."""
        self.assertEqual(self.rule("3"), ("text", [("0:3.2-8", self.W)]))
        self.assertEqual(self.rule("4"), ("text", [("0:3.2", self.W)]))
        self.assertEqual(self.rule("yes", proposed="3"), ("text", [("0:3.2-8", self.W)]))
        self.assertEqual(self.rule("No, the correct candidate is 3"), ("text", [("0:3.2-8", self.W)]))

    def test_what_is_not_a_ruling(self):
        for bad in ("", "maybe 32:2.11", "No, it is 0:3.2 or 0:3.3", "No", "No, the correct candidate is 7",
                    "text 0:3.2-8 «The First Source»", "2 and 1", "«words» 13:1.1", "13:1.1 «a» «b»"):
            self.assertIsInstance(self.rule(bad), str, bad)
        self.assertIsInstance(self.rule("note 32:2.12", notes=("a" * 16, "b" * 16)), str)
        self.assertIsInstance(self.rule("yes", proposed="none"), str)

    def test_a_blank_ruling_accepts(self):
        self.assertEqual(apply.accepted(self.ITEM)["ruling"], "yes")
        self.assertEqual(apply.accepted({**self.ITEM, "ruling": "  "})["ruling"], "yes")
        self.assertEqual(apply.accepted({**self.ITEM, "proposed": "none"})["ruling"], "none")
        self.assertEqual(apply.accepted({**self.ITEM, "ruling": "2"})["ruling"], "2")

    def test_hold(self):
        text = {"9:1.1": "The words.", "9:1.2": "Other words.", "9:1.3": "x" * 1200}
        self.assertEqual(apply.hold(text, "text", [("9:1.1", "The words.")], "w"), ([], []))
        self.assertEqual(apply.hold(text, "text", [("9:1.1", "The words."), ("9:1.2", quiz.WHOLE)], "w"), ([], []))
        self.assertEqual(len(apply.hold(text, "text", [("9:1.1", "Other")], "w")[0]), 1)
        self.assertEqual(apply.hold(text, "text", [("9:1.1-3", quiz.WHOLE)], "w")[0], [])
        self.assertEqual(len(apply.hold(text, "text", [("9:1.1-3", quiz.WHOLE)], "w")[1]), 1)    # over 1,000: warned
        self.assertEqual(len(apply.hold(text, "text", [("9:1.1-4", quiz.WHOLE)], "w")[0]), 1)
        self.assertEqual(apply.hold({}, "note", [("9:1.1", "a" * 16)], "w"), ([], []))

    def test_doubtful_md_overrides_a_review(self):
        """A question in var/quiz/doubtful.md is read from there whole: its
        candidates (one more than the review's), its proposal and its ruling."""
        import tempfile
        review = """# Paper 9, for review

## Q1 (id 80, quiz.tex:600)

Q?

- ✓ a

Candidates:
1. text 9:1.1 «The words.»
   score 10

Checked: fine.
Proposed: 1

Ruling: 

## Q2 (id 81, quiz.tex:610)

Q?

Candidates:
1. text 9:1.2 «Other words.»
   score 10

Proposed: 1

Ruling: yes
"""
        doubtful = """# The doubtful ones

# Paper 9, Title

## Q1 (id 80, quiz.tex:600)

Q?

- ✓ a

Candidates:
1. text 9:1.1 «The words.»
   score 10
2. text 9:1.1 and 9:2.1-3

Checked: fine.
Second reading: P — a list, one item to a paragraph.
Why here: P
Proposed: 2 (was 1)

Ruling: 
"""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "review-009.md").write_text(review, encoding="utf-8")
            (root / "doubtful.md").write_text(doubtful, encoding="utf-8")
            old = apply.REVIEWS, apply.DOUBTS
            apply.REVIEWS, apply.DOUBTS = root, root / "doubtful.md"
            try:
                got = {qid: item for n, qid, item in apply.reviewed([9], apply.doubts())}
                plain = {qid: item for n, qid, item in apply.reviewed([9], None)}
            finally:
                apply.REVIEWS, apply.DOUBTS = old
        self.assertEqual(got[80]["proposed"], "2")
        self.assertEqual(got[80]["candidates"]["2"], "text 9:1.1 and 9:2.1-3")
        self.assertEqual(apply.decide(apply.accepted(got[80]), lambda ref: []),
                         ("text", [("9:1.1", quiz.WHOLE), ("9:2.1-3", quiz.WHOLE)]))
        self.assertEqual(apply.decide(apply.accepted(plain[80]), lambda ref: []), ("text", [("9:1.1", "The words.")]))
        self.assertEqual(got[81], plain[81])
        self.assertEqual(got[81]["ruling"], "yes")


class Pages(unittest.TestCase):
    """/quiz, /quiz/N, the invitation at a paper's end, the line on Home."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "tests"))
        from test_appendix_pages import get
        cls.get = staticmethod(get)

    def data(self, body):
        import json
        import re
        m = re.search(r'<script type="application/json" id="ub-quiz">(.*?)</script>', body, re.S)
        return json.loads(m.group(1))

    def test_a_papers_quiz(self):
        st, _, body = self.get("/quiz/32")
        self.assertEqual(st, 200)
        d = self.data(body)
        self.assertEqual((d["paper"], d["count"], len(d["q"])), (32, 6, 6))
        self.assertEqual(d["next"], {"n": 33, "count": 1})
        multi = d["q"][1]
        self.assertEqual((multi["m"], len(multi["a"])), (0b111, 7))
        self.assertIn("neighboring", multi["q"])          # its spelling the book's
        self.assertIn('src="/static/quiz.js', body)
        self.assertEqual(body.count('<li>\n      <p class="qq">'), 6)   # listed without scripts

    def test_the_quiz_page_has_every_question(self):
        st, _, body = self.get("/quiz")
        self.assertEqual(st, 200)
        d = self.data(body)
        self.assertEqual((len(d["q"]), len(d["papers"])), (777, 125))     # 40 dropped: Paper 0's 8, 11 Q20, and 31 ruled 2026-10-30,
        self.assertEqual(body.count('<li data-n="'), 125)                   # Paper 138's one question among them

    def test_a_run_of_paragraphs_answers(self):
        st, _, body = self.get("/quiz/0")
        q = {x["id"]: x for x in self.data(body)["q"]}
        self.assertEqual(q[35]["s"]["ref"], "0:3.2-8")          # the seven Absolutes, ruled so
        self.assertEqual([p["ref"] for p in q[35]["s"]["p"]], ["0:3.2-8"])
        self.assertEqual(q[35]["s"]["p"][0]["h"].count("<br>"), 6)
        self.assertEqual(q[1]["s"]["k"], "text")
        self.assertIn('<a class="qref" href="/0:3.2-8">0:3.2–8</a>', body)
        self.assertFalse(set(range(40, 47)) & set(q))            # dropped until the figure is here

    def test_addresses_that_are_not(self):
        st, _, body = self.get("/quiz/3")
        self.assertEqual(st, 404)
        self.assertIn('Paper 3 has no questions in the quiz', body)
        self.assertEqual(self.get("/quiz/197")[0], 404)
        self.assertEqual(self.get("/quiz/x")[0], 404)
        self.assertEqual(self.get("/quiz/01")[2], self.get("/quiz/1")[2])

    def test_the_invitation_at_a_papers_end(self):
        self.assertIn('<aside class="quizcall">', self.get("/32:5")[2])
        self.assertIn('href="/quiz/32"', self.get("/32:5")[2])
        self.assertNotIn('class="quizcall"', self.get("/32:4")[2])       # not its last section
        self.assertNotIn('class="quizcall"', self.get("/3:6")[2])        # no questions
        self.assertIn('class="quizway"', self.get("/")[2])

    def test_the_setting(self):
        from ubsite import settings
        quiz = next(s for s in settings.SHOW if s[0] == "quiz")
        self.assertEqual((quiz[1], quiz[3]), ("switch", True))
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text()
        self.assertIn(':root[data-quiz="off"] :is(.quizcall, .quizway) { display: none; }', css)


if __name__ == "__main__":
    unittest.main()
