"""The quiz (build/quiz.py, data/quiz/, tools/quiz/convert.py).

Its files on made-up examples, so each refusal is seen to refuse; the ids and
the layouts of the answers, kept for ever, against the last commit; the
conversion from the study edition's quiz.tex, and the rewrites it made; and
the pages.
"""

import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import quiz  # noqa: E402
from build.problems import Report  # noqa: E402
from tools.quiz import convert  # noqa: E402

ONE = """
[[question]]
id = 1
q = 'What is the name of our own world?'
a = ['Mars', 'Urantia']
right = ['Urantia']
refs = ['0:0.1 «Urantia»']
"""


def load(files: dict[str, str]):
    """data/quiz/ made of these files, loaded: (problems' codes, questions, gone)."""
    with tempfile.TemporaryDirectory() as d:
        for name, text in files.items():
            (pathlib.Path(d) / name).write_text(text, encoding="utf-8")
        r = Report()
        qs, gone = quiz.load(r, pathlib.Path(d))
    return [p.code for p in r.problems], qs, gone


def paper(n: int, body: str = ONE, head: str = "") -> dict[str, str]:
    return {f"{n:03d}.toml": f"paper = {n}\n{head}{body}"}


class Files(unittest.TestCase):
    def test_a_good_file(self):
        codes, qs, gone = load(paper(0, ONE + ONE.replace("id = 1", "id = 2"), "gone = [3]\n"))
        self.assertEqual(codes, [])
        self.assertEqual([(q.id, q.paper, q.ord, q.v) for q in qs], [(1, 0, 1, 1), (2, 0, 2, 1)])
        self.assertEqual(qs[0].answers, [("Mars", False), ("Urantia", True)])
        self.assertEqual((qs[0].state, qs[0].refs), ("text", [("0:0.1", "Urantia")]))
        self.assertEqual(gone, [3])

    def test_refusals(self):
        def refused(body, code, head=""):
            self.assertIn(code, load(paper(0, body, head))[0], body)
        refused(ONE.replace("right = ['Urantia']", "right = ['Earth']"), "quiz-right")
        refused(ONE.replace("right = ['Urantia']", "right = []"), "quiz-right")
        refused(ONE.replace("a = ['Mars', 'Urantia']", "a = ['Urantia']"), "quiz-answers")
        refused(ONE.replace("a = ['Mars', 'Urantia']", "a = ['Urantia', 'Urantia']"), "quiz-answers")
        refused(ONE.replace("id = 1", "id = 1\ncolour = 'red'"), "quiz-question")
        refused(ONE.replace("id = 1", "id = 1\nstate = 'none'"), "quiz-question")
        refused(ONE.replace("id = 1", "id = 1\nstate = 'maybe'").replace("refs = ['0:0.1 «Urantia»']", ""),
                "quiz-question")
        refused(ONE.replace("id = 1", "id = 1\nv = 0"), "quiz-question")
        refused(ONE.replace("«Urantia»", "Urantia"), "quiz-refs")
        refused(ONE.replace("0:0.1 «Urantia»", "0:3.2-8 «The First»"), "quiz-refs")
        refused(ONE.replace("0:0.1 «Urantia»", "0:3.8-2"), "quiz-refs")
        refused(ONE.replace("refs = ['0:0.1 «Urantia»']", "note = '32:2.12'"), "quiz-note")
        refused(ONE, "quiz-ids", "gone = [1]\n")
        self.assertIn("quiz-ids", load({**paper(0), **paper(1)})[0])
        self.assertIn("quiz-file", load({"000.toml": f"paper = 1\n{ONE}"})[0])
        self.assertIn("quiz-file", load({"0.toml": f"paper = 0\n{ONE}"})[0])
        self.assertIn("quiz-file", load({"000.toml": f"paper = 0\ntitle = 'x'\n{ONE}"})[0])

    def test_what_answers_a_question(self):
        """Several passages in the order shown (Tigran, 2026-10-29: 13:1.1 and
        13:2.7-8), a run of paragraphs shown whole, a note, nothing, or not yet."""
        refs = "refs = ['13:1.1', '13:2.7-8', '13:1.5 «The secrets»']"
        codes, qs, _ = load(paper(13, ONE.replace("refs = ['0:0.1 «Urantia»']", refs)))
        self.assertEqual(codes, [])
        self.assertEqual(qs[0].refs, [("13:1.1", "¶"), ("13:2.7-8", "¶"), ("13:1.5", "The secrets")])
        for line, state, rs in (("note = '32:2.12 8fbb4aa5e5c51c7f'", "note", [("32:2.12", "8fbb4aa5e5c51c7f")]),
                                ("state = 'none'", "none", []), ("state = 'drop'", "drop", []), ("", "-", [])):
            codes, qs, _ = load(paper(0, ONE.replace("refs = ['0:0.1 «Urantia»']", line)))
            self.assertEqual((codes, qs[0].state, qs[0].refs), ([], state, rs), line)

    def test_which_answers_keep_their_order(self):
        """Shuffled each time they are asked, but yes and no, rising numbers,
        the days, and an answer that names the others (Tigran, 2026-11-22)."""
        fixed = quiz.fixed_order
        self.assertTrue(fixed(["yes", "no"]))
        self.assertTrue(fixed(["no, never", "yes, during every trip to Paradise"]))
        self.assertTrue(fixed(["1 year", "2 years", "3 years", "5 years", "12 years"]))
        self.assertTrue(fixed(["about 135 million years ago", "about 200 million years ago", "about 300 million years ago"]))
        self.assertTrue(fixed(["3", "4", "7", "12", "Infinitely many"]))
        self.assertTrue(fixed(["36,000 km/s", "100,000 km/s", "299,792 km/s", "unlimited"]))
        self.assertTrue(fixed(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))
        self.assertTrue(fixed(["Spirit of Truth", "Return to the world himself", "Both"]))
        self.assertTrue(fixed(["At the time of Adam", "At the mortal transit of Jesus", "All three"]))
        self.assertFalse(fixed(["3", "7", "12", "24", "4"]))                 # numbers, not in order
        self.assertFalse(fixed(["Mars", "Venus", "Urantia"]))
        self.assertFalse(fixed(["both teach that there are many gods", "both deny that matter is real"]))
        self.assertFalse(fixed(["100,000 ly", "200,000 ly"]))                 # two numbers are no scale
        # Its file overrules the rule, either way.
        for line, f in (("shuffle = false", 1), ("shuffle = true", 0)):
            codes, qs, _ = load(paper(0, ONE.replace("id = 1", f"id = 1\n{line}")))
            self.assertEqual((codes, qs[0].shuffle), ([], f == 0))
        self.assertIn("quiz-question", load(paper(0, ONE.replace("id = 1", "id = 1\nshuffle = 'yes'")))[0])

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
        self.assertEqual(quiz.paragraphs("0:3.2-4"), ["0:3.2", "0:3.3", "0:3.4"])
        self.assertEqual(quiz.paragraphs("32:2.11"), ["32:2.11"])

    def test_the_files(self):
        r = Report()
        qs, gone = quiz.load(r)
        self.assertEqual(r.problems, [])
        self.assertEqual((len(qs), len({q.paper for q in qs}), len(gone)), (811, 125, 39))
        self.assertEqual(sum(sum(right for _, right in q.answers) > 1 for q in qs), 37)
        self.assertEqual(sorted(q.id for q in qs if q.state == "drop"), list(range(40, 47)))


def layouts(files: dict[str, str]) -> dict[int, tuple]:
    """{id: (paper, v, answers, mask)} of a data/quiz/, and {id: (paper, None ...)} for one gone."""
    out = {}
    for name, text in files.items():
        d = tomllib.loads(text)
        for i in d.get("gone", []):
            out[i] = (d["paper"], None, None, None)
        for q in d.get("question", []):
            mask = sum(1 << n for n, a in enumerate(q["a"]) if a in q["right"])
            out[q["id"]] = (d["paper"], q.get("v", 1), tuple(q["a"]), mask)
    return out


def git(*args) -> str | None:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


class Kept(unittest.TestCase):
    """A question's id and paper never change, nor an id come back once gone:
    the browser and the board keep answers by id.  And an answer is kept by
    its position under the layout v names, so a change to the answers' number,
    their order or which are right raises v (data/quiz/README.md)."""

    def now(self):
        return layouts({p.name: p.read_text(encoding="utf-8") for p in (ROOT / "data" / "quiz").glob("*.toml")})

    def test_against_the_last_commit(self):
        names = (git("ls-tree", "--name-only", "HEAD", "data/quiz/") or "").split()
        tomls = [n for n in names if n.endswith(".toml")]
        now = self.now()
        if tomls:
            then = layouts({n: git("show", f"HEAD:{n}") for n in tomls})
            for i, (p, v, answers, mask) in then.items():
                self.assertIn(i, now, f"id {i} is in no file: an id stays, in its paper's gone if deleted")
                p2, v2, answers2, mask2 = now[i]
                self.assertEqual(p2, p, f"id {i} stays in Paper {p}")
                if v is None:
                    self.assertIsNone(v2, f"id {i} is gone, and never given again")
                elif v2 is not None and (len(answers2), mask2) != (len(answers), mask) or \
                        v2 is not None and sorted(answers2) == sorted(answers) and answers2 != answers:
                    self.assertGreater(v2, v, f"id {i}: its answers' layout changed, so v is raised")
                elif v2 is not None:
                    self.assertGreaterEqual(v2, v, f"id {i}: v never goes back")
        else:
            # The commit before the conversion: its ledger, data/quiz/questions.tsv.
            ledger = git("show", "HEAD:data/quiz/questions.tsv")
            if ledger is None:
                self.skipTest("no quiz at the last commit")
            for line in ledger.splitlines():
                if not line or line.startswith(("#", "id\t")):
                    continue
                i, p, _, v, state = line.split("\t")
                self.assertIn(int(i), now, f"id {i}")
                self.assertEqual(now[int(i)][0], int(p), f"id {i}")
                if state == "gone":
                    self.assertIsNone(now[int(i)][1], f"id {i} is gone, and never given again")
                elif now[int(i)][1] is not None:              # or deleted since, its id kept
                    self.assertEqual(now[int(i)][1], int(v), f"id {i}")

    def test_the_rule_is_seen_to_hold(self):
        """What the test above calls a change of layout."""
        a = layouts(paper(0))[1]
        for body, changed in ((ONE.replace("'Mars', 'Urantia'", "'Urantia', 'Mars'"), True),
                              (ONE.replace("'Mars'", "'Mars', 'Venus'"), True),
                              (ONE.replace("right = ['Urantia']", "right = ['Urantia', 'Mars']"), True),
                              (ONE.replace("'Mars'", "'Marss'"), False)):
            b = layouts(paper(0, body))[1]
            self.assertEqual((len(a[2]), a[3]) != (len(b[2]), b[3])
                             or (sorted(a[2]) == sorted(b[2]) and a[2] != b[2]), changed, body)


class Converted(unittest.TestCase):
    """tools/quiz/convert.py, which made data/quiz/ from quiz.tex once."""

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
            self.assertEqual(convert.dates(tex), want, tex)

    def test_american_spelling(self):
        used = set()
        table = {"centre": "center", "manmade": "man-made"}
        got = convert.americanize("Centre, centres, \\centre{x}, CENTRE, manmade", table, used)
        self.assertEqual(got, "Center, centres, \\centre{x}, CENTER, man-made")
        self.assertEqual(used, {"centre", "manmade"})

    def test_quotation_marks(self):
        self.assertEqual(convert.curly("``Father'' and man's `own' $f'(x)$"), "“Father” and man’s ‘own’ $f'(x)$")
        self.assertEqual(convert.lit("man’s"), "'man’s'")
        self.assertEqual(tomllib.loads("x = " + convert.lit("it's \\hyp{}"))["x"], "it's \\hyp{}")

    def test_it_comes_out_the_same(self):
        """Run again, it gives the 817 questions and the five ids gone, each
        string expanding as quiz.tex's did (the conversion checks that itself),
        and every question it made is in data/quiz/ under its id and paper."""
        from build import config
        if not pathlib.Path(config.load()["study"]["tex"]).exists():
            self.skipTest("no study edition here")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(convert.main(["--out", d]), 0)
            made = layouts({p.name: p.read_text(encoding="utf-8") for p in pathlib.Path(d).glob("*.toml")})
        self.assertEqual((len(made), sum(v[1] is None for v in made.values())), (822, 5))
        now = Kept().now()
        for i, (p, *_) in made.items():
            self.assertEqual(now[i][0], p, f"id {i}")


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

    def test_paper_1(self):
        """The edition's one question on Paper 1 and the 28 written for the site
        on 2026-11-22, in the order of the text; one answered by a study note."""
        st, _, body = self.get("/quiz/1")
        self.assertEqual(st, 200)
        d = self.data(body)
        ids = [q["id"] for q in d["q"]]
        self.assertEqual(ids, [823, 824, 58, *range(825, 851)])
        q = {x["id"]: x for x in d["q"]}
        self.assertEqual((q[829]["s"]["k"], q[829]["s"]["ref"]), ("note", "1:0.1"))
        self.assertIn("Psalms", q[829]["s"]["h"])
        self.assertEqual(q[828]["m"], 0b101)                    # two right of five
        self.assertEqual(q[823]["s"]["p"][0]["ref"], "1:0.5")
        self.assertIn("God-consciousness", q[823]["s"]["p"][0]["h"])
        self.assertNotIn("f", q[823])                           # its answers shuffled
        js = (ROOT / "ubsite" / "static" / "quiz.js").read_text()
        self.assertIn("start(shuffle(D.q.slice()), D.paper)", js)      # the questions, each time
        self.assertIn("if (!q.f) shuffle(R.order);", js)               # and the answers, but `f`
        self.assertIn("choose(R.order[k])", js)                        # a key the place as shown
        d0 = self.data(self.get("/quiz/0")[2])
        self.assertEqual({x["id"]: x.get("f") for x in d0["q"]}[49], 1)   # yes | no, as written

    def test_the_quiz_page_has_every_question(self):
        st, _, body = self.get("/quiz")
        self.assertEqual(st, 200)
        d = self.data(body)
        self.assertEqual((len(d["q"]), len(d["papers"])), (804, 125))     # 40 dropped: Paper 0's 8, 11 Q20, and 31 ruled 2026-10-30,
        self.assertEqual(body.count('<li data-n="'), 125)                   # Paper 138's one question among them
        # The Foreword's row twice, on its own and in Part I, for Settings'
        # Foreword in Part I (quiz.html; 2026-11-04); its choice in the list
        # is sent, and quiz.js takes it out while the switch is on.
        self.assertEqual(body.count('data-n="0"'), 2)
        self.assertIn('<ol class="toc qtoc fwout">\n    <li data-n="0"><a href="/quiz/0"><b>0</b> Foreword</a>', body)
        self.assertIn('<li class="fwin" data-n="0"><a href="/quiz/0"><b>0</b> Foreword</a>', body)
        self.assertIn('<option value="0"', body)

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

    def test_the_board_has_no_setting(self):
        """No Quiz board switch since 2026-11-18 (Tigran): the offer after a
        quiz can be left unanswered.  With Quiz off there is still no offer
        and no link to the board."""
        from ubsite import settings
        self.assertNotIn("quizboard", [s[0] for s in settings.SHOW])
        self.assertNotIn("quizboard", settings.NEEDS)
        css = (ROOT / "ubsite" / "static" / "ub.css").read_text()
        self.assertNotIn("data-quizboard", css)
        self.assertIn(':root[data-quiz="off"] .qboard { display: none; }', css)
        js = (ROOT / "ubsite" / "static" / "quiz.js").read_text()
        self.assertNotIn("g.quizboard", js)
        self.assertIn("return g.quiz !== false;", js)
        ru = (ROOT / "ubsite" / "ru.toml").read_text(encoding="utf-8")
        self.assertNotIn('"Quiz board" =', ru)
        # A browser that kept it off draws no attribute for it: the head script
        # reads the settings there are, and this is none.
        page = self.get("/quiz")[2]
        self.assertNotIn("quizboard", page.replace('class="prose quiz quizboard"', ""))


if __name__ == "__main__":
    unittest.main()
