"""The derived tables: the reverse map, density, entry stats, the concept graph.

This is where the index stops being a list and becomes navigable in the
direction print cannot express -- from a paragraph to everything that has been
said about it.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "vendor" / "index"))
import xref  # noqa: E402


def reverse_map(con) -> None:
    """paragraph -> citing entries, filed by citation precision.

    A paragraph-precision citation names this paragraph.  A section- or
    paper-precision one covers it without naming it, and the reader shows those
    once at the heading instead of repeating them under every paragraph.
    """
    con.execute("""
      INSERT OR IGNORE INTO para_citers (paragraph_id, entry_id, precision)
      SELECT t.paragraph_id, t.entry_id, 'para'
        FROM citation_target t
       WHERE t.precision = 'para' AND t.paragraph_id IS NOT NULL""")
    con.execute("""
      INSERT OR IGNORE INTO para_citers (paragraph_id, entry_id, precision)
      SELECT p.id, t.entry_id, 'sec'
        FROM citation_target t
        JOIN paragraph p ON p.paper_n = t.paper AND p.section_n = t.section
       WHERE t.precision = 'sec'""")
    con.execute("""
      INSERT OR IGNORE INTO para_citers (paragraph_id, entry_id, precision)
      SELECT p.id, t.entry_id, 'paper'
        FROM citation_target t
        JOIN paragraph p ON p.paper_n = t.paper
       WHERE t.precision = 'paper'""")


def density(con) -> None:
    con.execute("""
      INSERT INTO para_density
      SELECT p.id,
             COALESCE(SUM(c.precision = 'para'), 0),
             COALESCE(SUM(c.precision = 'sec'), 0),
             COALESCE(SUM(c.precision = 'paper'), 0),
             COUNT(c.entry_id),
             COALESCE(SUM(c.precision = 'para'), 0) = 0,
             COUNT(c.entry_id) = 0,
             100.0 * COALESCE(SUM(c.precision = 'para'), 0) / MAX(p.word_count, 1)
        FROM paragraph p
        LEFT JOIN para_citers c ON c.paragraph_id = p.id
       GROUP BY p.id""")


def entry_stats(con) -> None:
    con.execute("""
      INSERT INTO entry_stats
      SELECT e.id,
             (SELECT COUNT(*) FROM citation      WHERE entry_id = e.id),
             (SELECT COUNT(*) FROM citation_target WHERE entry_id = e.id),
             (SELECT COUNT(DISTINCT paragraph_id) FROM citation_target
               WHERE entry_id = e.id AND paragraph_id IS NOT NULL),
             (SELECT COUNT(DISTINCT paper) FROM citation_target WHERE entry_id = e.id),
             (SELECT COUNT(*) FROM index_entry d WHERE d.root_id = e.id AND d.id <> e.id)
        FROM index_entry e""")



# A headword citing fewer paragraphs than this has no reading path: two read
# as well from its concept page (Tigran, 2026-10-13).
PATH_MIN = 3


def reading_path(con) -> int:
    """reading_path: which headwords have one, and how long it is."""
    level2: dict[int, int] = {}        # entry -> its level-2 ancestor, or itself at level 1
    for i, parent, level in con.execute(
            "SELECT id, parent_id, level FROM index_entry WHERE scope = 'az' ORDER BY level"):
        level2[i] = i if level <= 2 else level2[parent]
    paras: dict[int, set[int]] = {}
    chapters: dict[int, set[int]] = {}
    for root, entry in con.execute(
            "SELECT DISTINCT e.root_id, e.id FROM citation_target t"
            " JOIN index_entry e ON e.id = t.entry_id WHERE e.scope = 'az'"):
        chapters.setdefault(root, set()).add(level2[entry])
    for root, pid in con.execute(
            "SELECT DISTINCT e.root_id, c.paragraph_id FROM para_citers c"
            " JOIN index_entry e ON e.id = c.entry_id"
            " WHERE e.scope = 'az' AND c.precision IN ('para', 'sec')"):
        paras.setdefault(root, set()).add(pid)
    words = dict(con.execute("SELECT id, word_count FROM paragraph"))
    rows = [(root, len(ps), sum(words[p] for p in ps), len(chapters[root]))
            for root, ps in sorted(paras.items()) if len(ps) >= PATH_MIN]
    con.executemany("INSERT INTO reading_path VALUES (?,?,?,?)", rows)
    return len(rows)


def anchors(con, report) -> None:
    """A fragment id for every entry, so that a link can land on a subentry.

    Subentries have no slug.  A position or a row id would shift silently when
    the index is edited, and a saved link would land on the wrong line.  A hash
    of the entry's path can only stop matching, and then an old link opens the
    headword at the top.  The path hashed is `path_fold`, citations and all:
    `path_plain` cannot serve, because it drops every parenthesis and so makes
    "Isaiah (first)" and "Isaiah (second)" the same string.  The same path twice
    under one headword takes -2, -3, as slugs take a numeric suffix; each such
    repeat is reported, because two identical subentries under one headword are
    usually one heading split in two.

    An appendix is one page, so its anchors are unique across the appendix
    rather than under a headword, and they hash what a row is, not what it
    cites: a B-F row its name, a Chronology event its date and its words.  An
    added citation then moves no link, and the three `conjunction of Jupiter and
    Saturn in Pisces' of 7 B.C. -- one text, three dates -- are three anchors.
    """
    con.execute("ALTER TABLE index_entry ADD COLUMN anchor TEXT")
    seen: dict[tuple, int] = {}
    rows = []
    for eid, scope, root, fold, name, year, month, where, line in con.execute(
            "SELECT e.id, e.scope, e.root_id, e.path_fold, e.path_plain,"
            "       v.year_label, v.month_label, e.source_file, e.source_line"
            "  FROM index_entry e LEFT JOIN chronology_event v ON v.entry_id = e.id"
            " ORDER BY e.root_id, e.ord").fetchall():
        if scope == "az":
            page, key = root, fold
        elif year is not None:
            page, key = scope, xref.fold(f"{year} {month or ''} {name}")
        else:
            page, key = scope, xref.fold(name)
        base = "e" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
        k = seen[(page, base)] = seen.get((page, base), 0) + 1
        if k > 1:
            report.warn("index-repeated-subentry", f"{where}:{line}", key)
        rows.append((base if k == 1 else f"{base}-{k}", eid))
    con.executemany("UPDATE index_entry SET anchor=? WHERE id=?", rows)


# One target naming several headwords, with what joins them kept, so that each
# part can be linked on its own and the text between them left as it was.
RE_CONJ_KEEP = re.compile(r"(\s+and\s+|\s*,\s*)")


def links(con, report) -> int:
    """Make a name a link wherever the index names a headword by it.

    Three places, all in `text_html`, and each wraps text already there, so the
    round trip still holds:

    * the name before a `q.v.` -- 1,026 of them, A-Z and appendix alike --
      linked to the headword it names, part by part when it names two
      ("6. & 7. Secrets of Greatness and Souls of Goodness q.v.");
    * an Appendix B-F row's own name, when it is an A-Z headword
      (`appendix_head`, via 'name');
    * the target of an Appendix B-F `See`.  An A-Z entry's See is not linked
      here, because its concept page lists its cross-references as links.

    Mirrors the routes of load._resolve, so the part linked is the part that
    resolved: "1. administrative assistants" links its words, not its number.
    """
    slug = dict(con.execute("SELECT id, slug FROM index_entry WHERE slug IS NOT NULL"))
    heads: dict[str, int] = {}
    for i, h in con.execute("SELECT id, headword FROM index_entry"
                            " WHERE scope='az' AND level=1 AND headword IS NOT NULL"
                            " ORDER BY id"):
        heads.setdefault(xref.fold(h), i)

    def a(text, href):
        return f'<a class="hw" href="{href}">{text}</a>'

    def named(name: str, target: str) -> str | None:
        for reading in xref.readings(target):
            if not name.endswith(reading):
                continue
            lead = name[:len(name) - len(reading)]
            h = heads.get(xref.fold(reading.split(":")[0]))
            if h is not None:
                return lead + a(reading, f"/i/{slug[h]}")
            bits = RE_CONJ_KEEP.split(reading)
            parts = bits[0::2]
            if len(parts) > 1 and all(xref.fold(p) in heads for p in parts):
                return lead + "".join(
                    a(b, f"/i/{slug[heads[xref.fold(b)]]}") if k % 2 == 0 else b
                    for k, b in enumerate(bits))
        members = xref.expand_range(target)
        if members and all(xref.fold(m) in heads for m in members):
            return a(name, f"/i/{slug[heads[xref.fold(members[0])]]}")
        return None

    html = {}
    for eid, h, where, line, target in con.execute(
            "SELECT e.id, e.text_html, e.source_file, e.source_line, x.target"
            "  FROM xref x JOIN index_entry e ON e.id = x.entry_id WHERE x.kind = 'qv'"):
        name, sep, tail = h.partition(" <i>q.v.</i>")
        linked = named(name, target) if sep and not tail.strip() else None
        if linked is None:
            report.hard("qv-unlinked", f"{where}:{line}", f"{h!r} names {target!r}")
            continue
        html[eid] = linked + sep + tail

    for eid, h, name, head, where, line in con.execute(
            "SELECT e.id, e.text_html, e.headword, a.head_entry_id,"
            "       e.source_file, e.source_line"
            "  FROM appendix_head a JOIN index_entry e ON e.id = a.entry_id"
            " WHERE a.via = 'name'"):
        if not h.startswith(name):
            report.hard("appendix-name-unlinked", f"{where}:{line}", f"{h!r} vs {name!r}")
            continue
        html[eid] = a(name, f"/i/{slug[head]}") + h[len(name):]

    for eid, h, kind, target, head, deep, dlevel, danchor, where, line in con.execute(
            "SELECT e.id, e.text_html, x.kind, x.target, x.head_entry_id,"
            "       x.deep_entry_id, d.level, d.anchor, e.source_file, e.source_line"
            "  FROM xref x JOIN index_entry e ON e.id = x.entry_id"
            "  LEFT JOIN index_entry d ON d.id = x.deep_entry_id"
            " WHERE e.scope <> 'az' AND x.kind IN ('see', 'seealso')"):
        h = html.get(eid, h)
        mark = "<i>See also</i> " if kind == "seealso" else "<i>See</i> "
        i = h.find(mark)
        j = h.find(target, i) if i >= 0 else -1
        if j < 0 or head is None:
            report.hard("appendix-see-unlinked", f"{where}:{line}", f"{h!r} -> {target!r}")
            continue
        href = f"/i/{slug[head]}" + (f"#{danchor}" if deep and dlevel > 1 else "")
        html[eid] = h[:j] + a(target, href) + h[j + len(target):]

    con.executemany("UPDATE index_entry SET text_html=? WHERE id=?",
                    [(h, i) for i, h in html.items()])
    return len(html)


def cocitation(con, floor: int = 2) -> int:
    """Concept adjacency: two headwords that cite the same paragraphs.

    Rolled up to level-1 roots and restricted to paragraph precision.  Both
    restrictions are load-bearing: at entry grain the pair count explodes, and a
    single `Paper 15` citation would otherwise make a clique of everything that
    cites Paper 15 -- 470 entries, 110,000 pairs, from one citation.
    """
    by_para: dict[int, set[int]] = {}
    for pid, root in con.execute("""
            SELECT t.paragraph_id, e.root_id
              FROM citation_target t
              JOIN index_entry e ON e.id = t.entry_id
             WHERE t.precision = 'para' AND t.paragraph_id IS NOT NULL
               AND e.scope = 'az'"""):
        by_para.setdefault(pid, set()).add(root)

    pair: dict[tuple[int, int], int] = {}
    size: dict[int, int] = {}
    for roots in by_para.values():
        for r in roots:
            size[r] = size.get(r, 0) + 1
        if len(roots) > 1:
            for a, b in itertools.combinations(sorted(roots), 2):
                pair[(a, b)] = pair.get((a, b), 0) + 1

    rows = [(a, b, n, n / (size[a] + size[b] - n))
            for (a, b), n in sorted(pair.items()) if n >= floor]
    con.executemany("INSERT INTO cocitation VALUES (?,?,?,?)", rows)
    return len(rows)


def fts(con) -> None:
    con.execute("INSERT INTO paragraph_fts(rowid, text) "
                "SELECT id, text FROM paragraph")
    con.execute("INSERT INTO paragraph_fts(paragraph_fts) VALUES('optimize')")
    con.execute("INSERT INTO index_entry_fts(rowid, text_expanded, path) "
                "SELECT id, text_expanded, path FROM index_entry")
    con.execute("INSERT INTO index_entry_fts(index_entry_fts) VALUES('optimize')")
    # The reasons are what the card shows (queries.section), whichever place in
    # it each stands; the verdict is left out, or "adopted" finds every note.
    con.execute("INSERT INTO footnote_fts(rowid, reading, reasons) "
                "SELECT f.id, f.text,"
                "  TRIM(COALESCE(s.why_text, '') || ' ' || COALESCE(t.why_text, ''))"
                " FROM footnote f LEFT JOIN srt_item s ON s.id = f.srt_item_id"
                " LEFT JOIN srt_item t ON t.id = s.see_id")
    con.execute("INSERT INTO footnote_fts(footnote_fts) VALUES('optimize')")
