"""The quiz's board (ubsite/board.py, its routes in app.py).

Its marking against ub.db's right answers, the first answer winning, a layout
moved on, names and their clashes, two joins racing; the routes, which every
site answers for its own board and no other origin's page may use (Tigran,
2026-11-18: one board on the main site before, asked across origins); what the
file keeps and does not; and a backup made as deploy.sh makes it, read back.
Each test has a board of its own in a temporary directory: nothing here writes
var/quiz.db.
"""

import asyncio
import json
import pathlib
import sqlite3
import sys
import tempfile
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ubsite import board  # noqa: E402
from ubsite.board import Board, Refused  # noqa: E402

DB = ROOT / "var" / "ub.db"
T1, T2, T3 = "a" * 32, "b" * 32, "c" * 32
# Paper 32's six (build/quiz.py ids 366-371): the right answers' masks.
RIGHT = [[366, 1, 2], [367, 1, 7], [368, 1, 8], [369, 1, 4], [370, 1, 2], [371, 1, 32]]


def call(method: str, path: str, body: bytes = b"", host: str = "ubsite.sigmaai.au",
         origin: str | None = None) -> tuple[int, dict, dict | str]:
    from ubsite.app import app
    headers = [(b"host", host.encode()), (b"content-type", b"application/json"),
               (b"content-length", str(len(body)).encode())]
    if origin:
        headers.append((b"origin", origin.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": headers, "client": ("127.0.0.1", 1), "server": (host, 443)}
    out = {"status": 0, "headers": {}, "body": b""}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(m):
        if m["type"] == "http.response.start":
            out["status"] = m["status"]
            out["headers"] = {k.decode(): v.decode() for k, v in m["headers"]}
        elif m["type"] == "http.response.body":
            out["body"] += m.get("body", b"")

    asyncio.run(app(scope, receive, send))
    text = out["body"].decode()
    try:
        return out["status"], out["headers"], json.loads(text)
    except ValueError:
        return out["status"], out["headers"], text


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Marking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.b = Board(pathlib.Path(self.tmp.name) / "quiz.db")

    def tearDown(self):
        self.tmp.cleanup()

    def line(self, name):
        return next(x for x in self.b.lines()["lines"] if x["name"] == name)

    def test_the_server_marks_first_answers(self):
        self.b.join(T1, "Ganid", RIGHT[:2] + [[368, 1, 1]])       # 368 wrong
        self.assertEqual(self.line("Ganid"), {**self.line("Ganid"), "right": 2, "answered": 3, "papers": 0})
        self.b.add(T1, [[368, 1, 8]] + RIGHT[3:])                # 368 again: the first stands
        self.b._cache = None
        self.assertEqual((self.line("Ganid")["right"], self.line("Ganid")["answered"]), (5, 6))
        self.assertEqual(self.line("Ganid")["papers"], 1)          # every question of 32

    def test_a_multi_answer_question_is_its_whole_set(self):
        self.b.join(T1, "Ruth", [[367, 1, 3]])                   # two of its three
        self.assertEqual(self.line("Ruth")["right"], 0)

    def test_an_answer_under_another_layout_counts_for_nothing(self):
        self.b.join(T1, "Martha", [[366, 2, 2]])
        self.assertEqual((self.line("Martha")["right"], self.line("Martha")["answered"]), (0, 0))

    def test_ranked_by_right_then_who_got_there_first(self):
        self.b.join(T1, "Abner", RIGHT[:1])
        self.b.join(T2, "Nalda", RIGHT[:1])
        self.b.join(T3, "Rodan", RIGHT[:2])
        self.b._cache = None
        self.assertEqual([x["name"] for x in self.b.lines()["lines"]], ["Rodan", "Abner", "Nalda"])

    def test_names(self):
        self.b.join(T1, "  Ganid  of  India ", [])
        self.assertEqual(self.line("Ganid of India")["answered"], 0)
        self.assertEqual(board.name_of("two\n lines")[0], "two lines")   # whitespace folded
        for bad in ("", "x" * 33, "<b>", "a__b", "...", 7, None, "a\u0000b"):
            with self.assertRaises(Refused, msg=repr(bad)):
                self.b.join(T2, bad, [])
        for clash in ("GANID OF INDIA", "Ｇａｎｉｄ of India"):     # folded, full-width too
            with self.assertRaises(Refused) as e:
                self.b.join(T2, clash, [])
            self.assertEqual(e.exception.status, 409)
        self.b.join(T1, "Ganid", [])                             # one's own line, renamed
        self.assertEqual([x["name"] for x in self.b.lines()["lines"]], ["Ganid"])

    def test_tokens_and_answers_are_checked(self):
        for t in ("short", "A" * 32, "g" * 32, None):
            with self.assertRaises(Refused):
                self.b.join(t, "Thomas", [])
        for a in ([[366, 1]], [[366, 1, 0]], [[366, 1, 512]], "x", [[366, 1, 2.0]], [[0, 1, 1]]):
            with self.assertRaises(Refused, msg=repr(a)):
                self.b.join(T1, "Thomas", a)
        with self.assertRaises(Refused) as e:
            self.b.add(T2, [])
        self.assertEqual(e.exception.status, 404)

    def test_two_joins_race_for_one_name(self):
        got = []

        def join(t):
            try:
                got.append(Board(self.b.path).join(t, "Fortune", [])["line"])
            except Refused as e:
                got.append(e.status)
        threads = [threading.Thread(target=join, args=(f"{i:032x}",)) for i in range(1, 7)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(got, key=str), sorted([1] + [409] * 5, key=str))

    def test_what_the_file_keeps(self):
        self.b.join(T1, "Nathaniel", RIGHT)
        blob = b"".join(p.read_bytes() for p in pathlib.Path(self.tmp.name).iterdir())
        self.assertNotIn(T1.encode(), blob)                       # the token's hash alone
        con = sqlite3.connect(self.b.path)
        cols = {t: [c[1] for c in con.execute(f"PRAGMA table_info({t})")] for t in ("line", "answer")}
        self.assertEqual(cols, {"line": ["id", "name", "fold", "token", "joined", "hidden"],
                                "answer": ["line_id", "question", "v", "mask", "at"]})

    def test_a_backup_reads_back(self):
        self.b.join(T1, "Gonod", RIGHT)
        copy = pathlib.Path(self.tmp.name) / "copy.db"
        sqlite3.connect(self.b.path).backup(sqlite3.connect(copy))     # as deploy.sh makes it
        self.assertEqual(Board(copy).lines(), self.b.lines())

    def test_hidden_and_renamed_by_hand(self):
        self.b.join(T1, "Jacob", [])
        self.assertTrue(self.b.hide("jacob"))
        self.assertEqual(self.b.lines()["lines"], [])
        with self.assertRaises(Refused):
            self.b.join(T2, "Jacob", [])                          # still taken
        self.assertTrue(self.b.hide("Jacob", False))
        self.assertTrue(self.b.rename("Jacob", "Jacob the stonemason"))
        self.assertEqual(self.b.lines()["lines"][0]["name"], "Jacob the stonemason")

    def test_no_file_until_a_write(self):
        self.assertEqual(self.b.lines(), {"lines": []})
        self.assertFalse(self.b.path.exists())


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        board._board = Board(pathlib.Path(self.tmp.name) / "quiz.db")

    def tearDown(self):
        board._board = None
        self.tmp.cleanup()

    def post(self, path, body, **kw):
        return call("POST", path, json.dumps(body).encode(), **kw)

    def test_join_and_answers_at_the_boards_site(self):
        st, h, j = self.post("/quiz/board/join", {"t": T1, "n": "Gonod", "a": RIGHT[:3]})
        self.assertEqual((st, j["name"], j["place"], j["of"]), (200, "Gonod", 1, 1))
        self.assertEqual(h["cache-control"], "no-store")
        st, _, j = self.post("/quiz/board/answers", {"t": T1, "a": RIGHT[3:]})
        self.assertEqual(st, 200)
        st, h, j = call("GET", "/quiz/board/lines")
        self.assertEqual(j["lines"][0]["right"], 6)
        self.assertEqual(h["x-robots-tag"], "noindex")

    def test_refusals(self):
        self.assertEqual(self.post("/quiz/board/join", {"t": T1, "n": "<b>"})[0], 400)
        self.assertEqual(self.post("/quiz/board/answers", {"t": T1, "a": []})[0], 404)
        self.assertEqual(call("POST", "/quiz/board/join", b"not json")[0], 400)
        self.assertEqual(call("POST", "/quiz/board/join", b"[]")[0], 400)
        # Deeper than json.loads goes, inside the size allowed: a 500 until 2026-11-09.
        self.assertEqual(call("POST", "/quiz/board/join", b"[" * (board.MAX_BODY - 1))[0], 400)
        self.assertEqual(call("POST", "/quiz/board/join", b"x" * (board.MAX_BODY + 1))[0], 413)
        self.post("/quiz/board/join", {"t": T1, "n": "Gonod"})
        self.assertEqual(self.post("/quiz/board/join", {"t": T2, "n": "gonod"})[0], 409)

    def test_every_site_has_its_board(self):
        """Whatever the Host, the app answers for the board beside it: no site
        is named as the one that keeps it, and none refuses."""
        for n, host in enumerate(("ubsite.sigmaai.au", "ubsite.ddns.net", "localhost:8130", "192.168.1.9:8130")):
            token = f"{n + 1:032x}"
            st, _, j = self.post("/quiz/board/join", {"t": token, "n": f"Reader {n}", "a": RIGHT[:1]}, host=host)
            self.assertEqual((st, j["name"]), (200, f"Reader {n}"), host)
            self.assertEqual(self.post("/quiz/board/answers", {"t": token, "a": RIGHT[1:2]}, host=host)[0], 200, host)
            st, _, j = call("GET", "/quiz/board/lines", host=host)
            self.assertEqual((st, len(j["lines"])), (200, n + 1), host)
        for name in ("BOARD", "DEFAULT", "BOARD_HOST", "here", "origins"):
            self.assertFalse(hasattr(board, name), name)

    def test_a_token_from_another_board_is_unknown(self):
        """A browser on the board the other site kept holds a token this one
        has never had: 404, on which quiz.js offers again, and the join that
        follows takes every first answer it sends."""
        st, _, j = self.post("/quiz/board/answers", {"t": T1, "a": RIGHT[:2]})
        self.assertEqual((st, j), (404, {"error": "unknown"}))
        self.assertFalse(board._board.path.exists())                  # and nothing was made for it
        st, _, j = self.post("/quiz/board/join", {"t": T1, "n": "Ganid", "a": RIGHT})
        self.assertEqual((st, j["place"]), (200, 1))
        self.assertEqual(call("GET", "/quiz/board/lines")[2]["lines"][0]["right"], 6)

    def test_no_other_origin_is_answered(self):
        """No Access-Control header whatever the Origin, the other site's
        among them, and no OPTIONS: a browser then sends no JSON from another
        origin's page, and lets none read the lines."""
        for origin in ("https://ubsite.ddns.net", "https://ubsite.sigmaai.au", "https://example.com", "null", None):
            for path in ("/quiz/board/lines", "/quiz/board/join", "/quiz/board/answers"):
                st, h, _ = call("OPTIONS", path, origin=origin)
                self.assertEqual(st, 405, (origin, path))
                self.assertFalse([k for k in h if k.startswith("access-control-")], (origin, path))
            st, h, _ = call("GET", "/quiz/board/lines", origin=origin)
            self.assertEqual(st, 200)
            self.assertFalse([k for k in h if k.startswith("access-control-")], origin)
            self.assertNotIn("vary", h)
            st, h, _ = self.post("/quiz/board/join", {"t": T2, "n": "Nalda"}, origin=origin)
            self.assertEqual(st, 200)
            self.assertFalse([k for k in h if k.startswith("access-control-")], origin)

    def test_a_quiz_page_names_no_site(self):
        """The board is asked at the page's own origin (quiz.js), so the pages
        are the same on every host and in the one offline copy."""
        for host in ("ubsite.sigmaai.au", "ubsite.ddns.net"):
            st, h, body = call("GET", "/quiz/board", host=host)
            self.assertEqual(st, 200)
            self.assertEqual(h["x-robots-tag"], "noindex")
            for path in ("/quiz/board", "/quiz", "/quiz/32"):
                body = call("GET", path, host=host)[2]
                self.assertNotIn("data-board", body, path)
                self.assertNotIn("https://ubsite.", body.split("<main", 1)[1].split("</main>", 1)[0], path)
        js = (ROOT / "ubsite" / "static" / "quiz.js").read_text(encoding="utf-8")
        self.assertNotIn("dataset.board", js)
        self.assertNotIn("BOARD", js)
        self.assertEqual(js.count("fetch('/quiz/board/lines'"), 1)
        self.assertEqual(js.count("return fetch(path, {"), 1)


if __name__ == "__main__":
    unittest.main()
