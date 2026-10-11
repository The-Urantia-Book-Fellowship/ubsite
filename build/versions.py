"""Text versions: what a site syncing with /api/v1/text holds, and what has changed since.

A consumer keeps the number of the version it last received.  Asked from 0, the
API sends the whole text; asked from 5, only the records that are new or
different after version 5, and the keys of any that have gone.  A record is a
part, a paper, a section or a paragraph, exactly as the API sends it, so a
version moves when anything a consumer receives changes -- a correction, an
italic, the red letter, how we render or number -- and only then.  Almost every
press commit is layout, and moves nothing.

ub.db is rebuilt from nothing and remembers no earlier build, so the history is
a ledger checked in under data/text/, append-only like data/slugs.tsv:

  versions.tsv   version  made_on  press_commit  changed  removed
  units.tsv      version  kind     key           hash      ('-' for a removal)

Version 1 lists every record.  Each later version lists only what it changed.
A version number that has reached a consumer must never be reused for other
content, so the ledger is only ever appended to, and only after a build has
passed (cli.py), and deploy.sh refuses to ship while it is uncommitted.

`hash` is the first 16 hex digits of the sha256 of the record's canonical JSON
without its hash: sorted keys, no spaces, UTF-8.  /api documents it, so that a
consumer can check its own copy.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import hashlib
import json
import pathlib

from .render import render

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "text"
KINDS = ("part", "paper", "section", "paragraph")


def canonical(rec: dict) -> str:
    return json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(rec: dict) -> str:
    return hashlib.sha256(canonical(rec).encode("utf-8")).hexdigest()[:16]


@dataclasses.dataclass(frozen=True)
class _Span:
    start: int
    end: int
    kind: str
    attr: object = None


def records(con) -> list[tuple[str, str, dict]]:
    """Every record the API serves, as (kind, key, record), each kind in reading order.

    The keys of each record are in the order a person reads them; the hash does
    not depend on it.
    """
    out = []
    for n, label, title, sponsor, lo, hi in con.execute(
            "SELECT n, label, title, sponsor, first_paper, last_paper FROM part ORDER BY n"):
        out.append(("part", str(n), {"part": n, "label": label, "title": title,
                                     "sponsor": sponsor, "papers": [lo, hi]}))
    for n, part, title, author in con.execute(
            "SELECT n, part_n, title, author FROM paper ORDER BY n"):
        out.append(("paper", str(n), {"paper": n, "part": part, "title": title,
                                      "author": author}))
    for p, n, uf, title, combined in con.execute(
            "SELECT s.paper_n, s.n, u.ref, s.title, s.combined_with FROM section s"
            " JOIN uf_section u ON u.section_id = s.id ORDER BY s.paper_n, s.n"):
        out.append(("section", f"{p}:{n}", {"ref": f"{p}:{n}", "uf_ref": uf, "paper": p,
                                            "section": n, "title": title,
                                            "combined_with": combined}))
    # A footnote marker points at a 1955 reading the API does not send, so the
    # paragraphs that have one are rendered again without it.  The rest are
    # already stored as render() made them: rendering all 14,586 took 5 s.
    spans = collections.defaultdict(list)
    for pid, start, end, kind in con.execute(
            "SELECT paragraph_id, start, \"end\", kind FROM span WHERE paragraph_id IN"
            " (SELECT paragraph_id FROM span WHERE kind = 'fnref') AND kind <> 'fnref'"
            " ORDER BY paragraph_id, ord"):
        spans[pid].append(_Span(start, end, kind))
    marked = {pid for (pid,) in con.execute(
        "SELECT DISTINCT paragraph_id FROM span WHERE kind = 'fnref'")}
    for pid, ref, uf, p, s, n, text, html in con.execute(
            "SELECT p.id, p.ref, u.ref, p.paper_n, p.section_n, p.para_n, p.text, p.html"
            " FROM paragraph p JOIN uf_paragraph u ON u.paragraph_id = p.id ORDER BY p.ord"):
        if pid in marked:
            html = render(text, spans.get(pid, []))
        # HTML alone, no plain copy beside it (Tigran, 2026-10-11): stripping its
        # tags gives the text exactly, which check_db holds, and one copy cannot
        # disagree with itself.
        out.append(("paragraph", ref, {"ref": ref, "uf_ref": uf, "paper": p, "section": s,
                                       "paragraph": n, "html": html}))
    return out


@dataclasses.dataclass
class Ledger:
    """data/text/ folded: the history, and each key's latest hash and when it was set."""
    versions: list[tuple[int, str, str, int, int]]
    latest: dict[tuple[str, str], tuple[str, int]]

    @property
    def n(self) -> int:
        return self.versions[-1][0] if self.versions else 0


def _rows(path: pathlib.Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def fold(ledger: pathlib.Path = LEDGER) -> Ledger:
    versions = [(int(v), made, press, int(c), int(r))
                for v, made, press, c, r in _rows(ledger / "versions.tsv")]
    if [v[0] for v in versions] != list(range(1, len(versions) + 1)):
        raise SystemExit(f"versions: {ledger}/versions.tsv is not numbered 1..N")
    latest: dict[tuple[str, str], tuple[str, int]] = {}
    last = 0
    for v, kind, key, h in _rows(ledger / "units.tsv"):
        v = int(v)
        if v < last or v > len(versions) or kind not in KINDS:
            raise SystemExit(f"versions: {ledger}/units.tsv: bad row {v} {kind} {key}")
        last = v
        latest[(kind, key)] = (h, v)
    return Ledger(versions, latest)


@dataclasses.dataclass
class Pending:
    """A new version, not yet written to the ledger: cli.py appends it after the build passes."""
    version: tuple[int, str, str, int, int]
    units: list[tuple[int, str, str, str]]
    ledger: pathlib.Path

    def append(self) -> None:
        self.ledger.mkdir(parents=True, exist_ok=True)
        new = not (self.ledger / "units.tsv").exists()
        with open(self.ledger / "units.tsv", "a", encoding="utf-8") as fh:
            if new:
                fh.write("# version\tkind\tkey\thash ('-': removed).  Append-only:"
                         " build/versions.py\n")
            fh.writelines(f"{v}\t{k}\t{key}\t{h}\n" for v, k, key, h in self.units)
        # Last, so that a units.tsv row can never name a version that does not exist.
        new = not (self.ledger / "versions.tsv").exists()
        with open(self.ledger / "versions.tsv", "a", encoding="utf-8") as fh:
            if new:
                fh.write("# version\tmade_on\tpress_commit\tchanged\tremoved."
                         "  Append-only: build/versions.py\n")
            fh.write("\t".join(map(str, self.version)) + "\n")


def diff(ledger: Ledger, current: dict[tuple[str, str], str]):
    """(changed keys, removed keys) of `current` against the ledger's latest state."""
    changed = [k for k, h in current.items()
               if k not in ledger.latest or ledger.latest[k][0] != h]
    removed = [k for k, (h, _) in ledger.latest.items() if h != "-" and k not in current]
    return changed, removed


@dataclasses.dataclass
class State:
    """Where the text stands after this build: every version, and per record when it last changed."""
    n: int
    versions: list[tuple[int, str, str, int, int]]
    since: dict[tuple[str, str], int]          # each current record: the version of its content
    gone: dict[tuple[str, str], int]           # each removed record: the version that removed it
    pending: Pending | None


def advance(ledger: Ledger, current: dict[tuple[str, str], str], press: dict,
            ledger_dir: pathlib.Path, today: str | None = None) -> State:
    """The state `current` puts the ledger in: a new version if anything differs."""
    changed, removed = diff(ledger, current)
    versions, pending = list(ledger.versions), None
    n = ledger.n
    since = {k: v for k, (h, v) in ledger.latest.items() if k in current}
    gone = {k: v for k, (h, v) in ledger.latest.items() if h == "-" and k not in current}
    if changed or removed:
        n += 1
        made = today or datetime.date.today().isoformat()
        commit = (press["commit"] or "?") + ("+dirty" if press["dirty"] else "")
        row = (n, made, commit, len(changed), len(removed))
        order = {k: i for i, k in enumerate(KINDS)}
        units = sorted([(n, k, key, current[(k, key)]) for k, key in changed]
                       + [(n, k, key, "-") for k, key in removed], key=lambda u: order[u[1]])
        pending = Pending(row, units, ledger_dir)
        versions.append(row)
        since.update({k: n for k in changed})
        gone.update({k: n for k in removed})
    return State(n, versions, since, gone, pending)


def assign(con, press: dict, ledger_dir: pathlib.Path = LEDGER,
           today: str | None = None) -> tuple[int, Pending | None]:
    """Fill text_version, text_unit and text_removed; return (version, what to append)."""
    recs = records(con)
    current = {(kind, key): digest(rec) for kind, key, rec in recs}
    st = advance(fold(ledger_dir), current, press, ledger_dir, today)
    con.executemany("INSERT INTO text_version VALUES (?,?,?,?,?)", st.versions)
    ords = collections.Counter()
    rows = []
    for kind, key, rec in recs:
        h = current[(kind, key)]
        body = json.dumps({**rec, "hash": h}, ensure_ascii=False, separators=(",", ":"))
        rows.append((kind, key, ords[kind], body, h, st.since[(kind, key)]))
        ords[kind] += 1
    con.executemany("INSERT INTO text_unit (kind, key, ord, body, hash, version)"
                    " VALUES (?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO text_removed VALUES (?,?,?)",
                    [(k, key, v) for (k, key), v in st.gone.items()])
    return st.n, st.pending
