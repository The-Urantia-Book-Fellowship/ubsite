"""The derived tables: the reverse map, density, entry stats, the concept graph.

This is where the index stops being a list and becomes navigable in the
direction print cannot express -- from a paragraph to everything that has been
said about it.
"""

from __future__ import annotations

import hashlib
import itertools
import math


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
    """
    con.execute("ALTER TABLE index_entry ADD COLUMN anchor TEXT")
    seen: dict[tuple[int, str], int] = {}
    rows = []
    for eid, root, fold, where, line in con.execute(
            "SELECT id, root_id, path_fold, source_file, source_line"
            "  FROM index_entry ORDER BY root_id, ord").fetchall():
        base = "e" + hashlib.sha1(fold.encode("utf-8")).hexdigest()[:8]
        k = seen[(root, base)] = seen.get((root, base), 0) + 1
        if k > 1:
            report.warn("index-repeated-subentry", f"{where}:{line}", fold)
        rows.append((base if k == 1 else f"{base}-{k}", eid))
    con.executemany("UPDATE index_entry SET anchor=? WHERE id=?", rows)


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
