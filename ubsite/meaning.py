"""Search by meaning: a question in a reader's own words, answered with
passages of the book.  No language model writes anything here: an embedding
model, bge-m3, turns a text into a vector, and texts that mean alike have
vectors that point alike (ARCHITECTURE.md, Search by meaning).

This module holds the one way a text becomes a vector, `Embedder`, which the
build uses for the book's units (tools/embed/build.py) and a host for a
reader's question: the same model files, the same code, so that a vector of
the one is comparable with a vector of the other.

The model is three files in var/embed/bge-m3/ (sources.toml [embed], placed
by tools/embed/fetch.py and shipped by deploy.sh), and its packages are
imported only when an Embedder is made: a host without the model, the tests'
in-process app and `make data` never load them.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = ROOT / "var" / "embed" / "bge-m3"
GRAPH = "onnx/model.onnx"                   # its weights beside it, onnx/model.onnx_data
TOKENIZER = "tokenizer.json"
DIM = 1024

# The longest text the model is given, in its tokens.  The book's longest
# paragraph is 699 (measured 2026-11-24) and the model reads 8,192; a text
# over this is refused, never cut: a vector of a text's first part would be
# filed under the whole.
MAX_TOKENS = 2048

# A sentence both a database's maker and its reader embed (embed_meta's
# `probe`): a host whose model file or runtime is not the maker's finds it
# out here, at once, and not in what a reader is shown.
PROBE = "The Universal Father is the God of all creation, the First Source and Center of all things and beings."


def there(model: pathlib.Path = MODEL) -> bool:
    """Whether this machine has the model."""
    return all((model / f).is_file() for f in (GRAPH, GRAPH + "_data", TOKENIZER))


class TooLong(ValueError):
    """A text of more than MAX_TOKENS tokens."""


def runtime():
    """onnxruntime, told first to report nothing.  The library's Linux wheel
    carries Microsoft's telemetry (1.32.0 does; found 2026-11-24, in the
    journal of the first host given it): unless ORT_DISABLE_TELEMETRY is in
    the environment as the library loads, every process that makes a session
    writes a device id and a queue of events under ~/.cache/Microsoft/ and
    tells mobile.events.data.microsoft.com what it runs on, the system, the
    processor, the program's name, and by the fields compiled in the model's
    file name and hashes and how long its runs took.  No text given to a
    model is among them; all the same a host of this site tells nobody what
    it runs.  `disable_telemetry_events()` after the import does not stop it:
    traced, the connection is made all the same.  This is the only import of
    the library (tests/test_meaning.py holds every one to it), for the
    server, the build and the retrieval test alike."""
    import os
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    import onnxruntime
    return onnxruntime


class Embedder:
    """bge-m3: texts to unit vectors of 1,024 float32, the CLS token of the
    last hidden state, L2-normalised, with no prefix, as the model is made to
    be used.

    `threads` is the runtime's own pool for one run; a host answers one
    question at a time in each worker (ubsite/app.py), and four threads is
    where an i7-3770 stops gaining (measured 2026-11-23).  `gpu` is the build's,
    on the 3090, and fails where the runtime would have fallen back to the CPU
    without a word.
    """

    def __init__(self, model: pathlib.Path = MODEL, threads: int = 4, gpu: bool = False):
        import numpy
        from tokenizers import Tokenizer

        onnxruntime = runtime()
        self.np = numpy
        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        if gpu:
            onnxruntime.preload_dlls()              # CUDA and cuDNN, from the venv's own nvidia packages
        self.session = onnxruntime.InferenceSession(
            str(model / GRAPH), opts, providers=["CUDAExecutionProvider" if gpu else "CPUExecutionProvider"])
        self.provider = self.session.get_providers()[0]
        if gpu and self.provider != "CUDAExecutionProvider":
            raise RuntimeError(f"the runtime gave {self.provider}, not the GPU")
        self.runtime = onnxruntime.__version__
        self.tokenizer = Tokenizer.from_file(str(model / TOKENIZER))
        # A batch is padded to its longest text; one text alone is not padded.
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"), pad_token="<pad>")

    def lengths(self, texts: list[str]) -> list[int]:
        """Each text's length in tokens, as the model will read it."""
        return [sum(e.attention_mask) for e in self.tokenizer.encode_batch(texts)]

    def encode(self, texts: list[str]):
        """One batch: an array of len(texts) rows, each a unit vector."""
        np = self.np
        encs = self.tokenizer.encode_batch(texts)
        if encs and len(encs[0].ids) > MAX_TOKENS:
            raise TooLong(f"a text of {len(encs[0].ids):,} tokens, where {MAX_TOKENS:,} is the most")
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        out = self.session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask})[0]
        v = out[:, 0, :].astype(np.float32)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        return v

    def one(self, text: str):
        """One text's vector."""
        return self.encode([text])[0]


# ---- the units in memory, and one search ------------------------------------

DB = ROOT / "var" / "embed.db"
UB = ROOT / "var" / "ub.db"

RRF = 60              # reciprocal rank fusion's constant: a list's nth is worth 1 / (RRF + n)
NEAR = 50             # units of a kind taken from the matrix for one question
ENTRIES = 30          # entries of the index whose citations are followed
CITED = 100           # paragraphs taken through the index, at the most
WORDS = 50            # paragraphs taken by words


class Mismatch(RuntimeError):
    """var/embed.db is not of the var/ub.db beside it: a unit names a
    paragraph the book has not, or an entry's id is another entry's now."""


def _ro(path: pathlib.Path):
    import sqlite3
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class Units:
    """var/embed.db read into memory: the matrix, a row to a unit, and what
    each row leads to in the book, found once, here, in the ub.db beside it."""

    def __init__(self, db: pathlib.Path = DB, ub: pathlib.Path = UB):
        import numpy as np
        self.np = np
        self.stamp = db.stat().st_mtime_ns
        con = _ro(db)
        self.meta = dict(con.execute("SELECT key, value FROM embed_meta"))
        rows = con.execute("SELECT kind, label, target FROM unit ORDER BY id").fetchall()
        blob = b"".join(v for (v,) in con.execute("SELECT v FROM unit ORDER BY id"))
        con.close()
        self.m = np.frombuffer(blob, dtype="<f4").reshape(len(rows), DIM)
        # A kind's units stand together (build/embed.py): its rows are a slice.
        self.at: dict[str, tuple[int, int]] = {}
        for i, (kind, _, _) in enumerate(rows):
            a, _z = self.at.get(kind, (i, i))
            if i != _z:
                raise Mismatch(f"the units of kind {kind} do not stand together")
            self.at[kind] = (a, i + 1)
        u = _ro(ub)
        # A paragraph: its id, and where it stands, for joining neighbours.
        self.para = {}                                 # id -> (ref, section_id, para_n, ord)
        ids = {}
        for pid, ref, sec, n, o in u.execute("SELECT id, ref, section_id, para_n, ord FROM paragraph"):
            self.para[pid] = (ref, sec, n, o)
            ids[ref] = pid
        u.close()

        def of(ref: str) -> int:
            if ref not in ids:
                raise Mismatch(f"a unit names {ref}, which the book has not")
            return ids[ref]

        self.leads: list = [None] * len(rows)          # row -> what it leads to
        self.label = [label for _, label, _ in rows]
        self.row = {}                                  # a paragraph's id -> its own unit's row
        for i, (kind, label, target) in enumerate(rows):
            if kind == "para":
                self.leads[i] = (of(label),)
                self.row[self.leads[i][0]] = i
            elif kind == "note":
                self.leads[i] = (of(target),)
            elif kind == "entry":
                self.leads[i] = int(target)

    def nearest(self, scores, kind: str, n: int) -> list[int]:
        """The n rows of a kind that score highest, best first."""
        np = self.np
        a, z = self.at.get(kind, (0, 0))
        part = scores[a:z]
        if not len(part):
            return []
        n = min(n, len(part))
        top = np.argpartition(-part, n - 1)[:n]
        return [int(a + i) for i in top[np.argsort(-part[top])]]


def language(q: str) -> str:
    """ru for a question with a Cyrillic letter, en for one in Latin letters,
    else none: which text a question's words are looked for in."""
    if any("Ѐ" <= c <= "ӿ" for c in q):
        return "ru"
    return "en" if any(c.isascii() and c.isalpha() for c in q) else ""


def match(q: str, stems: bool = True) -> str | None:
    """A question as an FTS5 query: any of its words, each quoted, as the
    ordinary search quotes them (app.py fts_query), so that it cannot fail to
    parse; and with `stems`, a longer word also by its beginning, since the
    tokenizer knows no word's other forms ("worship", "worshiped"; «молитва»,
    «молитвы»).  bm25 weighs a word by how rare it is, so "what" and "the"
    cost nothing and no list of them is kept."""
    import re
    seen, terms = set(), []
    for w in re.findall(r"\w+", q.replace("ё", "е").replace("Ё", "Е").casefold()):
        if len(w) < 2 or w in seen:
            continue
        seen.add(w)
        terms.append(f'"{w}"')
        if stems and len(w) >= 6 and w.isalpha():
            terms.append(f'"{w[:-2]}"*')
    return " OR ".join(terms) or None


def by_words(ub, q: str, lang: str, n: int = WORDS, stems: bool = True) -> list[int]:
    """Paragraphs by the question's words, the likeliest first (bm25): the
    book's own text for a question in English, the translations' for one in
    Russian, each paragraph once, at its best translation's place."""
    m = match(q, stems)
    if not m or lang not in ("en", "ru"):
        return []
    if lang == "en":
        return [r[0] for r in ub.execute(
            "SELECT rowid FROM paragraph_fts WHERE paragraph_fts MATCH ? ORDER BY rank LIMIT ?", (m, n))]
    out, seen = [], set()
    for (pid,) in ub.execute(
            "SELECT t.paragraph_id FROM tr_paragraph_fts f JOIN tr_paragraph t ON t.id = f.rowid"
            " WHERE tr_paragraph_fts MATCH ? ORDER BY f.rank LIMIT ?", (m, n * 4)):
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out[:n]


def routes(units: Units, ub, v, q: str, stems: bool = True) -> dict:
    """What one question finds, route by route, each a list of paragraph ids,
    the likeliest first, none twice:

      para    paragraphs nearest in meaning
      note    the paragraphs of the nearest study notes
      index   the paragraphs the nearest index entries cite, entry by entry,
              an entry's own in the order of their nearness; with `via`, the
              entries that brought each
      words   by the question's words (by_words)

    and `entries`, the rows of the nearest index entries, and `kjv`, the rows
    of the nearest passages of the King James Version, both for showing.
    """
    scores = units.m @ v

    def own(pid: int) -> float:
        """A paragraph's own nearness to the question."""
        return -float(scores[units.row[pid]]) if pid in units.row else 0.0

    def spread(rows: list[int]) -> list[int]:
        out, seen = [], set()
        for r in rows:
            for pid in sorted(units.leads[r], key=own):
                if pid not in seen:
                    seen.add(pid)
                    out.append(pid)
        return out

    found = {
        "para": spread(units.nearest(scores, "para", NEAR)),
        "note": spread(units.nearest(scores, "note", 10)),
        "words": by_words(ub, q, language(q), stems=stems),
    }
    erows = units.nearest(scores, "entry", ENTRIES)
    eids = [units.leads[r] for r in erows]
    paths = dict(ub.execute(
        f"SELECT id, path_plain FROM index_entry WHERE id IN ({','.join('?' * len(eids))})", eids))
    for r, e in zip(erows, eids):
        if paths.get(e) != units.label[r]:
            raise Mismatch(f"index entry {e} is {paths.get(e)!r} in the book's database, "
                           f"{units.label[r]!r} in the vectors'")
    cites: dict[int, list[int]] = {}
    for e, pid in ub.execute(
            f"SELECT entry_id, paragraph_id FROM citation_target WHERE paragraph_id IS NOT NULL"
            f" AND entry_id IN ({','.join('?' * len(eids))})", eids):
        cites.setdefault(e, []).append(pid)
    index, via = [], {}
    for r, e in zip(erows, eids):
        for pid in sorted(set(cites.get(e, ())), key=own):
            via.setdefault(pid, []).append(r)
            if len(via[pid]) == 1:
                index.append(pid)
    found["index"] = index[:CITED]
    return {"found": found, "via": via, "entries": erows, "kjv": units.nearest(scores, "kjv", 10),
            "scores": scores}


# What each route's place is worth in the fusion: set by the retrieval test
# (tools/embed/bench.py, var/embed/bench.md), never by hand.  The index at
# half: at one it is right in the first ten a little more often, and first of
# all less often, its paragraphs coming an entry at a time.  The study notes'
# paragraphs are not fused: a note is shown as a note, in a list of its own.
WEIGHTS = {"para": 1.0, "index": 0.5, "words": 1.0}


def fuse(found: dict[str, list[int]], weights: dict[str, float] = WEIGHTS, k: int = RRF) -> list[tuple[int, float]]:
    """The routes' lists as one, by reciprocal rank: a paragraph's worth is
    the sum, over the routes that found it, of weight / (k + its place)."""
    worth: dict[int, float] = {}
    for route, pids in found.items():
        w = weights.get(route, 0.0)
        if w:
            for place, pid in enumerate(pids, 1):
                worth[pid] = worth.get(pid, 0.0) + w / (k + place)
    return sorted(worth.items(), key=lambda x: -x[1])


# ---- a worker's engine, and one question answered -----------------------------

import threading
import unicodedata

QUESTION = 300        # characters: the longest question taken
WAITING = 4           # questions that may wait for the model in one worker; more are turned away
PASSAGES = 20         # passages in an answer: the fusion's paragraphs, in order, neighbours joined, until the 21st would begin
SHOWN = {"entries": 6, "notes": 3, "kjv": 5}
# A study note is listed where it is about as near the question as the nearest
# paragraph: there are few notes, and the nearest of them is often not near.
NOTE_NEAR = 0.05


class Refused(Exception):
    """A question not answered: the status to send, and why, in a word the
    page has a sentence for (static/meaning.js)."""

    def __init__(self, status: int, why: str):
        super().__init__(why)
        self.status, self.why = status, why


class Engine:
    """What a worker needs to answer: the model and the units, loaded once.
    The model is asked for the probe as it loads, and must answer as the
    database's maker did."""

    def __init__(self):
        self.embedder = Embedder()
        self.units = Units()
        probe = self.units.meta.get("probe_v")
        np = self.embedder.np
        if not probe or self.units.meta.get("probe") != PROBE:
            raise Mismatch("var/embed.db has no probe, or another's")
        alike = float(self.embedder.one(PROBE) @ np.frombuffer(probe, dtype="<f4"))
        if alike < 0.9999:
            raise Mismatch(f"this model's vector of the probe and the database's are {alike:.6f} alike")
        self.gate = threading.Semaphore(1)
        self.count = threading.Lock()
        self.waiting = 0

    def fresh(self) -> Units:
        """The units, read again where var/embed.db has been replaced under a
        running server (`make embed` beside the dev server)."""
        if DB.stat().st_mtime_ns != self.units.stamp:
            self.units = Units()
        return self.units

    def vector(self, q: str):
        """A question's vector: one at a time, the runtime's threads being the
        machine's, and no long line behind it."""
        with self.count:
            if self.waiting >= WAITING:
                raise Refused(503, "busy")
            self.waiting += 1
        try:
            with self.gate:
                return self.embedder.one(q)
        except TooLong:
            raise Refused(400, "long") from None
        finally:
            with self.count:
                self.waiting -= 1


_engine: Engine | None = None
_state: bool | None = None          # None: this machine has no model; False: it failed to load, or has not yet
_loading = threading.Lock()


def here() -> bool:
    """Whether this machine is to answer: it has the model and the vectors,
    and UB_MEANING is not "off" (the tests' and the e2e servers')."""
    import os
    return os.environ.get("UB_MEANING") != "off" and there() and DB.is_file()


def load() -> None:
    """Load the engine, once; a failure is said once, in the journal, and the
    feature is off until the worker starts again."""
    global _engine, _state
    with _loading:
        if _engine is not None or _state is False and not here():
            return
        if not here():
            _state = None
            return
        _state = False
        try:
            _engine = Engine()
            _state = True
        except Exception as exc:                       # noqa: BLE001
            import sys
            print(f"Search by meaning is off: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def start() -> None:
    """As a worker starts: the model loaded behind it, so that the first
    question does not wait for it, and the worker's start does not."""
    if here():
        threading.Thread(target=load, name="meaning-load", daemon=True).start()


def status() -> bool | None:
    """True: answering.  False: this machine has the model, and it is not
    loaded, yet or at all.  None: it has none."""
    return _state is True if here() else None


def engine() -> Engine:
    if _engine is None:
        if not here():
            raise Refused(503, "none")
        load()                                         # a question before the start's own load is done waits for it
        if _engine is None:
            raise Refused(503, "none")
    return _engine


def question(q: object) -> str:
    """A question as it is put to the model: NFC, its white space single."""
    if not isinstance(q, str):
        raise Refused(400, "json")
    q = " ".join(unicodedata.normalize("NFC", q).split())
    if not q:
        raise Refused(400, "empty")
    if len(q) > QUESTION:
        raise Refused(400, "long")
    return q


def search(q: str, ub) -> dict:
    """One question answered, as ids for the page to draw (app.py):

      lang      ru, en or nothing: the language its words were looked for in
      runs      the passages, the likeliest first: each a list of paragraph
                ids running on in one section, in the book's order
      why       paragraph id -> the routes that found it, of "meaning",
                "words" and "index"
      via       paragraph id -> the index entries' ids that brought it
      entries   index entries' ids, the nearest first
      notes     study notes' keys, where any is near enough
      kjv       labels of the King James Version's passages, the nearest first
    """
    eng = engine()
    units = eng.fresh()
    r = routes(units, ub, eng.vector(q), q)
    found, scores = r["found"], r["scores"]
    para = units.para

    def joined(pids) -> list[list[int]]:
        """Paragraphs as passages: those running on in a section together."""
        by_sec: dict[int, list[int]] = {}
        for pid in pids:
            by_sec.setdefault(para[pid][1], []).append(pid)
        out: list[list[int]] = []
        for ps in by_sec.values():
            ps.sort(key=lambda p: para[p][2])
            for i, pid in enumerate(ps):
                if i and para[ps[i - 1]][2] + 1 == para[pid][2]:
                    out[-1].append(pid)
                else:
                    out.append([pid])
        return out

    # The fusion's paragraphs in their order, until one would begin a passage
    # more than PASSAGES: an answer is so many passages, each a paragraph or
    # several running on, and says so in its heading.
    worth: dict[int, float] = {}
    for pid, w in fuse(found):
        if len(joined([*worth, pid])) > PASSAGES:
            break
        worth[pid] = w
    runs = joined(worth)
    runs.sort(key=lambda run: -max(worth[p] for p in run))
    names = {"para": "meaning", "words": "words", "index": "index"}
    why = {pid: [names[k] for k in ("para", "words", "index") if pid in found[k]] for pid in worth}
    via = {pid: [units.leads[row] for row in r["via"].get(pid, ())][:3] for pid in worth if pid in found["index"]}
    entries, seen = [], set()
    for row in r["entries"]:
        if units.label[row] not in seen:
            seen.add(units.label[row])
            entries.append(units.leads[row])
    best = float(scores[units.row[found["para"][0]]]) if found["para"] else 1.0
    notes = [units.label[row] for row in units.nearest(scores, "note", SHOWN["notes"])
             if float(scores[row]) >= best - NOTE_NEAR]
    kjv, taken = [], []
    for row in r["kjv"]:
        book, _, where = units.label[row].partition(" ")
        chapter, _, verses = where.partition(":")
        a, _, z = verses.partition("-")
        span = (book, chapter, int(a), int(z or a))
        if not any(t[:2] == span[:2] and t[2] <= span[3] and span[2] <= t[3] for t in taken):
            taken.append(span)
            kjv.append(span)
    return {"lang": language(q), "runs": runs, "why": why, "via": via,
            "entries": entries[:SHOWN["entries"]], "notes": notes, "kjv": kjv[:SHOWN["kjv"]]}
