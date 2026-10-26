"""python3 -m build <command>"""
from __future__ import annotations

import sys

import pathlib

from . import config, vendorlib


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__ + "\n  sources | dirty [db] | vendor-sync | vendor-check", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    repos = config.load()

    if cmd == "sources":
        print(config.describe(repos))
        return 0
    if cmd == "dirty":
        # Whether a built database was read from uncommitted source files
        # (config._dirty), as its build_source records: deploy.sh refuses to
        # ship one unless told to (Tigran, 2026-10-18).  Each such source, and
        # what makes it dirty now; 3 if any, 0 if none, so that a failure here
        # (1) is never taken for a dirty build that --allow-dirty would ship.
        import sqlite3
        db = rest[0] if rest else str(config.ROOT / "var" / "ub.db")
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
            dirty = [k for (k,) in con.execute("SELECT repo FROM build_source WHERE dirty = 1 ORDER BY repo")]
        for k in dirty:
            r = repos[k]
            print(f"  {k}, {r['path']}:")
            for f in (config.dirty_files(r["path"], str(r["tex"].relative_to(r["path"])))
                      or ["(nothing now: built while it was dirty; build again)"]):
                print(f"    {f}")
        return 3 if dirty else 0
    if cmd == "vendor-sync":
        return vendorlib.sync({**repos, "texlive": config.texlive(),
                               "sqlite_wasm": config.sqlite_wasm(), **config.sbl()})
    if cmd == "vendor-check":
        return vendorlib.check({**repos, "texlive": config.texlive(),
                                "sqlite_wasm": config.sqlite_wasm(), **config.sbl()})

    if cmd == "paranoid":
        # Prove, rather than assert, that a build leaves the source repos alone.
        import hashlib
        import subprocess

        trees = [r["path"] for r in repos.values()]
        trees += [a["path"] for a in config.audio().values() if a["present"]]
        if config.block()["charts"] is not None:
            trees.append(config.block()["path"])

        def fingerprint():
            out = {}
            for tree in trees:
                for f in sorted(tree.rglob("*")):
                    if f.is_file() and ".git" not in f.parts:
                        try:
                            st = f.stat()
                            out[str(f)] = (st.st_mtime_ns, st.st_size)
                        except OSError:
                            pass
            return out

        before = fingerprint()
        print(f"fingerprinted {len(before):,} files in {len(trees)} source trees"
              " (three repos, the recordings and Block's charts)")
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
        from .readers.press import read_all, read_hyphenation, read_parts

        root = pathlib.Path(__file__).resolve().parent.parent
        out = root / "var" / "ub.db"
        out.parent.mkdir(exist_ok=True)
        tmp = out.with_suffix(".db.tmp")
        report = Report()
        t0 = time.time()

        def at(r):
            return (r["commit"] or "?")[:7] + ("-dirty" if r["dirty"] else "")

        print(f"reading press text, {repos['press']['rev']} at {at(repos['press'])} ...")
        papers = read_all(repos["press"]["tex"], report)
        parts = read_parts(repos["press"]["path"], report)
        from .hyphen import Hyphenator
        hyphenator = Hyphenator(read_hyphenation(repos["press"]["tex"], report))
        ix = repos["index"]
        print(f"reading index at {at(ix)} ...")
        az = read_az(ix["tex"], report, rev=ix["at"])
        apps = read_appendices(ix["tex"], report, rev=ix["at"])
        # The study edition's notes, for each paper reviewed in data/study/:
        # onto the press text before it is rendered, so one render places them.
        from . import study
        curated = study.load_curated(report)
        block = config.block()
        if curated:
            print(f"study notes of {len(curated)} paper{'s' * (len(curated) > 1)},"
                  f" the edition at {at(repos['study'])} ...")
        study_built = study.attach(papers, curated, repos["study"], block, report, hyphenator)

        con = db.create(tmp)
        print("loading ...")
        para_key = load.load_text(con, papers, parts, repos["press"], hyphenator, report)
        study.store(con, study_built)
        # The translations, each joined to our numbering (build/translation.py).
        from . import translation
        ours = translation.ours(con)
        tr_built = []
        for k in translation.meta():
            if k not in repos:
                report.hard("tr-no-source", k, "data/translations.toml names it, and config has no such source")
                continue
            print(f"translation {k}, at {at(repos[k])} ...")
            tr_built.append(b := translation.build(k, repos[k], ours, report))
            print(f"  {len(b.paras):,} paragraphs, {sum(len(p.notes) for p in b.paras)} notes,"
                  f" {len(b.headings)} titles")
        translation.store(con, tr_built, ours)
        translation.roundtrip(con, report)
        print("the Foundation's numbering ...")
        from . import foundation
        n_uf = foundation.load(con, repos["press"], report,
                               root / "tests" / "known-uf-refs.tsv",
                               root / "tests" / "known-separator-deltas.tsv")
        print(f"  {n_uf} paragraphs it numbers otherwise")
        print("the SRT Committee's reasons ...")
        from . import srt
        srt_src = config.srt()
        srt_stats = srt.load(con, srt_src, report, root / "tests" / "known-srt-deltas.tsv",
                             hyphenator)
        if srt_stats:
            print(f"  {srt_stats['srt_items']} changes considered;"
                  f" {srt_stats['srt_notes']} of the 1955 notes have their reason")
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
        print(f"  {derive.reading_path(con):,} headwords have a reading path")
        derive.anchors(con, report)
        n_links = derive.links(con, report)
        print(f"  {n_links:,} entries name a headword, now linked")
        n_pairs = derive.cocitation(con)
        derive.fts(con)
        print("speech ...")
        from . import speech
        n_speech = speech.derive(con)
        print("audio ...")
        from . import audio
        audio_stats = audio.load_audio(con, report)
        audio_stats["speech_units"] = n_speech
        print("changelog ...")
        from . import changelog
        print(f"  {changelog.load(con)} lines of ChangeLog.md, for /changelog")
        print("fonts ...")
        from . import fonts
        for name, (size, glyphs) in fonts.build(
                con, repos["press"]["path"] / "fonts", root / "ubsite", report).items():
            print(f"  {name:22} {size:>9,} bytes  " + (f"{glyphs} glyphs" if glyphs else "as published"))
        print("text versions ...")
        from . import versions
        text_version, pending = versions.assign(con, repos["press"])
        if pending:
            v = pending.version
            print(f"  version {v[0]}: {v[3]:,} records new or changed, {v[4]} removed"
                  f" -- data/text/ is appended to if the build passes; commit it")
        else:
            print(f"  unchanged at version {text_version}")
        con.execute("INSERT INTO build VALUES (1, ?, 3, 0)",
                    (time.strftime("%Y-%m-%dT%H:%M:%S"),))
        # The commits this database was read from: /healthz shows them, so the
        # live site can say which index it carries (the footer did too, with a
        # link to each, until 2026-10-18).  Only the repos the build reads;
        # study joins when Phase 6 imports it.
        con.executemany("INSERT INTO build_source VALUES (?,?,?,?,?,?)",
                        [(k, repos[k]["commit"], int(repos[k]["dirty"]), repos[k]["rev"],
                          repos[k]["date"], repos[k]["commit_url"]) for k in ("press", "index")])
        # And each translation read (build/translation.py).
        con.executemany("INSERT INTO build_source VALUES (?,?,?,?,?,?)",
                        [(b.key, repos[b.key]["commit"], int(repos[b.key]["dirty"]), repos[b.key]["rev"],
                          repos[b.key]["date"], repos[b.key]["commit_url"]) for b in tr_built])
        # The study edition, and Block's charts by their manifest's SHA-256, once
        # a paper's notes are on the site: until then the build reads neither.
        if study_built.papers:
            st = repos["study"]
            con.execute("INSERT INTO build_source VALUES ('study',?,?,?,?,?)",
                        (st["commit"], int(st["dirty"]), st["rev"], st["date"], st["commit_url"]))
            con.execute("INSERT INTO build_source VALUES ('block', ?, 0, 'manifest', NULL, NULL)",
                        (block["sha256"],))
            # And the library's pages the Bibliography links, by LIBRARY.tsv's SHA-256.
            if block["library_sha256"]:
                con.execute("INSERT INTO build_source VALUES ('library', ?, 0, 'LIBRARY.tsv', NULL, NULL)",
                            (block["library_sha256"],))
        # The SRT snapshot is no repository: its "commit" is the file's SHA-256,
        # its date the day it was fetched, its page the committee's.
        if srt_stats:
            import hashlib
            con.execute("INSERT INTO build_source VALUES ('srt', ?, 0, 'snapshot', ?, ?)",
                        (hashlib.sha256(srt_src["path"].read_bytes()).hexdigest(),
                         srt_stats["srt_fetched"][:10], srt_src["url"]))
        for k in ("press", "index"):
            if repos[k]["commit_url"] and not repos[k]["pushed"]:
                report.warn("source-not-pushed", f"{k} {repos[k]['commit'][:7]}",
                            "on no remote branch as of the last fetch: /healthz names"
                            " a commit nobody else can fetch until it is pushed")
        for k, q in [
                ("papers", "SELECT COUNT(*) FROM paper"),
                ("sections", "SELECT COUNT(*) FROM section"),
                ("paragraphs", "SELECT COUNT(*) FROM paragraph"),
                ("spans", "SELECT COUNT(*) FROM span"),
                ("footnotes", "SELECT COUNT(*) FROM footnote"),
                # Each \fnc in the press TeX: a place where the text departs
                # from the 1955 printing, with the 1955 reading.  The home page
                # counts these, not `footnotes`, which Phase 6's study notes join.
                ("variants_1955", "SELECT COUNT(*) FROM footnote"
                                  " WHERE kind='variant-1955'"),
                ("study_notes", "SELECT COUNT(*) FROM footnote WHERE kind='study'"),
                ("study_papers", "SELECT COUNT(*) FROM study_paper"),
                ("study_sources", "SELECT COUNT(DISTINCT key) FROM study_source"),
                ("srt_items", "SELECT COUNT(*) FROM srt_item"),
                ("variants_1955_explained", "SELECT COUNT(*) FROM footnote"
                                            " WHERE srt_item_id IS NOT NULL"),
                ("redletter_paragraphs", "SELECT COUNT(DISTINCT paragraph_id) FROM span"
                                         " WHERE kind='redletter'"),
                ("index_entries", "SELECT COUNT(*) FROM index_entry"),
                ("citations", "SELECT COUNT(*) FROM citation"),
                ("citation_targets", "SELECT COUNT(*) FROM citation_target"),
                ("xrefs", "SELECT COUNT(*) FROM xref"),
                ("chronology_events", "SELECT COUNT(*) FROM chronology_event"),
                ("appendix_entries", "SELECT COUNT(*) FROM index_entry"
                                     " WHERE scope IN ('B','C','D','E','F')"),
                ("appendix_heads", "SELECT COUNT(*) FROM appendix_head"),
                ("para_citers", "SELECT COUNT(*) FROM para_citers"),
                ("cocitation_pairs", "SELECT COUNT(*) FROM cocitation"),
                ("reading_paths", "SELECT COUNT(*) FROM reading_path"),
                ("translations", "SELECT COUNT(*) FROM translation"),
                ("tr_paragraphs", "SELECT COUNT(*) FROM tr_paragraph"),
                ("tr_notes", "SELECT COUNT(*) FROM tr_note")]:
            con.execute("INSERT INTO stat VALUES (?,?)",
                        (k, con.execute(q).fetchone()[0]))
        con.executemany("INSERT INTO stat VALUES (?,?)", sorted(audio_stats.items()))
        con.execute("INSERT INTO stat VALUES ('text_version', ?)", (text_version,))
        con.commit()
        con.execute("VACUUM")
        con.close()
        rc = report.emit()
        if rc:
            tmp.unlink(missing_ok=True)
            return rc
        # The ledger only after everything has passed: a failed build must not
        # leave a version behind that no database carries.
        if pending:
            pending.append()
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
                        repos["index"]["path"] / "data" / "srt.jsonl", {}, repos["study"]["at"])
        print("\n== study notes ==")
        from .checks.check_study import run as study_run
        rc |= study_run(repos["study"], config.block(), report)
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
        itex, iat = repos["index"]["tex"], repos["index"]["at"]
        az = read_az(itex, report, rev=iat)
        apps = read_appendices(itex, report, rev=iat)
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
            from .checks.check_hyphen import run as hyphen_run
            from .readers.press import read_hyphenation
            print("\n== hyphenation ==")
            rc |= hyphen_run(_db.connect(dbf), read_hyphenation(repos["press"]["tex"], report))
            from . import translation
            from .checks.check_hyphen import run_translations
            rc |= run_translations(_db.connect(dbf), {k: translation.hyphenation(k, repos[k], report)
                                                      for k in translation.meta() if k in repos})
            from .checks.check_audio import run as audio_run
            print("\n== audio ==")
            rc |= audio_run(_db.connect(dbf))

        print("\n== problems ==")
        rc |= report.emit()
        return rc

    print(f"unknown command {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
