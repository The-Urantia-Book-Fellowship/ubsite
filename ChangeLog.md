# Changelog

What has changed in *ubsite*, *The Urantia Book* read together with its index, at https://ubsite.ddns.net and https://ubsite.sigmaai.au. The newest is at the top.

The form follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). A release will be a tag `vX.Y.Z` on `main`, numbered by [Semantic Versioning](https://semver.org/spec/v2.0.0.html): the first number goes up when anything that reads `var/ub.db`, the text API or the class names in a paragraph's stored HTML has to change; the second when something is added; the third for a fix. Until the first release, everything is under Unreleased.

Under each version, Added, Changed, Deprecated, Removed, Fixed and Security are written for readers, one plain sentence to an entry, without Markdown: the site's What's new shows them to a reader whose offline copy is older, each dated by the day its line was written. For developers is for anyone who builds, deploys or reads the database: the schema, the API, what the build needs, and anything that breaks. What's new never shows it.

## [Unreleased]

### Added

- Search finds the study notes too, listed after the text while Settings shows them, each opening its paragraph with the note's card.
- Search finds the words of the translations shown beside the text, and of their translators' notes: each translation has a list of its own after the text's, in the order Settings gives them, a note under its paragraph, and a hit opens its paragraph with that translation unfolded. Е finds ё, and ё finds е.
- The translations can be kept in the offline copy, each a download of its own, chosen in Settings' Offline tab, and are then updated with it; a translation not kept says so in its fold when read offline.
- The translator's notes of Урантийские документы are small numbers in its text under a paragraph, each opening the note as a card, as a study note does, with the works it cites.
- Two Russian translations can be shown under each paragraph, folded to a line that opens them: tick them in Settings, in the new Translations tab, where their order is the order of a fold's tabs. None is shown unless you tick one.
- The site can be read with its interface in Russian: the flags at the top right switch between English and Russian, and a browser set to Russian starts in Russian. The text, the index and the appendices stay as the book prints them, in English.
- The Bibliography links each work that can be read freely in the Urantia Library to its page there, and so does a study note's card where it cites one.
- The offline copy now keeps itself up to date whenever the site is open and online, then shows what is new and reloads the page once that is closed; Settings can turn this off, leaving Update now to you.
- The page about the text API is in the offline copy too, so it can be read without a connection, naming the site it is read at; the API itself still needs one.
- Ctrl+X puts the words selected into the search box, ready to search with Enter or to be changed first, or with nothing selected goes to the search box; Escape there goes back to where you were reading.
- Paper 8, The Infinite Spirit, has study notes too, 16 of them, and the Bibliography lists the work they add.
- Paper 7, Relation of the Eternal Son to the Universe, has study notes too, 20 of them, and the Bibliography lists the three works they add.
- Paper 6, The Eternal Son, has study notes too, 16 of them, and the Bibliography lists the two works they add.
- Paper 5, God's Relation to the Individual, has study notes too, 29 of them, and the Bibliography lists the three works they add.
- Paper 4, God's Relation to the Universe, has study notes too, 27 of them, and the Bibliography lists the work they add.
- Paper 3, The Attributes of God, has study notes too, 32 of them, and the Bibliography lists the four works they add.
- Ctrl+, opens Settings from any page, and closes it again.
- Space, Page Down and the right arrow turn the page, keeping the last line read at the top, and Settings can make a tap on the text turn it too, on a phone or a tablet.
- Entries beside a paragraph that share a headword now stand together, the part they share said once and each entry's own words after it, separated by semicolons.
- Paper 1, The Universal Father, has eleven more study notes, 45 in all, each a parallel in Matthew Block's chart that no note gave.
- Beside a paragraph, a Chronology entry now stands first, and shows the event printed just before it in Appendix A and the one just after, each with a link to where the book tells it.
- Paper 2, The Nature of God, has study notes too, 29 of them, and the Bibliography lists the four works they add.
- Where a study note corrects Matthew Block's chart from the original, its credit line says so, with what it gives for his: a page, a title, a date.
- The List of study notes and the List of 1955 readings begin with "Go to a paper", which opens onto the numbers of the papers they list, to go straight to one.
- The Foreword and Paper 1 have study notes from The British Study Edition, edited by Tigran Aivazian, 45 in all, the first of the papers to have them, shown once Notes is turned on in Settings: each is a small number in the text that opens the note, the List of study notes gathers them, and the Bibliography lists the works they cite.
- Settings can turn off the index and the appendices, leaving the text alone, with its 1955 readings while those are on.
- A Changelog link at the foot of every page opens this changelog, each change with the day it was made; What's new links to it too.

### Changed

- Settings is in four tabs, Reading, Show, Listening and Offline, so that it no longer runs off the screen, and it keeps one size whichever tab is open.
- ubsite.sigmaai.au, the main site, now has the blue book as the icon of its tab and of its app, and ubsite.ddns.net the burgundy one; an app installed before keeps its old icon until it is installed again.
- The index and the appendices set the suffix of an ordinal as a superscript, as the book does, in 1st, 6th and December 25th: on their own pages, beside the text, in the reading paths and in search.
- Search results show a superscript where the text has one, as in 33:3.2's 611,121st, and so do the committee's reasons among the 1955 readings, and today's words beside each reading on the List of 1955 readings.
- The index is revised from its reading of Papers 20 to 28: entries reworded to say more exactly what the book says, numbers given as the book gives them, citations corrected, the creature-trinitized sons in the three kinds the book names, the Magisterial Sons' magisterial missions apart from their bestowals, and the college of the ethics of law and the technique of Supremacy and the transport personalities under the names the book gives them.
- The index is revised from its reading of Papers 17 to 19: entries reworded to say more exactly what the book says, the numbers of beings given as the book gives them, for Orvonton or for one superuniverse, citations corrected, and the Advisory Commission of Interuniverse Ethics and Self-government under the name the book gives it.
- What's new no longer adds a line of its own, "The index as of" a date, when the index or the text has changed: its lines from the changelog say what changed.
- The index is revised from its reading of Papers 11 and 14 to 16: entries reworded to say more exactly what the book says, citations corrected, and nether Paradise's three zones of absolute force presence numbered as the book numbers them, with the Zone of Infinity apart.
- The index now cites two paragraphs in a row as a range, and all it cites in one section together, so an entry citing such a pair stands beside the first of the two only, as one citing a longer range already did.
- With paragraph references, listening and the 1955 page references all off, each paragraph's first line is set in a little, as the book's are.
- A numbered list stands as the book sets it, every number ending at one place and every item's words beginning at one place.
- On a wide screen, as on a phone, a paragraph's reference and play button stand at its start, and the text stands nearer the contents; the play button stands on the second line, under the reference.
- The offline menu says simply what Work offline keeps: everything but Merritt Horn's recordings.
- A Chronology entry beside the text no longer has the heading Chronology over it; its dashed line marks it.
- On a wide screen a note's card, a 1955 reading's or a study note's, is set larger, in the same proportion to the text as on a tablet; on a phone or a tablet it is as before.
- A note's card, a 1955 reading's or a study note's, has its close button above the words, which now take the card's whole width; before, a long note was set in from the right all the way down.
- When the offline copy is up to date, its menu now gives the date of the site it keeps, as it already did when the copy was out of date.
- Dates are written the American way, month first: October 18.
- The footer is two lines: the edition and its licence, with a link to this changelog, and that the site is not affiliated with Urantia Foundation.
- The licence of Goudy, the book's typeface, is linked from Settings, beside the typeface.
- Update now, in the offline menu, reloads the page once the update is in, and brings with it the part of the site that answers offline, so that nothing needs reloading by hand, even when you go offline straight after.

### Fixed

- Ctrl+, opens Settings on a Russian keyboard too, where that key types б.
- Beside a paper's first paragraph, on a wide screen, the index entries stand level with its text again, not with the line of its reference above it.
- The Foreword is headed Foreword alone, as the book heads it, not Paper 0.
- The Bibliography gives the publisher of Illingworth's Personality Human and Divine as its 1894 title page does, Macmillan and Co., not The Macmillan Company.
- The Bibliography gives the publisher of Knudson's The Doctrine of God as its 1930 title page does, The Abingdon Press, not Abingdon-Cokesbury Press.

### For developers

- `requirements.txt` and `requirements-dev.txt` pin brotli 1.2.1, which mends an out-of-bounds write in its decoder (GHSA-9v8h-qqgm-4m35). Nothing here decodes brotli: fontTools uses it to write the WOFF2 fonts, which come out byte for byte as before. The hosts take it at the next deploy.
- `tr_paragraph` has a new column, `id`, its rowid named, which search indexes. `tr_paragraph_fts` and `tr_note_fts` (`build/schema/004_fts.sql`) index the translations' paragraphs and their translators' notes through two views, `tr_paragraph_folded` and `tr_note_folded`, that read ё as е, one letter for one. Search's `in` also takes `study` and each translation's key, so no translation's key may be `index`, `text`, `notes` or `study`. In the offline copy each translation's download has its database for search too, `tr-<key>.db`, which a worker from before fetches and never reads.
- The offline copy's manifest lists the translations apart, under `translations`, each with its chunks (`tr-<key>-<n>`, twenty papers to a chunk: each section's share of `/tr/`, its headings and its paragraphs), its size and a `build` of its own; `chunks`, `build`, `bytes` and `raw` are the copy without them, so a worker from before neither sees nor fetches them. The worker keeps those a reader chooses (`{cmd: 'get', tr: [keys]}`, and `{cmd: 'drop', tr: key}` to let one go) and joins a section's from them inside the fragment's frame. `deploy.sh` keeps their chunks on the hosts as it keeps the rest.
- A translator's note is set at build as a study note is, by its own closed table (`build/tr_macros.py` `UD_NOTES`): `tr_note` gains `id`, `key`, `text` and `html_hy`, and the works it cites are `tr_source` and `tr_cite`. Its marker in `tr_paragraph.html_hy` is `<a class="fn" data-k="tn" data-n="…">`, empty, as a study note's is, and `/tr/` sends each note after its paragraph as an `<aside class="note tn" data-of="…">`. A `\bibref` whose words name another paragraph than it links is set as its TeX sets it, and must be exactly `tests/known-tr-bibrefs.tsv`.
- A section's translations are sent by `/tr/<paper>:<section>`, an HTML fragment of every translation the section has, asked for under its version, the article's `data-trv`, and kept for good under it, as `/rail/N` is. On a section page each paragraph, or block of verse, is now a `.row` with its index entries and, where a translation has it, its fold, `.tf[data-has]`.
- `var/ub.db` holds two Russian translations, each read from its LaTeX repository at a commit (`../ud`, `../urantia-ru`) and joined to the press's numbering: `translation`, `tr_paragraph` (a translated paragraph under our `paragraph_id`, with its own address in `src_ref` where it numbers otherwise), `tr_heading` and `tr_note` (`build/schema/010_translation.sql`). Where a translation numbers otherwise, `tests/known-tr-numbering.tsv` says how, and the build requires exactly that list. Each is hyphenated as its own TeX would set it, by hyph-ru (vendored from TeX Live) and its own exception list. The database is about 44 MB larger.
- The interface is in English and Russian. Every word around the book is an entry of `ubsite/ru.toml`, keyed by its English, which `ubsite/l10n.py` draws in the templates and `/l10n.js` in the scripts. A page carries both languages, in `<x-en>` and `<x-ru>` elements and `data-ru-*` attributes, and CSS shows the reader's, by `data-lang` on `<html>`: no setting reaches the server, and the offline copy is still one copy for every reader. A string the site draws that `ru.toml` lacks is an error. `UB_BILINGUAL=0` in the environment draws English alone, as before.
- The offline copy's format is 2: a page's title piece begins inside its `<title` tag, so as to carry its Russian, `data-ru`. A worker from before refuses a copy of format 2 and asks for a reload.
- EB Garamond Regular and Italic, OFL 1.1, are vendored from TeX Live (`vendor/fonts/`), and `build/fonts.py` subsets them to the Cyrillic alphabet and № as more faces of UB Goudy, which has no Cyrillic. Its glyph gate now reads the words of `ru.toml` in both languages.
- `study_source` has a new column, `url`: the work's page where it can be read freely, in Tigran's library at https://ulib.sigmaai.au, or NULL. The build reads it from `originals/LIBRARY.tsv` in the block-sources directory, a line whose new column `public` is `yes`, and records that file's SHA-256 in `build_source` as `library`.
- `index_entry` has two new columns, `headword_html` and `path_html`, `xref` one, `target_html`, and `chronology_event` one, `label_html`: each the HTML of the plain column beside it, the same words with an ordinal's suffix in `<sup>`, as the index now sets it (`\ts`, its 0aeae38). The plain columns read `1st` as before. The offline search databases carry where each hit's superscripts stand.
- `chronology_event` has a new column, `line_html`: the event on one line with its citations as printed, each a link to its place in the text.
- The EPUB is retired: `epub/`, `make epub` and its epubcheck, `tests/test_epub.py` and `tools/make_cover.py` are gone, and nothing here needs Java any more. Work offline keeps the whole site in the browser, search and the reading paths with it. The last commit that builds the EPUB is tagged `epub-last`.
- `deploy.sh` no longer ships a file git neither tracks nor ignores, a draft or an editor's swap file, being in no commit; what the build makes is ignored and still goes.
- `study_note` has a new column, `corrects`, the HTML of what a note corrects in Block's chart from the original, and its `origin` may now be NULL, for a note the review adds, as `study_source`'s may for a source.
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
- `make epub` made the whole site an EPUB 3, private, until it was retired on October 19, 2026; the tag `epub-last` is the last commit that builds it.
