"""The chart of the personalities, as the database holds it (build/cosmo.py).

The build holds the snapshot to the book as it loads it, so a database that
exists passed those gates.  This looks at what was stored, each count of
which must be 0: that it is the snapshot whole, and that everything in it
joins up, a card to its unit, a line to its two ends, a reference to its
section, a headword to the index.  And it reports, since his chart is days old
and moving: its size, the commit of his it was made at and whether his
repository has moved on since, and what has no headword in the index.
"""

from __future__ import annotations

import sqlite3

from .. import config
from ..readers import cosmo as reader


def run(db) -> int:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    src = config.cosmology()
    meta = dict(con.execute("SELECT key, value FROM cosmo_meta"))
    if not meta:
        print("  no chart in the database" + (": and the snapshot is there, so the build read none of it"
                                               if src["snapshot"].is_file() else ""))
        return 1 if src["snapshot"].is_file() else 0
    doc = reader.read(src["snapshot"])
    one = lambda q, *a: con.execute(q, a).fetchone()[0]
    n = {k: one(f"SELECT COUNT(*) FROM {t}") for k, t in
         (("persons", "cosmo_person"), ("units", "cosmo_unit"), ("places", "cosmo_place"), ("links", "cosmo_link"))}
    print(f"  {n['persons']} personalities in {n['units']} units, {n['places'] - n['persons']} of them drawn again"
          f" where they serve; {n['links']} lines ("
          + ", ".join(f"{c} of {t}" for t, c in con.execute("SELECT type, COUNT(*) FROM cosmo_link GROUP BY type"
                                                             " ORDER BY COUNT(*) DESC")) + ")")
    behind = src["commit"] and src["commit"] != meta["commit"]
    print(f"  his {meta['version']}, {meta['commit'][:7]} of {meta['date']}"
          + (f"; his repository is now at {src['commit'][:7]} of {src['date']}: make cosmo-snapshot" if behind
             else "; his repository is at that commit" if src["commit"] else "; his repository is not on this machine"))
    checks = [
        ("the database holds the snapshot's personalities, units, cards and lines, each one",
         sum(n[k] != len(doc[k]) for k in ("persons", "units", "places", "links"))
         + int(meta["commit"] != doc["source"]["commit"])),
        ("every personality has one card where it has its origin",
         one("SELECT COUNT(*) FROM cosmo_person p WHERE (SELECT COUNT(*) FROM cosmo_place c"
             " WHERE c.person = p.id AND NOT c.ghost) != 1")),
        ("every card stands in a unit there is, and is a personality's",
         one("SELECT COUNT(*) FROM cosmo_place c WHERE c.unit NOT IN (SELECT id FROM cosmo_unit)"
             " OR c.person NOT IN (SELECT id FROM cosmo_person)")),
        ("every line ends at a card, or at a unit a line may end at",
         one("SELECT COUNT(*) FROM cosmo_link l, (SELECT 0 AS e UNION SELECT 1) x"
             " WHERE (CASE x.e WHEN 0 THEN l.a ELSE l.b END) NOT IN"
             " (SELECT id FROM cosmo_place UNION SELECT id FROM cosmo_unit WHERE linkable)")),
        ("every line has its route in English and in Russian",
         one("SELECT COUNT(*) FROM cosmo_link l WHERE (SELECT COUNT(*) FROM cosmo_route r"
             " WHERE r.link_id = l.id AND r.lang IN ('en', 'ru') AND r.d LIKE 'M%') != 2")),
        ("every name is in English and in Russian",
         one("SELECT COUNT(*) FROM (SELECT 'unit' AS kind, id FROM cosmo_unit UNION ALL SELECT 'person', id"
             " FROM cosmo_person UNION ALL SELECT kind, key FROM cosmo_key) x WHERE (SELECT COUNT(*)"
             " FROM cosmo_text t WHERE t.kind = x.kind AND t.key = x.id AND t.field = 'name') != 2")),
        ("every reference is a paper's or a section's",
         one("SELECT COUNT(*) FROM cosmo_ref r WHERE NOT EXISTS (SELECT 1 FROM section s"
             " WHERE s.paper_n = r.paper_n AND (r.section_n IS NULL OR s.n = r.section_n))")),
        ("every headword named for one is a headword of the index",
         one("SELECT COUNT(*) FROM cosmo_head h WHERE NOT EXISTS (SELECT 1 FROM index_entry e"
             " WHERE e.slug = h.slug AND e.scope = 'az' AND e.level = 1)")),
        ("every sign is one the page draws",
         one("SELECT COUNT(*) FROM cosmo_person WHERE glyph NOT IN"
             " ('deity', 'absolute', 'trinity', 'ascender', 'descending', 'angel', 'local', 'spirit')")),
    ]
    rc = 0
    for what, bad in checks:
        print(f"  {what:<70} {bad}")
        rc |= int(bad != 0)
    none = [r[0] for r in con.execute(
        "SELECT t.text FROM (SELECT 'person' AS kind, id, ord FROM cosmo_person UNION ALL"
        " SELECT 'unit', id, 1000 + ord FROM cosmo_unit) x JOIN cosmo_text t ON t.kind = x.kind AND t.key = x.id"
        " AND t.field = 'name' AND t.lang = 'en' WHERE NOT EXISTS (SELECT 1 FROM cosmo_head h"
        " WHERE h.kind = x.kind AND h.key = x.id) ORDER BY x.ord")]
    print(f"  with no headword in the index ({len(none)}, shown, not failed): " + "; ".join(none))
    return rc
