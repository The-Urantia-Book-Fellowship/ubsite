"""The quiz's board: the first thing the site accepts from a reader.

Opt-in, and no login (Tigran, 2026-10-28).  After a quiz a reader may put any
name they choose on it; their browser then sends the first answer it gave each
question (static/quiz.js, `first` in ub_quiz), and after each later quiz the
answers it has not sent.  The server marks them itself, against the right
answers in ub.db (build/quiz.py): a score cannot be typed in, though a program
that sends the right answers can still be written, which is accepted.  The
board ranks by the questions a reader had right the first time they met them,
which retaking a quiz cannot raise; a tie goes to whoever reached the count
first.  Beside it, how many questions were answered, and on how many papers
every question was.

A line is the browser's: a random token, 128 bits it made itself, which the
server keeps as its SHA-256 and which never goes in an address.  A name may be
taken once, letters, digits, spaces and . - ' only, 1 to 32 of them, compared
as NFKC case-folded; one that should not be there is hidden from the host's
command line (`python -m ubsite.board`), its line and its name kept.  Kept:
the name, the token's hash, the answers, the server's times.  No IP address,
no cookie, nothing about the device, and nothing joined to var/visits.db.

One board, on the main site (UB_BOARD, ubsite.sigmaai.au), which the other
sites' pages send to and read from across origins; anywhere else these routes
answer 404, and var/quiz.db is never made.  deploy.sh never ships it, and
brings a copy back on each deploy.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys
import threading
import time
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = pathlib.Path(os.environ.get("UB_BOARD_DB", ROOT / "var" / "quiz.db"))
UB_DB = ROOT / "var" / "ub.db"
# The site that keeps the board, which every quiz page names: the same bytes on
# every host and in the one offline copy (offline/pages.py holds it so).
DEFAULT = "https://ubsite.sigmaai.au"
BOARD = os.environ.get("UB_BOARD", DEFAULT).rstrip("/")
MAX_BODY = 16 * 1024
MAX_ANSWERS = 2000
CACHE_S = 10

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS line (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  fold TEXT NOT NULL UNIQUE,         -- the name compared: NFKC, case-folded
  token TEXT NOT NULL UNIQUE,        -- SHA-256 of the browser's token, hex
  joined TEXT NOT NULL,              -- the server's time, UTC
  hidden INTEGER NOT NULL DEFAULT 0  -- taken off the board by hand; its name stays taken
);
CREATE TABLE IF NOT EXISTS answer (
  line_id INTEGER NOT NULL REFERENCES line(id),
  question INTEGER NOT NULL,         -- quiz_question.id, for ever
  v INTEGER NOT NULL,                -- the layout of its answers it was given under
  mask INTEGER NOT NULL,             -- the answers chosen, bit n for answer n
  at TEXT NOT NULL,                  -- when the server first had it, UTC
  PRIMARY KEY (line_id, question, v)
);
"""
RE_TOKEN = re.compile(r"[0-9a-f]{32}")
RE_NAME = re.compile(r"[^\W_]+(?:[ .'’-]+[^\W_]+)*[.]?")


class Refused(Exception):
    """What a request asks that the board will not do: status, and why."""

    def __init__(self, status: int, why: str):
        super().__init__(why)
        self.status, self.why = status, why


def name_of(raw) -> tuple[str, str]:
    """(the name as shown, the name as compared), or Refused."""
    if not isinstance(raw, str):
        raise Refused(400, "name")
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not 1 <= len(name) <= 32 or not RE_NAME.fullmatch(name):
        raise Refused(400, "name")
    return name, unicodedata.normalize("NFKC", name.casefold())


def token_of(raw) -> str:
    if not isinstance(raw, str) or not RE_TOKEN.fullmatch(raw):
        raise Refused(400, "token")
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def answers_of(raw) -> list[tuple[int, int, int]]:
    if not isinstance(raw, list) or len(raw) > MAX_ANSWERS:
        raise Refused(400, "answers")
    out = []
    for a in raw:
        if (not isinstance(a, list) or len(a) != 3 or not all(type(x) is int for x in a)
                or not (0 < a[0] < 100000 and 0 < a[1] < 1000 and 0 < a[2] < 512)):
            raise Refused(400, "answers")
        out.append(tuple(a))
    return out


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Board:
    def __init__(self, path: pathlib.Path = DB, ub: pathlib.Path = UB_DB):
        self.path, self.ub = pathlib.Path(path), pathlib.Path(ub)
        self._cache: tuple[float, dict] | None = None
        self._lock = threading.Lock()

    def _con(self, write: bool) -> sqlite3.Connection | None:
        """A connection, with ub.db beside it; None if nothing was ever written
        and this is only a read.  The file is made by the first accepted write."""
        if not write and not self.path.exists():
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(f"file:{self.path}", uri=True, timeout=5, isolation_level=None)
        con.executescript(SCHEMA)
        con.execute("ATTACH DATABASE ? AS ub", (f"file:{self.ub}?mode=ro",))
        return con

    def _known(self, con, answers) -> list[tuple[int, int, int]]:
        """The answers to questions the quiz has, at any layout."""
        ids = {q for (q,) in con.execute("SELECT id FROM ub.quiz_question")}
        return [a for a in answers if a[0] in ids]

    def join(self, token: str, name: str, answers: list) -> dict:
        """A line for this browser, under `name`, with its answers; or, for a
        browser already on the board, its name changed and its answers added."""
        t, (shown, fold) = token_of(token), name_of(name)
        got = answers_of(answers)
        con = self._con(True)
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT id FROM line WHERE token = ?", (t,)).fetchone()
            other = con.execute("SELECT token FROM line WHERE fold = ?", (fold,)).fetchone()
            if other and other[0] != t:
                con.execute("ROLLBACK")
                raise Refused(409, "taken")
            if row:
                line = row[0]
                con.execute("UPDATE line SET name = ?, fold = ? WHERE id = ?", (shown, fold, line))
            else:
                line = con.execute("INSERT INTO line (name, fold, token, joined) VALUES (?,?,?,?)",
                                   (shown, fold, t, now())).lastrowid
            self._add(con, line, got)
            con.execute("COMMIT")
        except sqlite3.IntegrityError:
            con.execute("ROLLBACK")
            raise Refused(409, "taken")
        finally:
            con.close()
        self._cache = None
        return self.place(line, shown)

    def add(self, token: str, answers: list) -> dict:
        """The answers a browser on the board has not sent before."""
        t, got = token_of(token), answers_of(answers)
        con = self._con(False)
        if con is None:
            raise Refused(404, "unknown")
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT id, name FROM line WHERE token = ?", (t,)).fetchone()
            if row is None:
                con.execute("ROLLBACK")
                raise Refused(404, "unknown")
            self._add(con, row[0], got)
            con.execute("COMMIT")
        finally:
            con.close()
        self._cache = None
        return self.place(row[0], row[1])

    def _add(self, con, line: int, answers) -> None:
        # The first a browser sends for a question wins, here as in the browser.
        con.executemany("INSERT OR IGNORE INTO answer VALUES (?,?,?,?,?)",
                        [(line, q, v, m, now()) for q, v, m in self._known(con, answers)])

    def lines(self) -> dict:
        """The board, ranked: each line's id, name, right, answered and papers."""
        with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < CACHE_S:
                return self._cache[1]
        con = self._con(False)
        out: dict = {"lines": []}
        if con is not None:
            try:
                rows = con.execute(
                    "SELECT l.id, l.name, l.joined,"
                    " SUM(q.id IS NOT NULL) AS answered,"
                    " SUM(q.id IS NOT NULL AND a.mask = q.mask) AS right,"
                    " MAX(CASE WHEN a.mask = q.mask THEN a.at END) AS reached"
                    " FROM line l LEFT JOIN answer a ON a.line_id = l.id"
                    " LEFT JOIN ub.quiz_question q ON q.id = a.question AND q.v = a.v AND q.state <> 'drop'"
                    " WHERE NOT l.hidden GROUP BY l.id").fetchall()
                whole = {p: n for p, n in con.execute("SELECT paper_n, n FROM ub.quiz_paper")}
                done: dict[int, int] = {}
                for line, paper, n in con.execute(
                        "SELECT a.line_id, q.paper_n, COUNT(*) FROM answer a JOIN ub.quiz_question q"
                        " ON q.id = a.question AND q.v = a.v AND q.state <> 'drop' GROUP BY a.line_id, q.paper_n"):
                    if whole.get(paper) == n:
                        done[line] = done.get(line, 0) + 1
            finally:
                con.close()
            rows.sort(key=lambda r: (-(r[4] or 0), r[5] or "~", r[2]))
            out["lines"] = [{"id": r[0], "name": r[1], "right": r[4] or 0, "answered": r[3] or 0,
                             "papers": done.get(r[0], 0)} for r in rows]
        with self._lock:
            self._cache = (time.monotonic(), out)
        return out

    def place(self, line: int, name: str) -> dict:
        ls = self.lines()["lines"]
        at = next((i for i, x in enumerate(ls) if x["id"] == line), None)
        return {"line": line, "name": name, "place": None if at is None else at + 1, "of": len(ls)}

    def hide(self, name: str, hidden: bool = True) -> bool:
        con = self._con(False)
        if con is None:
            return False
        try:
            n = con.execute("UPDATE line SET hidden = ? WHERE fold = ?",
                            (int(hidden), name_of(name)[1])).rowcount
        finally:
            con.close()
        self._cache = None
        return n == 1

    def rename(self, old: str, new: str) -> bool:
        shown, fold = name_of(new)
        con = self._con(False)
        if con is None:
            return False
        try:
            n = con.execute("UPDATE line SET name = ?, fold = ? WHERE fold = ?",
                            (shown, fold, name_of(old)[1])).rowcount
        finally:
            con.close()
        self._cache = None
        return n == 1


BOARD_HOST = urllib.parse.urlsplit(BOARD).netloc


def here(host: str | None) -> bool:
    """Whether this request is to the site that keeps the board: its Host, as
    nginx passes it on (proxy_params), port and all, so that two servers on
    one machine are two sites."""
    return host is not None and host == BOARD_HOST


def origins(sites) -> set[str]:
    """The other sites whose pages may send to the board: every site the app
    serves, as https, and those UB_BOARD_ORIGINS adds, for a test."""
    out = {f"https://{h}" for h in sites}
    out |= {o.strip().rstrip("/") for o in os.environ.get("UB_BOARD_ORIGINS", "").split(",") if o.strip()}
    out.discard(BOARD)
    return out


_board: Board | None = None


def board() -> Board:
    global _board
    if _board is None:
        _board = Board()
    return _board


def main(argv: list[str]) -> int:
    """python -m ubsite.board list | hide NAME | show NAME | rename OLD NEW"""
    b = Board()
    try:
        if argv == ["list"]:
            con = b._con(False)
            if con is None:
                print("no board here: var/quiz.db has never been written")
                return 0
            for i, name, joined, hidden, n in con.execute(
                    "SELECT l.id, l.name, l.joined, l.hidden, COUNT(a.question) FROM line l"
                    " LEFT JOIN answer a ON a.line_id = l.id GROUP BY l.id ORDER BY l.id"):
                print(f"{i:5}  {joined}  {n:4} answers  {'HIDDEN  ' if hidden else ''}{name}")
            return 0
        if len(argv) == 2 and argv[0] in ("hide", "show"):
            ok = b.hide(argv[1], argv[0] == "hide")
            print("done" if ok else f"no line named {argv[1]!r}")
            return 0 if ok else 1
        if len(argv) == 3 and argv[0] == "rename":
            ok = b.rename(argv[1], argv[2])
            print("done" if ok else f"no line named {argv[1]!r}, or {argv[2]!r} is taken")
            return 0 if ok else 1
    except (Refused, sqlite3.IntegrityError) as e:
        print(f"refused: {e}")
        return 1
    print(main.__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
