"""python3 -m build <command>"""
from __future__ import annotations

import sys

import pathlib

from . import config, vendorlib


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__ + "\n  sources | vendor-sync | vendor-check", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    repos = config.load()

    if cmd == "sources":
        print(config.describe(repos))
        return 0
    if cmd == "vendor-sync":
        return vendorlib.sync(repos)
    if cmd == "vendor-check":
        return vendorlib.check(repos)

    if cmd == "paranoid":
        # Prove, rather than assert, that a build leaves the source repos alone.
        import hashlib
        import subprocess

        def fingerprint():
            out = {}
            for r in repos.values():
                for f in sorted(r["path"].rglob("*")):
                    if f.is_file() and ".git" not in f.parts:
                        try:
                            st = f.stat()
                            out[str(f)] = (st.st_mtime_ns, st.st_size)
                        except OSError:
                            pass
            return out

        before = fingerprint()
        print(f"fingerprinted {len(before):,} files in 3 source trees")
        rc = main(["data"])
        after = fingerprint()
        changed = [k for k in before if k in after and before[k] != after[k]]
        gone = [k for k in before if k not in after]
        new = [k for k in after if k not in before]
        for k in (changed + gone + new)[:20]:
            print(f"  TOUCHED {k}")
        ok = not (changed or gone or new)
        print(f"\nsources {'UNCHANGED' if ok else 'MODIFIED'}: "
              f"{len(changed)} changed, {len(gone)} removed, {len(new)} added")
        return rc or (0 if ok else 1)

    if cmd == "data":
        import time

        from . import db, derive, load
        from .problems import Report
        from .readers.index_app import read_appendices
        from .readers.index_az import read_az
        from .readers.press import read_all

        root = pathlib.Path(__file__).resolve().parent.parent
        out = root / "var" / "ub.db"
        out.parent.mkdir(exist_ok=True)
        tmp = out.with_suffix(".db.tmp")
        report = Report()
        t0 = time.time()

        print("reading press text ...")
        papers = read_all(repos["press"]["tex"], report)
        print("reading index ...")
        az = read_az(repos["index"]["tex"], report)
        apps = read_appendices(repos["index"]["tex"], report)

        con = db.create(tmp)
        print("loading ...")
        para_key = load.load_text(con, papers, repos["press"], report)
        load.load_index(con, az, apps, para_key, report)
        print("slugs ...")
        from . import slugs
        heads = [h for (h,) in con.execute(
            "SELECT headword FROM index_entry WHERE level=1 AND headword IS NOT NULL"
            " AND scope='az' ORDER BY ord")]
        table = slugs.assign(heads, report)
        con.execute("ALTER TABLE index_entry ADD COLUMN slug TEXT")
        con.executemany("UPDATE index_entry SET slug=? WHERE id=?",
                        [(table[h], i) for i, h in con.execute(
                            "SELECT id, headword FROM index_entry"
                            " WHERE level=1 AND headword IS NOT NULL AND scope='az'")
                         if h in table])
        con.execute("CREATE INDEX index_entry_slug ON index_entry(slug)")

        print("deriving ...")
        derive.reverse_map(con)
        derive.density(con)
        derive.entry_stats(con)
        derive.anchors(con, report)
        n_pairs = derive.cocitation(con)
        derive.fts(con)
        print("fonts ...")
        from . import fonts
        for name, (size, glyphs) in fonts.build(
                con, repos["press"]["path"] / "fonts", root / "ubsite", report).items():
            print(f"  {name:22} {size:>7,} bytes  {glyphs} glyphs")
        con.execute("INSERT INTO build VALUES (1, ?, 1, 0)",
                    (time.strftime("%Y-%m-%dT%H:%M:%S"),))
        for k, q in [
                ("papers", "SELECT COUNT(*) FROM paper"),
                ("sections", "SELECT COUNT(*) FROM section"),
                ("paragraphs", "SELECT COUNT(*) FROM paragraph"),
                ("spans", "SELECT COUNT(*) FROM span"),
                ("footnotes", "SELECT COUNT(*) FROM footnote"),
                ("index_entries", "SELECT COUNT(*) FROM index_entry"),
                ("citations", "SELECT COUNT(*) FROM citation"),
                ("citation_targets", "SELECT COUNT(*) FROM citation_target"),
                ("xrefs", "SELECT COUNT(*) FROM xref"),
                ("chronology_events", "SELECT COUNT(*) FROM chronology_event"),
                ("para_citers", "SELECT COUNT(*) FROM para_citers"),
                ("cocitation_pairs", "SELECT COUNT(*) FROM cocitation")]:
            con.execute("INSERT INTO stat VALUES (?,?)",
                        (k, con.execute(q).fetchone()[0]))
        con.commit()
        con.execute("VACUUM")
        con.close()
        rc = report.emit()
        if rc:
            tmp.unlink(missing_ok=True)
            return rc
        tmp.replace(out)
        mb = out.stat().st_size / 1e6
        print(f"\n{out}  {mb:.1f} MB  in {time.time()-t0:.1f}s")
        for k, v in db.connect(out).execute("SELECT key, value FROM stat"):
            print(f"  {k:20} {v:>8,}")
        return 0

    if cmd == "check":
        from .checks.check_align import run as align_run
        from .checks.check_text import load_deltas, load_oracle, run as text_run
        from .problems import Report
        from .readers.press import read_all

        root = pathlib.Path(__file__).resolve().parent.parent
        from . import oracle
        report = Report()

        # Rebuild the oracles first, from the sources as they stand right now.
        # They are derived and regenerate in seconds; comparing against a copy
        # built days ago would report agreement with an older book.
        print("== oracles ==")
        srt = oracle.build_srt(repos, report)
        ital = oracle.build_italics(repos, report)
        print(f"  srt {srt}")
        print(f"  italics {ital}")

        print("\n== press text ==")
        papers = read_all(repos["press"]["tex"], report)
        rc = text_run(papers,
                      load_oracle(srt or repos["index"]["path"] / "data" / "srt.jsonl"),
                      load_deltas(root / "tests" / "known-oracle-deltas.tsv"))
        print("\n== section titles vs press HTML ==")
        from .checks.check_titles import load_press_titles, run as titles_run
        htmldir = repos["press"]["path"] / "misc" / "html"
        if htmldir.is_dir():
            rc |= titles_run(papers, load_press_titles(htmldir),
                             load_deltas(root / "tests" / "known-title-deltas.tsv"))
        else:
            print("  press misc/html absent -- skipped")
        print("\n== edition alignment ==")
        rc |= align_run(repos["study"]["tex"],
                        repos["index"]["path"] / "data" / "srt.jsonl", {})
        print("\n== italic spans vs press artifacts ==")
        from .checks.check_spans import load_press_italics, run as span_run
        art = ital or (repos["press"]["path"] / "artifacts" / "text-verify" / "tex")
        if art and art.is_dir():
            rc |= span_run(papers, load_press_italics(art))
        else:
            print("  press artifacts absent -- skipped")

        print("\n== index ==")
        from .checks.check_index import check_citations, check_xrefs
        from .readers.index_app import read_appendices
        from .readers.index_az import read_az
        itex = repos["index"]["tex"]
        az = read_az(itex, report)
        apps = read_appendices(itex, report)
        app_entries = [e for a in apps for e in a.entries]
        events = [v for a in apps for v in a.events]
        paras = {(q.paper, q.section, q.n) for p_ in papers for q in p_.paragraphs}
        c = check_citations(az + app_entries, events, paras, report)
        x = check_xrefs(az, app_entries, report)
        print(f"  entries        {len(az)} A-Z + {len(app_entries)} appendix"
              f" + {len(events)} chronology events")
        print(f"  citations      {c['citations']} -> {c['targets']} targets "
              f"{c['by_precision']}")
        print(f"  unreachable    {c['unreachable']}")
        print(f"  cross-refs     {x['targets']} targets, {x['dangling']} dangling")
        print(f"  of {x['qualified']} colon-qualified: {x['deep_linkable']} "
              f"deep-linkable to an exact sub-entry, {x['headword_only']} "
              f"resolve to the headword only")

        dbf = root / "var" / "ub.db"
        if dbf.exists():
            from . import db as _db
            from .checks.check_db import run as db_run
            print("\n== database ==")
            rc |= db_run(_db.connect(dbf))

        print("\n== problems ==")
        rc |= report.emit()
        return rc

    print(f"unknown command {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
