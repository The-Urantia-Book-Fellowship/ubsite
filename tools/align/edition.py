"""The words a reading reads, where they are not today's.

Григорий Войнер recorded the translation between 2012 and 2014, as it then
stood; its repository has been corrected ever since, above all from May 2021,
and the site shows its HEAD.  1:1.4 was heard as "... известен по имени,
которое можно рассматривать как Первоисточник. Далее, в пространственных
вселенных ...", which is the repository's text until 2021 word for word and
not today's, of which the aligner found 56%.

No commit of the repository is the text he read.  Heard against every commit
that touched the text, the nearest is the refresh of April 2017 (94b54ca),
which brought in corrections made by 2014 that the commits of 2012 to 2014
lack ("В отличие от" at 100:5.7, where they have "Отличным от"); and here and
there he reads those first commits' words, which that refresh replaced: the
song of Zacharias at 122:9, in the Synodal Bible's ("По благоутробному
милосердию Бога нашего, которым посетил нас свыше").  His text lies between.

So a reading names the commits of its translation's repository that its text
lies between (the config's `edition`, the nearest first), and each paragraph
is matched to the text at whichever of them is nearer what was heard in it
(`read`): the cuts are then placed by the words actually said, and `match`
says how much of them was heard, as it does for a reading of the English,
where the text has hardly moved since.  What was heard in a paragraph is
known once it is cut, so the aligner cuts twice, first with every paragraph
as the first commit has it (tools/align/align.py); the cuts hardly depend on
which, 6 of 16,199 moving between one commit and the other, by a second at
most.  Which paragraphs' words have changed since the recording is another
question, answered here too (`report`), for whoever asks how often the voice
and the page differ.

A commit's paragraphs are found by their addresses, which are the
translation's own and have not changed since, except in 144:5, where the
separators have since lost their numbers.  So a section whose paragraphs at
the commit are, nearly all, like today's at the same addresses is taken
address by address, a paragraph rewritten altogether with the rest: it is
where his words are needed most.  A section where they are not (144:5) is
matched in order instead, each of today's paragraphs to the next one at the
commit that is like it; one with none like it is left to today's text, as is
one the commit lacks.

The repository is a master: read at the commit through build/readers/_io.py,
never its working tree, and never written.
"""

from __future__ import annotations

import difflib
import re

from tools.align import ru

RE_VS = re.compile(r"^\\vs p(\d{3}) (\d+):(\d+)\s?(.*)$", re.M)
RE_NOTE = re.compile(r"\\fnst\{(?:[^{}]|\{[^{}]*\})*\}")
RE_MACRO = re.compile(r"\\[A-Za-z]+\*?")
# At or above this likeness two paragraphs are one, reworded; a section with
# fewer than LINED_UP of its paragraphs so, address by address, was renumbered.
SAME, LINED_UP = 0.5, 0.8
AHEAD = 8                 # how far on a renumbered section's next paragraph is looked for


def plain(tex: str) -> str:
    """A paragraph of the translation's TeX as words: its notes out, each
    macro's name out and its argument kept ("\\ublistelem{1.}" is "1.")."""
    t = RE_NOTE.sub(" ", tex)
    t = t.replace("\\hyp{}", "-").replace("\\bibnobreakspace", " ")
    t = RE_MACRO.sub(" ", t)
    t = re.sub(r"\\.", " ", t)
    return re.sub(r"\s+", " ", t.replace("{", "").replace("}", "")).strip()


def at_commit(voice, commit: str) -> dict[str, str]:
    """{the translation's own address: its words} at a commit of its repository."""
    from build import config
    from build.readers import _io
    repo = config.load()[voice.translation]
    names = [f"p{n:03d}.tex" for n in range(197)]
    out = {}
    for name, tex in _io.read_tex_many(repo["tex"], names, commit).items():
        if tex is None:
            raise SystemExit(f"edition: {voice.translation} has no {name} at {commit}")
        for m in RE_VS.finditer(tex):
            out[f"{int(m[1])}:{m[2]}.{m[3]}"] = plain(m[4])
    return out


def likeness(a: str, b: str) -> float:
    x, y = ru.tokens(a), ru.tokens(b)
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() if x and y else 0.0


def paragraphs(voice, con, commit: str) -> tuple[dict[str, str], list[tuple[str, float]]]:
    """({our ref: its words at the commit}, [(our ref, likeness to today's)]),
    for the paragraphs the commit has in today's place.  The second lists
    every one whose words are not today's, by how like they still are."""
    old = at_commit(voice, commit)
    by_section: dict[str, list[str]] = {}            # the commit's addresses, in its order
    for addr in old:
        by_section.setdefault(addr.split(".")[0], []).append(addr)
    for addrs in by_section.values():
        addrs.sort(key=lambda a: int(a.split(".")[1]))
    sections: dict[tuple, list] = {}
    for ref, src, text, paper, sec in con.execute(
            "SELECT p.ref, COALESCE(t.src_ref, p.ref), t.text, p.paper_n, p.section_n FROM tr_paragraph t"
            " JOIN paragraph p ON p.id = t.paragraph_id WHERE t.translation = ? ORDER BY p.id",
            (voice.translation,)):
        sections.setdefault((paper, sec), []).append((ref, src, text))
    out, changed = {}, []

    def take(ref, was, text, like=None):
        out[ref] = was
        if ru.tokens(was) != ru.tokens(text):
            changed.append((ref, likeness(was, text) if like is None else like))

    for rows in sections.values():
        likes = [likeness(old[src], text) if old.get(src) else 0.0 for _ref, src, text in rows]
        if sum(1 for x in likes if x >= SAME) >= LINED_UP * len(rows):
            for (ref, src, text), like in zip(rows, likes):
                if old.get(src):
                    take(ref, old[src], text, like)
            continue
        # Renumbered since: today's paragraphs, in order, each to the next of
        # the commit's that is like it.  Every address the section's
        # paragraphs name, in any section of the commit's they point into.
        pool = []
        for sec in dict.fromkeys(src.split(".")[0] for _ref, src, _text in rows):
            pool += by_section.get(sec, [])
        j = 0
        for ref, _src, text in rows:
            for k in range(j, min(j + AHEAD, len(pool))):
                like = likeness(old[pool[k]], text)
                if like >= SAME:
                    take(ref, old[pool[k]], text, like)
                    j = k + 1
                    break
    return out, changed


def read(voice, con, heard: dict[str, list[str]] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """({our ref: the words read}, {our ref: the commit they are at}): each
    paragraph as the first of the reading's commits that has it has it, unless
    what was heard in it (`heard`, {ref: tokens}; tools/align/voice.py) is
    nearer its words at a later one.  With nothing heard, the first.

    A paragraph is weighed with the one before it in its section, as already
    chosen, and with what was heard in both: two commits may divide a sentence
    otherwise between two lines of verse, "Служить Ему, / В святости и правде"
    and "Дабы мы служили ему безбоязненно / Служить Ему в святости и правде"
    at 122:9.14-15, where each line weighed alone took the words "Служить Ему"
    for its own and they stood in the text twice, said once."""
    each = [(c, paragraphs(voice, con, c)[0]) for c in voice.src["edition"]]
    heard = heard or {}
    out, at = {}, {}
    before = None
    for (ref,) in con.execute("SELECT p.ref FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                              " WHERE t.translation = ? ORDER BY p.id", (voice.translation,)):
        has = [(c, got[ref]) for c, got in each if ref in got]
        if not has:
            before = None
            continue
        c, words = has[0]
        if heard.get(ref) and len(has) > 1:
            lead, led = [], []
            if before is not None and before.split(".")[0] == ref.split(".")[0]:
                lead, led = ru.tokens(out[before]), heard.get(before, [])
            best = _near(lead + ru.tokens(words), led + heard[ref])
            for c2, words2 in has[1:]:
                if ru.tokens(words2) != ru.tokens(words):
                    near = _near(lead + ru.tokens(words2), led + heard[ref])
                    if near > best + 1e-9:
                        c, words, best = c2, words2, near
        out[ref], at[ref] = words, c
        before = ref
    return out, at


def _near(words: list[str], heard: list[str]) -> float:
    return difflib.SequenceMatcher(None, words, heard, autojunk=False).ratio()


def report(voice, con) -> str:
    """How far today's text has moved from the text read, in a few lines."""
    got, at = read(voice, con, voice.heard())
    today = dict(con.execute("SELECT p.ref, t.text FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                             " WHERE t.translation = ?", (voice.translation,)))
    changed = [likeness(was, today[ref]) for ref, was in got.items() if ru.tokens(was) != ru.tokens(today[ref])]
    bands = [(0.95, 0), (0.8, 0), (0.5, 0), (0.0, 0)]
    for like in changed:
        for i, (lo, n) in enumerate(bands):
            if like >= lo:
                bands[i] = (lo, n + 1)
                break
    commits = voice.src["edition"]
    lines = [f"{voice.key} reads {voice.translation} as it stood at {' or '.join(commits)}:"
             f" {len(got):,} of {len(today):,} paragraphs found at their addresses,"
             f" {len(today) - len(got):,} left to today's text"]
    for c in commits:
        lines.append(f"  {sum(1 for x in at.values() if x == c):6,} as at {c}"
                     + ("" if c == commits[0] else ", nearer what was heard"))
    lines.append(f"  {len(got) - len(changed):,} word for word as today; {len(changed):,} reworded since:")
    upper = 1.0
    for lo, n in bands:
        lines.append(f"    {n:6,} between {lo:.2f} and {upper:.2f} alike")
        upper = lo
    return "\n".join(lines)


if __name__ == "__main__":
    import pathlib
    import sqlite3
    import sys
    from tools.align.voice import take
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    v, _rest = take(sys.argv[1:])
    if not v.src.get("edition"):
        raise SystemExit(f"{v.key} names no edition: it is matched to today's text")
    print(report(v, sqlite3.connect(f"file:{root / 'var' / 'ub.db'}?mode=ro", uri=True)))
