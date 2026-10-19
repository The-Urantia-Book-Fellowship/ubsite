"""The study edition's notes, reviewed one paper at a time (build/study.py).

Proved on a throwaway repository and a made-up paragraph, so the study
edition is never touched: what the reader takes from a paper, how a reviewed
copy is held to it, where a marker stands, and how a note is set.
"""

import pathlib
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "study"))

import block  # noqa: E402
from build import config, study  # noqa: E402
from build.expand import Expanded, Note, Span  # noqa: E402
from build.problems import Report  # noqa: E402
from build.readers import study as reader  # noqa: E402
from build.readers.press import Paper, Paragraph  # noqa: E402
from build.render import render  # noqa: E402

PAPER = textwrap.dedent(r"""
    \upaper{0}{Foreword}
    \vs p000 0:1 In the minds of the mortals of Urantia\fnst{A {nested \bibemph{note}} with \} brace.} --- the name of your world --- there exists great confusion.\fnst{Second.}
    \vs p000 0:2 \pc Plain paragraph.
    \quizlink
    \tunemarkuptwo{nobiblio}{}{%
    \begin{thebibliography}{100}
    \bibitem{p000Hart1}
    Charles Hartshorne.
    {``Man's Vision of God.''}
    {\em Chicago: Willett, Clark \&\ Company}, 1941.
    \end{thebibliography}
    }
    """).lstrip()

PRESS = {"0:0.1": "In the minds of the mortals of Urantia—the name of your world—there exists"
                  " great confusion respecting the meanings of such terms as God, divinity, and deity.",
         "0:0.2": "It is exceedingly difficult to present enlarged concepts and advanced truth."}
CHART = "https://urantiabooksources.com/wp-content/uploads/2019/12/000.pdf"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                           "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def press():
    paras = []
    for ref, text in PRESS.items():
        s, n = ref.split(":")[1].split(".")
        paras.append(Paragraph(0, int(s), int(n), "vs", 1, Expanded(text, [], [], {}, set())))
    return [Paper(0, "Foreword", None, {0: ""}, paras)]


def codes(report):
    return sorted({p.code for p in report.problems})


class Study(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name) / "study"
        self.tex = self.repo / "tex"
        self.tex.mkdir(parents=True)
        (self.tex / "p000.tex").write_text(PAPER, encoding="utf-8")
        git(self.repo, "init", "-q")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "v1")
        self.at = git(self.repo, "rev-parse", "HEAD")
        self.data = pathlib.Path(self.tmp.name) / "data"
        self.data.mkdir()
        self.block = {"path": self.data, "charts": {0: {"url": CHART}}}
        report = Report()
        self.orig = reader.read(self.tex, self.at, [0], report)[0]
        self.assertEqual(report.problems, [])

    def tearDown(self):
        self.tmp.cleanup()

    def toml(self, notes=None, chart=CHART, sources=None, dropped=None, dated="2019-12-04"):
        o = self.orig
        if notes is None:
            notes = [("0:0.1", "mortals of Urantia", o.notes[0].origin,
                      r"See \cite{Hart}, p.~8: ``seven'' cases.", "block")]
        if dropped is None:
            dropped = [("at", "0:0.1", o.notes[1].origin, "the edition's own reading")]
        if sources is None:
            sources = [("Hart", o.sources[0].origin, r"Charles Hartshorne, \emph{Man's Vision of God} (1941).")]
        out = ["paper = 0", f'chart = "{chart}"'] + ([f"chart_date = {dated}"] if dated else []) + [""]
        for key, origin, tex in sources:
            out += ["[[source]]", f'key = "{key}"', f'origin = "{origin}"', f"tex = '''{tex}'''", ""]
        for at, after, origin, tex, credit in notes:
            out += ["[[note]]", f'at = "{at}"', f'after = "{after}"', f'origin = "{origin}"',
                    f"tex = '''{tex}'''"] + ([f'credit = "{credit}"'] if credit else []) + [""]
        for kind, what, origin, why in dropped:
            out += ["[[dropped]]", f'{kind} = "{what}"', f'origin = "{origin}"', f'why = "{why}"', ""]
        (self.data / "000.toml").write_text("\n".join(out), encoding="utf-8")

    def attach(self):
        report = Report()
        cur = study.load_curated(report, self.data)
        papers = press()
        built = study.attach(papers, cur, {"tex": self.tex, "at": self.at}, self.block, report)
        return papers, built, report

    # -- the reader -------------------------------------------------------
    def test_reader_counts_braces_and_skips_escapes(self):
        n = self.orig.notes
        self.assertEqual([x.body for x in n],
                         ["A {nested \\bibemph{note}} with \\} brace.", "Second."])
        self.assertEqual([(x.ref, x.k) for x in n], [("0:0.1", 0), ("0:0.1", 1)])
        self.assertTrue(n[1].before.endswith("great confusion."))
        self.assertEqual(n[0].origin, reader.digest(n[0].body))
        s = self.orig.sources
        self.assertEqual([x.key for x in s], ["p000Hart1"])
        self.assertEqual(s[0].body, "Charles Hartshorne.\n{``Man's Vision of God.''}\n"
                                    "{\\em Chicago: Willett, Clark \\&\\ Company}, 1941.")

    def test_reader_reads_the_commit_not_the_worktree(self):
        (self.tex / "p000.tex").write_text(PAPER.replace("Second.", "Changed."), encoding="utf-8")
        self.assertEqual(reader.read(self.tex, self.at, [0], Report())[0].notes[1].body, "Second.")
        self.assertEqual(reader.read(self.tex, "worktree", [0], Report())[0].notes[1].body, "Changed.")

    def test_reader_refuses_what_it_cannot_be_sure_of(self):
        for bad, code in [(PAPER.replace("Second.}", "Second.} % a comment"), "study-note-comment"),
                          (PAPER + "\\section{x\\fnst{y}}\n", "study-note-unplaced"),
                          (PAPER.replace("\\tunemarkuptwo{nobiblio}{}{%\n", ""),
                           "study-bibliography-wrapper"),
                          (PAPER + "\\bibitem{stray}\n", "study-bibitem-unwrapped"),
                          (PAPER.replace("Second.}", "Second."), "study-note-unbalanced")]:
            with self.subTest(code=code):
                report = Report()
                reader.read_paper(0, bad, report)
                self.assertIn(code, codes(report))

    # -- accounting -------------------------------------------------------
    def test_a_reviewed_paper_attaches(self):
        self.toml()
        papers, built, report = self.attach()
        self.assertEqual(report.problems, [])
        q = papers[0].paragraphs[0]
        a = PRESS["0:0.1"].index("Urantia") + len("Urantia")
        self.assertEqual([(s.start, s.attr) for s in q.ex.spans],
                         [(a, {"kind": "study", "key": "st0_0_1_0", "n": 1, "hs": True})])
        note = q.ex.notes[0]
        self.assertEqual((note.offset, note.kind), (a, "study"))
        self.assertEqual(note.text, "See [1], p.\u00a08: “seven” cases.")
        self.assertEqual(built.papers[0]["block_date"], "2019-12-04")
        self.assertEqual(built.papers[0]["n_dropped"], 1)
        self.assertEqual(built.notes[0]["cites"], ["Hart"])
        self.assertEqual(built.sources[0]["text"], "Charles Hartshorne, Man’s Vision of God (1941).")
        self.assertIn('<a class="fn" href="#fnst0_0_1_0" id="fnrefst0_0_1_0" data-k="st"'
                      ' data-n="1" data-hs="1" aria-label="Note 1"></a>—the name',
                      render(q.ex.text, q.ex.spans, "0_0_1"))

    def test_a_note_on_the_words_of_a_1955_reading(self):
        """A study note may stand on the very words a 1955 reading marks
        (0:1.24's edition note did, after "perfection in all").  The press's
        marker stays first and keeps its number, the study note's follows it,
        and each links its own note."""
        self.toml()
        papers = press()
        q = papers[0].paragraphs[0]
        a = PRESS["0:0.1"].index("Urantia") + len("Urantia")
        q.ex.notes.append(Note(a, "variant-1955", "Urantia", "Urantia", []))
        q.ex.spans.append(Span(a, a, "fnref", {"kind": "variant-1955", "i": 0}))
        report = Report()
        study.attach(papers, study.load_curated(report, self.data),
                     {"tex": self.tex, "at": self.at}, self.block, report)
        self.assertEqual(report.problems, [])
        self.assertEqual([(n.offset, n.kind) for n in q.ex.notes], [(a, "variant-1955"), (a, "study")])
        html = render(q.ex.text, q.ex.spans, "0_0_1")
        self.assertIn('Urantia<a class="fn" href="#fn0_0_1_0" id="fnref0_0_1_0" data-k="1955"'
                      ' aria-label="1955 reading"></a><a class="fn" href="#fnst0_0_1_0"'
                      ' id="fnrefst0_0_1_0" data-k="st" data-n="1"', html)

    def test_every_original_is_accounted_for_once(self):
        o = self.orig
        for kw, code in [({"dropped": []}, "study-unaccounted"),
                         ({"dropped": [("at", "0:0.1", o.notes[0].origin, "twice")]},
                          "study-origin-unknown"),
                         ({"dropped": [("at", "0:0.2", o.notes[1].origin, "elsewhere")]},
                          "study-moved"),
                         ({"sources": []}, "study-unaccounted")]:
            with self.subTest(code=code):
                self.toml(**kw)
                self.assertIn(code, codes(self.attach()[2]))

    def test_a_source_the_review_adds(self):
        """A work a note quotes and the edition does not list is carried with
        origin "none": counted against no \\bibitem, stored without an origin,
        and like any source, cited by a note or a failure."""
        o = self.orig
        hart = ("Hart", o.sources[0].origin, r"Charles Hartshorne, \emph{Man's Vision of God} (1941).")
        white = ("White1911", "none", r"Ellen G. White, \emph{The Great Controversy} (1911).")
        cited = [("0:0.1", "mortals of Urantia", o.notes[0].origin,
                  r"See \cite{Hart}, and White~\cite{White1911}, p.~493.", "block")]
        self.toml(sources=[hart, white], notes=cited)
        _, built, report = self.attach()
        self.assertEqual(report.problems, [])
        self.assertEqual([(s["key"], s["origin"]) for s in built.sources],
                         [("Hart", o.sources[0].origin), ("White1911", None)])
        self.toml(sources=[hart, white])
        self.assertEqual(codes(self.attach()[2]), ["study-source-uncited"])
        self.toml(sources=[white], notes=cited)
        self.assertIn("study-unaccounted", codes(self.attach()[2]))

    def test_a_key_names_one_work_in_every_paper(self):
        """The Bibliography lists a work once, by its key, whichever paper
        cites it: the same key for two works fails, and two keys for one."""
        hart = {"paper_n": 0, "key": "Hartshorne", "html": "Charles Hartshorne, <em>Man’s Vision</em>."}
        knud = {"paper_n": 1, "key": "Knudson", "html": "Albert C. Knudson, <em>The Doctrine of God</em>."}
        for later, want in [({**hart, "paper_n": 2}, []),
                            ({**knud, "paper_n": 2}, []),
                            ({**knud, "paper_n": 2, "key": "Hartshorne"}, ["study-source-key"]),
                            ({**hart, "paper_n": 2, "key": "Hartshorne1941"}, ["study-source-key"]),
                            ({**hart, "paper_n": 2, "html": "C. Hartshorne, <em>Man’s Vision</em>."},
                             ["study-source-key"])]:
            with self.subTest(later=later):
                report = Report()
                study.one_work_one_key([hart, knud, later], report)
                self.assertEqual(codes(report), want)

    def test_a_note_changed_upstream_fails_until_reviewed(self):
        self.toml()
        (self.tex / "p000.tex").write_text(PAPER.replace("Second.", "Second, revised."), encoding="utf-8")
        git(self.repo, "commit", "-qam", "v2")
        self.at = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(codes(self.attach()[2]), ["study-origin-unknown", "study-unaccounted"])

    def test_blocks_chart_is_never_older_than_the_review(self):
        self.toml(chart=CHART.replace("2019/12", "2016/11"))
        self.assertIn("block-chart-revised", codes(self.attach()[2]))
        self.toml(chart="none", dated=None, notes=[("0:0.1", "mortals of Urantia", self.orig.notes[0].origin,
                                                    r"See \cite{Hart}.", None)])
        self.assertEqual(codes(self.attach()[2]), ["block-chart-new"])
        self.block = {"path": self.data, "charts": {}}
        self.assertEqual(codes(self.attach()[2]), [])

    def test_a_chart_is_named_with_blocks_date(self):
        """The card's credit gives the chart's date as Block gives it, which
        the copy names: never after the month the address says it was
        uploaded, never missing beside a chart, never beside none."""
        none = dict(chart="none", notes=[("0:0.1", "mortals of Urantia", self.orig.notes[0].origin,
                                          r"See \cite{Hart}.", None)])
        for kw, want in [({"dated": "2019-12-31"}, []),
                         ({"dated": "2020-01-01"}, ["study-chart-date"]),
                         ({"dated": None}, ["study-chart-date"]),
                         ({"dated": '"December 4, 2019"'}, ["study-chart-date"]),
                         ({**none, "dated": "2019-12-04"}, ["study-chart-date"]),
                         ({**none, "dated": None}, [])]:
            with self.subTest(**kw):
                self.block = {"path": self.data,
                              "charts": {} if kw.get("chart") == "none" else {0: {"url": CHART}}}
                self.toml(**kw)
                self.assertEqual(codes(self.attach()[2]), want)

    def test_each_reviewed_chart_date_is_blocks_own(self):
        """Held to the chart itself, which the build never opens."""
        b = config.block()
        for f in sorted(study.DATA.glob("[0-9][0-9][0-9].toml")):
            doc = tomllib.loads(f.read_text(encoding="utf-8"))
            pdf = b["path"] / f"{doc['paper']:03d}.pdf"
            if doc["chart"] == "none" or not pdf.exists():
                continue
            with self.subTest(f.name):
                self.assertEqual(doc["chart_date"], block.dated(pdf))

    def test_strict_keys(self):
        self.toml()
        f = self.data / "000.toml"
        f.write_text(f.read_text() + "\n[[note]]\nat = 'x'\n", encoding="utf-8")
        self.assertEqual(codes(self.attach()[2]), ["study-missing-key"])
        f.write_text("paper = 0\nchart = 'none'\nnotes = []\n", encoding="utf-8")
        self.assertEqual(codes(self.attach()[2]), ["study-unknown-key"])

    # -- where a marker stands ---------------------------------------------
    def test_after_is_once_and_whole_words(self):
        o = self.orig.notes[0].origin
        for after in ("of", "mortals of Uran", "ortals of Urantia", "not in the text", "Urantia "):
            with self.subTest(after=after):
                self.toml(notes=[("0:0.1", after, o, r"x \cite{Hart}.", None)])
                self.assertEqual(codes(self.attach()[2]), ["study-after"])
        self.toml(notes=[("0:0.1", "name of your world—", o, r"x \cite{Hart}.", None)])
        papers, _, report = self.attach()
        self.assertEqual(report.problems, [])
        self.assertEqual(papers[0].paragraphs[0].ex.notes[0].offset,
                         PRESS["0:0.1"].index("there exists"))

    def test_notes_in_the_order_of_the_text(self):
        o = self.orig.notes
        self.toml(notes=[("0:0.1", "great confusion", o[0].origin, "b.", None),
                         ("0:0.1", "Urantia", o[1].origin, "a.", None)], dropped=[],
                  sources=[])
        self.assertIn("study-order", codes(self.attach()[2]))

    # -- how a note is set ------------------------------------------------
    def expand(self, tex, sources=None):
        report = Report()
        paras = {"1:2.9": None, "1:7.1": None, "1:7.3": None}
        out = study.expand(tex, paras, sources if sources is not None else {"Hart": {}}, "t", report)
        return out, codes(report)

    def test_tex_is_set_as_tex_sets_it(self):
        (text, html, cites), bad = self.expand(
            r"Nave's ``word'' and `this'---Psalms~104:2, oor\'anteeya, 12.6\,ly\ldots{} \textsc{Lord}")
        self.assertEqual(bad, [])
        self.assertEqual(text, "Nave’s “word” and ‘this’—Psalms\u00a0104:2, oorántee"
                               "ya, 12.6\u202fly… Lord")

    def test_a_suffix_keeps_its_hyphen(self):
        # Tigran saw "suffix -" end a line, and "tia" begin the next.
        (text, html, _), bad = self.expand(
            r"the Latin suffix \textit{-tia}, the ending -el/-al, but self\hyp{}realization")
        self.assertEqual(bad, [])
        self.assertIn('<em><span class="nobreak">-tia</span></em>', html)
        self.assertIn('<span class="nobreak">-el</span>/<span class="nobreak">-al</span>', html)
        self.assertIn("self-realization", html)
        self.assertEqual(text, "the Latin suffix -tia, the ending -el/-al, but self-realization")

    def test_a_long_tie_is_reported(self):
        report = Report()
        study.expand(r"Sir~Arthur~S.\,Eddington and Psalms~104:1--2", {}, {}, "t", report)
        self.assertEqual([(p.severity, p.code) for p in report.problems], [("warn", "study-long-tie")])
        report = Report()
        study.expand(r"Sir~Arthur S. Eddington, p.~8, 1~Corinthians~13:12, Dr~Sadler", {}, {}, "t", report)
        self.assertEqual(report.problems, [])

    def test_links_and_citations(self):
        (text, html, cites), bad = self.expand(
            r"\cite{Hart}, see \bibref[1:2.9]{p001 2:9} and \bibref[1:7.1--3]{p001 7:1}; \cite{Hart}.")
        self.assertEqual(bad, [])
        self.assertEqual(text, "[1], see 1:2.9 and 1:7.1–3; [1].")
        self.assertIn('<a href="/1:2.9">1:2.9</a>', html)
        self.assertIn('<a href="/1:7.1-3">1:7.1–3</a>', html)
        self.assertEqual(cites, ["Hart"])
        for tex, code in [(r"\cite{Nobody}", "study-cite-unknown"),
                          (r"\bibref[1:2.8]{p001 2:9}", "study-bibref"),
                          (r"\bibref[1:3.1]{p001 3:1}", "study-bibref"),
                          (r"100% sure", "comment-in-note"),
                          (r"\unknown{x}", "unknown-macro"),
                          (r"$a", "study-math-unpaired"),
                          (r"$\frac{a}{b}$", "study-math")]:
            with self.subTest(tex=tex):
                self.assertIn(code, self.expand(tex)[1])

    def test_math_inside_a_macro_and_languages(self):
        (text, html, _), bad = self.expand(
            r"\bibemph{so $2^3 - 1 = 7$} and \textheb{שְׁמַע} and \textgreek{οὐρανός}")
        self.assertEqual(bad, [])
        self.assertIn('<em>so <math xmlns="http://www.w3.org/1998/Math/MathML"><msup><mn>2</mn>', html)
        self.assertIn('<span class="lang" lang="he" dir="rtl">שְׁמַע</span>', html)
        self.assertIn('<span class="lang" lang="grc">οὐρανός</span>', html)
        self.assertEqual(text, "so 23−1=7 and שְׁמַע and οὐρανός")


if __name__ == "__main__":
    unittest.main()
