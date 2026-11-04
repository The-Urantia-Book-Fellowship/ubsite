# The Urantia Foundation's releases

One zip per translation, as the Foundation publishes it in HTML on urantia.org and as Tigran downloaded it, kept here unchanged: the build reads the zip itself (`build/readers/uf_html.py`), so that the site shows each translation as the Foundation released it, and a new release is a new zip. `sources.toml` names each under its key, `[uf-ru]`, `[uf-fr]` and so on, by its path here, its SHA-256 and the text id its cover page gives, and the build fails on any other bytes or any other id (`build/config.py _zip()`, `build/translation.py _uf_papers()`). What a reader is told about each is `data/translations.toml`.

**The zips are never committed.** This repository is public, and the Foundation's written permission (Mo Siegel, its President, to Tigran, 2026) is to show its text on the site, not to hand out its files: `.gitignore` leaves `*.zip` out, and `deploy/deploy.sh` does not ship them, since a host serves the database and never holds a source. `MANIFEST.tsv` is the record for a fresh clone: each zip by its name, its digest, its text id, the day it was downloaded and where from. A clone that is to build the database needs the zips it names, downloaded again from the Foundation; the digest proves the bytes.

Until 2026-11-04 the Russian one stood beside the old TeX of that translation in `../urantia-rus`, which is never read (`DECISIONS.md`, Russian, and the translations). Tigran moved it here when more of the Foundation's translations were about to follow (2026-11-04).

A new translation is: its zip here, its line in `MANIFEST.tsv`, its section in `sources.toml`, its entry in `data/translations.toml`, a `speak_*` function for its language in `build/speech.py` (the build fails without one), and a reviewed build.
