# Changelog

What has changed in *ubsite*, *The Urantia Book* read together with its index, at https://ubsite.ddns.net and https://ubsite.sigmaai.au. The newest is at the top.

The form follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). A release will be a tag `vX.Y.Z` on `main`, numbered by [Semantic Versioning](https://semver.org/spec/v2.0.0.html): the first number goes up when anything that reads `var/ub.db`, the text API or the class names in a paragraph's stored HTML has to change; the second when something is added; the third for a fix. Until the first release, everything is under Unreleased.

Under each version, Added, Changed, Deprecated, Removed, Fixed and Security are written for readers, one plain sentence to an entry, without Markdown: the site's What's new shows them to a reader whose offline copy is older, each dated by the day its line was written. For developers is for anyone who builds, deploys or reads the database: the schema, the API, what the build needs, and anything that breaks. What's new never shows it.

## [Unreleased]

### Added

- The List of study notes and the List of 1955 readings begin with "Go to a paper", which opens onto the numbers of the papers they list, to go straight to one.
- The Foreword and Paper 1 have study notes from The British Study Edition, edited by Tigran Aivazian, 45 in all, the first of the papers to have them, shown once Notes is turned on in Settings: each is a small number in the text that opens the note, the List of study notes gathers them, and the Bibliography lists the works they cite.
- Settings can turn off the index and the appendices, leaving the text alone, with its 1955 readings while those are on.
- A Changelog link at the foot of every page opens this changelog, each change with the day it was made; What's new links to it too.

### Changed

- On a wide screen a note's card, a 1955 reading's or a study note's, is set larger, in the same proportion to the text as on a tablet; on a phone or a tablet it is as before.
- A note's card, a 1955 reading's or a study note's, has its close button above the words, which now take the card's whole width; before, a long note was set in from the right all the way down.
- When the offline copy is up to date, its menu now gives the date of the site it keeps, as it already did when the copy was out of date.
- Dates are written the American way, month first: October 18.
- The footer is two lines: the edition and its licence, with a link to this changelog, and that the site is not affiliated with Urantia Foundation.
- The licence of Goudy, the book's typeface, is linked from Settings, beside the typeface.
- Update now, in the offline menu, reloads the page once the update is in, and brings with it the part of the site that answers offline, so that nothing needs reloading by hand, even when you go offline straight after.

### For developers

- The nginx server blocks (`deploy/*.nginx`) now compress what is under `/static/`: the stylesheet, the scripts, SVG and the fonts served as TTF or OTF, as the SBL fonts must be (SBL Greek goes from 1.1 MB to 0.4 MB). Until now only HTML was compressed, `nginx.conf` naming no `gzip_types`. `deploy.sh` does not install a server block: on each host, install it again by hand, as root, as in `deploy/README.md` step 3, then `nginx -t` and reload nginx. Without it the site works as before, sending these uncompressed.
- A study note's Greek and Hebrew are set in SBL Greek and SBL Hebrew, vendored by address and digest (`sources.toml`) and served as published: their licence, unlike the site's other fonts', is not OFL, and allows them to be embedded only in non-commercial web pages and e-books, and redistributed only unmodified, so they are never subset (`build/fonts.py`).
- `var/ub.db` has four new tables, `study_paper`, `study_note`, `study_source` and `study_cite`, for the British Study Edition's notes, which reach the site one paper at a time, each reviewed in `data/study/`, the Foreword first. The build now reads the study edition at HEAD, and `../block-sources/MANIFEST.tsv`, the list of Matthew Block's charts of the human sources (`build/study.py`). `deploy.sh` refuses an uncommitted `data/study/`.
- `deploy.sh` refuses a database built from uncommitted press files, listing them, unless given `--allow-dirty`; `python -m build dirty var/ub.db` says whether a database is dirty (3) or clean (0). The index cannot be dirty: it is read at a commit.
- `var/ub.db` has a new table, `changelog`: this file block by block, which `/changelog` shows as written, each entry dated by the commit that wrote it, since the hosts have no `.git`. `build/changelog.py` makes it, and `offline/news.py` now reads the file through it, so What's new and the page cannot disagree.
- The footer no longer names the commits the text and the index were built from, nor links them on GitHub, their repositories being private; `/healthz` still names them. Nor does it name the typeface, say that other sites may sync with the text, or say how visits are counted.
- The site's What's new is read from this file (`offline/news.py`), each entry dated by the commit that wrote its line. Before this file began, it listed the subjects of the commits that touched `ubsite/`, `offline/`, `build/` or `data/`, and copies made before then still see those.

## The site on October 18, 2026, when this changelog began

Not a release, and not news: what the site was when this file began, for whoever starts reading here.

### Reading

- The text of the Uversa Press edition: 197 papers, 1,626 sections and 14,586 paragraphs, each paragraph at an address of its own (`/101:4.2`) and marked with its reference.
- Set as the book sets it: justified, and hyphenated only where the book hyphenates; verse as verse; the separators; each paper's first letter dropped two lines; the words of Jesus in red.
- The 180 places where the text departs from the 1955 printing, each a small ring that opens the 1955 reading, as the press gives it, with the SRT Committee's decision and reasons. All 180 are listed at `/lists/1955`.
- Settings, kept in the browser, with no account: theme, text size, line spacing, typeface, width, and what is shown beside the text.
- Search over the text and the index, and the 1955 readings when Settings asks; a reference typed into it opens that paragraph or range.

### The index

- The Uversa Press index, A–Z and Appendices A–F, read in both directions: a page for each of its 4,736 headwords, and beside every paragraph each entry that cites it.
- Every See, See also and q.v. is a link to what it names.
- A headword citing three paragraphs or more can be read through as one text, in the order of the book or by theme.

### Listening

- Every section in Merritt Horn's reading, from any paragraph, or in the browser's own voice. Playing can carry on through the book, and goes on while the reader moves to other pages.

### Work offline

- The whole site can be kept in the browser, search and the reading paths included, but not the recordings; offline, the browser's voice reads.

### For developers

- `var/ub.db` is built from three LaTeX repositories by `make data` and gated by `make check`; it is what the hosts are sent. The README's "Updating the site" is the procedure, and `CLAUDE.md` the record of decisions.
- Its schema is `build/schema/*.sql`; `PRAGMA user_version` is 1.
- The text API, `/api/v1`, documented at `/api`, is at text version 8.
- Python 3.12, FastAPI and Jinja2, rendered on the server; the offline copy is the site's own pages, held to the server's byte for byte by `make offline`.
- `make epub` makes the whole site an EPUB 3, private for now.
