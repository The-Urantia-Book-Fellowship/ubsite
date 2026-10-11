# ubsite

An interactive presentation of the Urantia revelation: the Uversa Press text read together with the Uversa Press index, so that the index works in both directions — from a concept into the text, and from any paragraph back to everything the index says about it.

The plan this was built from is `~/.claude/plans/have-a-look-at-fluttering-peacock.md`. `ROADMAP.md` beside this file is the survey of what the data makes possible — seventeen ideas ranked, with what to build and what deliberately not to.

Read §0 and §1 here first; `ROADMAP.md` for where this is going; the plan for the phase-by-phase detail.

---

## 0. The one thing to understand

**The product is the database.** The website, a future API, and any export are views over `var/ub.db`. Three LaTeX projects are read, verified against independent evidence, and loaded into one queryable store. If you are tempted to put logic in a template or a route that belongs in the build, don't.

The second thing: **the three source repos are masters and are never written to.** Not their `tex/`, not even their gitignored derived directories. This is enforced mechanically, not by good intentions — see §6.

---

## 1. The sources

Paths live in `sources.toml` and **nowhere else**; `build/config.py` is the only module that reads it.

| key | repo | what it supplies |
|---|---|---|
| `press` | `../urantia-uversa-press-claude` | the authoritative text |
| `study` | `../urantia-study-edition` | apparatus: footnotes, human sources, KJV, quiz, images *(not yet imported)* |
| `index` | `../index` | the Uversa Press index, revised for the third edition |
| `audio.mh` | `/Audio/Urantia/Urantia-MH-Audio-DVD` | Merritt Horn's reading, one MP3 per section, 121 h, as on the Uversa Press DVD (2006): 128 kbps stereo, 44.1 kHz. On pi5 too, same path |

All three share one address space: the `\vs` macro addresses `\vs p133 1:3` (a Urantia paragraph) and `\vs Gen 1:1` (a Bible verse) alike.

The index is read **at HEAD** and the revision recorded in the build, because that repo is under active editorial work. Count gates against it are therefore reported bands; structural gates stay hard.

Until 2026-10-06 the first half of that was not true. The readers opened the working tree, while `config` reported HEAD as clean. Now `config` resolves `rev` to one SHA (`at`), `_io.read_tex` reads `tex/` at it, and `build_source` records it. `tests/test_read_tex.py` proves that worktree edits do not get through.

Careful: there are three `urantia-study-edition` trees on this machine. `urantia-study-edition-latest` is the **oldest**. `sources.toml` pins the right one.

---

## 2. Commands

```
make venv           create .venv (uv) and sync requirements.txt -- run this first
make lock           recompile requirements.txt from requirements.in
make sources        the three repos and the revisions in use
make vendor-check   re-hash the vendored copies against upstream (fails with a diff)
make data           build var/ub.db          (~17 s)
make check          every gate               (~8 s; rebuilds the oracles first)
make epub           the whole site as an EPUB -> var/epub/  (~3 s, ~10 s more for its gates)
make test           the never-write-to-a-master guards
make paranoid       fingerprint all three trees, build, and prove nothing moved
make serve          the reader on 127.0.0.1:8130 (HOST=0.0.0.0 to reach it from a phone)
make stop           stop it (by pid — never by pattern, see §6)

make align-transcribe   Whisper over the recordings, 3090 only (~1.5 h, resumable)
make align / align-repair   cut them at the paragraph -> data/audio/mh.tsv
make tts-bakeoff        the AI-voice listening test -> var/tts/bakeoff/
make tts                the whole book in the AI voice, 3090 only (~27 h, resumable)
make tts-assemble       one MP3 per section from what has been made -> data/audio/ai*.tsv
```

The ML environments (`venv-align`, `venv-tts`, `venv-chatterbox`, `venv-browser` for Playwright) and their caches live in **`~/Software/ml`**, on the NVMe home, never in `requirements.txt` and never on `/Audio`.

`make data` never edits in place: it builds `var/ub.db.tmp` and swaps it in, so a failed build leaves the previous database untouched.

**Updating the live site and deploying it** is a fixed procedure, and it lives in `README.md`, not here: is pi5 behind, vendor drift, build, gate, look, commit, `./deploy/deploy.sh`, verify.

---

## 3. What is built

**Phases 0–5 are done.** The annotated reader runs.

- `build/` — LaTeX → `var/ub.db`, stdlib only
  - `expand.py` — the span-emitting expander. Plain text plus code-point spans.
  - `press_macros.py` — derived from press's own table, with 5 overrides; asserts key-set equality, so a new macro upstream fails our build too
  - `index_macros.py` — the index's closed 24-macro set, plain and HTML renderers
  - `readers/` — pure file → dataclasses; `_io.py` is the only module allowed to open a source path, always mode `'r'`
  - `render.py` — `(text, spans) → HTML`. **The only renderer.**
  - `load.py`, `derive.py`, `schema/*.sql`, `oracle.py`, `fonts.py`, `slugs.py`
  - `checks/` — the gates
- `ubsite/` — FastAPI + Jinja2, server-rendered, no build step, ~33 KB CSS, ~10 KB `ub.js` plus `listen.js` on section pages
- `vendor/` — copied by value with `UPSTREAM.lock`: press's tokenizer/macros/normalize, index's `cite.py`/`xref.py`
- `.venv/` — `uv venv` + `uv pip sync requirements.txt`, gitignored; `requirements.txt` is compiled from `requirements.in` with `uv pip compile`. Same arrangement as `../libnodes`. **Everything runs under it** — `make` sets `PY := .venv/bin/python`, so the build gets fontTools and the server gets uvicorn from one place.
  **Python 3.12**, pinned in `.python-version` to match `../libnodes` and `urantia-library`: all three will be hosted on the same Raspberry Pi 5 with uv-managed venvs, and sharing one interpreter saves fetching and storing a second. The full gate suite passes on it, with byte-identical output.

- **Listening** (2026-10-07). Every section can be heard in Merritt Horn's reading, and from any paragraph once his reading is aligned:
  - `build/audio.py` reads `data/audio/` into `audio_source`, `audio_file`, `audio_segment` and `audio_unread`. Each voice is a list of segments, `(file, start_ms, end_ms)`, one per paragraph plus a spoken heading. The player never knows whether a voice is one file per section or one per paragraph.
  - `build/speech.py` builds the `speech` table: the text as a voice is to read it, with numbers in words, list marks spoken and brackets dropped. It is gated so that no digit or symbol survives.
  - `tools/align/` turns the recordings into `data/audio/mh.tsv`: Whisper, difflib, and cuts placed in pauses.
  - `tools/tts/` makes the AI voice: the listening test that chose it, and `make tts` (§12).
  - `/audio/<key>/<name>` serves only names listed in `audio_file`, with Range support.
  - **Your browser's voice** (2026-10-08) needs no recording: the browser speaks the `speech` text itself (the Web Speech API), fetched from `/speech/<paper>:<section>` once that voice is chosen. It is a stopgap beside Merritt Horn until the recorded AI reading exists, then a third choice (§8, §12).
  - The player is `static/listen.js` (~31 KB, section pages only). While it plays with Follow along off, it also follows the site's links inside the page, so the reader can go anywhere and the reading goes on (§8). Settings, the ⚙ dialog, are declared in `ubsite/settings.py`, run by `ub.js`, stored in `localStorage` under `ub_settings`, and applied before first paint (§8).
- **The appendices** (2026-10-09). `/appendix/A` is the Chronology as printed, each year in a column of its own beside its months and events, with a jump bar by period; `/appendix/B` … `/F` are the five name lists, in two columns as printed. Every *q.v.* in the index, A–Z and appendix alike (1,026), links to the headword it names, and so does every B–F name that is an A–Z headword (`appendix_head`, 1,332 of 1,351): both are `derive.links`. A concept page says which appendices list it, and an appendix chip in the margin links to its line (§8).
- **Visits** (2026-10-09). The site counts its own visitors, server-side: `ubsite/visits.py` (a pure ASGI middleware, a queue, a writer thread per worker) → `var/visits.db` (`ubsite/visits.sql`), and a private `/stats` page (`ubsite/stats.py`, `templates/stats.html`) behind HTTP Basic auth against `var/stats.passwd`. Places come from DB-IP City Lite (`make geoip`, shipped by `deploy.sh`). README, "Visits".
- **The EPUB** (2026-10-10). `epub/` is the third view over `var/ub.db`: the whole site as one EPUB 3, offline, except listening. `make epub` builds `var/epub/the-urantia-book.epub` (5.5 MB) and gates it. The Foreword, the four parts with their papers (one file each), the Index A–Z with each headword its whole concept page, then Appendices A–F, as the volume prints them. Beneath every paragraph stand the entries that cite it, as on a phone; every paragraph begins with its reference as literal text, so a reader's own search for `101:4.2` finds it; the 1955 readings are pop-up notes. The entries citing a whole section stand under its title without the site's "Cited across this whole section" (Tigran: where they stand says so; the site keeps it). Entries are separated by a black `|` that is not a link, beneath paragraphs and in "Cited alongside". **No contents page** (Tigran: the reader's built-in outline, `nav.xhtml`, is easier); the outline reaches every section. **No red letter** (Tigran: it looks bad on e-ink): the spans are in the markup, uncoloured. **Private for now**: no download route, no deploy step, no Uversa Press metadata or ISBN until publishing is decided. What stands beside a paragraph and what a concept page lists come from **`ubsite/queries.py`**, which the site's routes call too, so the margin's rules exist once. The gates (`epub/check.py`) read the file back: every link lands, every paragraph and index entry round-trips to the database, counts match, every glyph is in the embedded Goudy, the same database gives the same bytes, and epubcheck (W3C, 5.4.0 in `~/Software/epubcheck`, which needs `openjdk-26-jre-headless`) reports nothing. The cover is `epub/cover.jpg`, drawn by `tools/make_cover.py`; the fonts are the site's own subset, unwrapped to OTF, and `build/fonts.py` scans `epub/templates/` so the subset covers the EPUB's own characters.
- **The text API** (2026-10-11). `/api/v1` lets other sites keep their copy of the English text in step with ours, and `/api` documents it, with a client in Python. Its first users are Vladislav Pogorelov's Urantia Papers Explorer and Alexander Alyuev's UB_AI_Search.
  - **The protocol is a text version.** A site keeps the number it was sent and asks `/api/v1/text?since=N`. It gets every record new or changed since N, the keys of any removed, and the new number. From 0 it gets the whole text, 3 MB gzipped.
  - **A record** is a part, a paper, a section or a paragraph, each with a hash. A paragraph also has `text`, `html` and `uf_ref`. The `html` is `render.py`'s, without the note markers.
  - **`build/versions.py`** keeps the versions in an append-only ledger, `data/text/`, because `ub.db` remembers no earlier build. The ledger is appended only after a build passes.
  - **`build/foundation.py`** gives every paragraph and section the Foundation's reference, `uf_ref`. It reads its SRT HTML (the zip in the press repo) and aligns it with ours paper by paper. Its differences must be exactly `tests/known-uf-refs.tsv`.
  - **`ubsite/api.py`** only concatenates stored records. Each worker gzips a reply once. Replies carry an ETag, so an unchanged one is a 304, and `Access-Control-Allow-Origin: *`.
  - **Calls are counted apart from views**, in `api_call` in `visits.db`. `/stats` lists each caller by its User-Agent.
- `deploy/` — the systemd unit, the nginx server block, the sudoers drop-in and `deploy.sh`, with a README naming the four steps that need root. All four have been run; the site is live at **https://ubsite.ddns.net**. **The database is the artifact**: the three source repos are not on pi5 and do not need to be, so `make data` runs here and `var/ub.db` is shipped.

Next: Phase 6 (the study-edition apparatus — `\fnst` notes, KJV, the quiz, figures behind the rights gate), then 7 (human sources), 8 (the timeline, the map).

---

## 4. The numbers

Every asserted number lives in `verify/expectations.toml` with `measured_on` and `source_commit`, **never in code**. `verify/exceptions.toml` is currently empty and should stay that way.

```
papers 197 · sections 1,626 · paragraphs 14,586
red-letter spans 1,267 · em spans 2,295 · 1955 variant notes 180
index entries 34,751 (32,964 A–Z + 1,351 appendix + 436 chronology events)
citations 39,885 → 50,842 targets {para 47,954, sec 2,254, paper 634}
cross-references 5,133 See/See also + 1,026 q.v., 0 dangling · headwords 4,736
B–F names that are A–Z headwords 1,332 · para_citers 113,992 · cocitation pairs 9,719
paragraphs the Foundation numbers otherwise 107 · text API records 16,413, at version 1 (2026-10-11)
```

The index lines move as the index is edited (these are at its `224c84d`, 2026-10-09).

**The best single structural check** is that every one of the 1,626 sections numbers its paragraphs 1..N with no gap and no duplicate. It holds in both editions. A verse block numbered wrongly shows up immediately as a hole.

---

## 5. Three oracles, and what each can prove

The comparison sources are **not the text**. Our text and all its spans come from our own parse; the oracles exist to prove that parse is right rather than merely self-consistent.

| source | proves |
|---|---|
| `build_srt.py` output | the plain text of all 14,586 paragraphs |
| press `extract_tex.py` output | the `em` spans, **by offset** |
| press `misc/html/` | dot-leader rows (26), `<sup>` (23), the 1955 page refs |

Both derived oracles are gitignored and regenerate in seconds, so a stale one would silently describe an older book. `make check` therefore **rebuilds them first**, by running the sibling projects' own tools unmodified in sandboxes under `var/` with the inputs symlinked in. Neither tool takes an output path; both write relative to the working directory, so giving them the right working directory is the whole trick.

**Nothing external marks the red letter.** The SRT HTML sets "Fear not." plain. Those 1,267 spans exist only in the press TeX — unverifiable, and the most distinctive thing the site carries.

Three places where the oracle is wrong and we are right are recorded in `tests/known-oracle-deltas.tsv`, each arbitrated against the SRT HTML. The gate requires **exactly** that set: a new disagreement fails, and so does one of these silently going away.

---

## 6. Rules

**Never write to a source repo.** `build/readers/_io.py` is the only module that may open a source path. `tests/test_no_writes.py` greps the package for write-mode opens and for writes near a sibling path; allowlisted writers must name their target and it must resolve inside this project. `make paranoid` fingerprints all three trees before and after a build.

**Vendor by value, never `sys.path` into a live sibling.** Press rewrites paragraph wrappers on every build; the index is edited daily. `make check-vendor` re-hashes and fails with a unified diff. Refreshing is a reviewed commit.

**Fail loudly.** An unknown macro, an unparseable citation, a span outside its paragraph, a source line nothing claimed — all are hard failures. The upstream readers *skip* what they do not recognise; we invert that everywhere.

**Never `pkill -f <pattern>`** where the pattern appears in the command you are typing. It matches the shell running it, kills itself, and orphans the process. This is how four dev servers ended up listening at once. Use `make stop`.

**Round-trip is the contract.** Stripping the tags from any rendered HTML must return the stored text byte for byte — 14,586 paragraphs and 34,625 index entries, both gated. This is why dot leaders and footnote markers are drawn in CSS: markup must not inject characters a reader would copy.

---

## 7. Traps, each of which has already cost something

1. **`\tunemarkup` means the opposite thing in the two repos.** Study defines it as a conditional *include*; press strips both arguments. One shared macro table would silently delete all 84 figures and 19 bibliographies.
2. **`\pc` takes an optional argument**, and `159:1.7`'s text really begins with `[`. Reassembling a `\vs` line by concatenation swallowed the whole paragraph as a false optional arg. Parse the prefix and the body separately.
3. **`\kern-1pt` takes an unbraced length**; `\makeatletter` lines are a skip region.
4. **`\itshape` switches to italic for the remainder of its group**, wherever in the group it appears — in the one live case (`0:12.10`) it sits after an `\hspace*`, so testing the leading token misses it.
5. **Appendix A contains no `\iapp`.** Keying an appendix reader on it imports A as empty — the exact bug that hid its 470 citations from every check in the index project until 2026-09-13.
6. **`\chrontext` vs `\chronsubtext` is the parentage signal, not document position.** A `\chrontext` can follow a `\chronmonth` and still hang off the year. `read_pack.py` gets this subtly wrong; don't copy it.
7. **The terminal period on a headword is a convention with 15 documented exceptions**, not a rule — the index project's CLAUDE.md §13 records that assuming one "set 373 lines wrong". Classify by what the second argument *contains*.
8. **`xref.fold()` collides**: 4,736 headwords → 4,734 folded keys. Never a key.
9. **`p139` has no section 10.** `\usectiontwo{9 and 10}` is one heading over one block; paragraphs run `139:9.x` then jump to 11. Sections are derived from paragraphs, with `combined_with` recording the second number.
10. **One cross-reference resolves to seven headwords** — `Master Spirit #1 – #7`. `xref` records a `route` (`head` / `conjunction` / `range`); the gate requires a route, not a head.
11. **Two indexes are load-bearing for build time**: `paragraph(paper_n, section_n)` and `citation_target(entry_id)`. Without the second, `entry_stats` runs 34,600 × 50,758 × 3 row scans and the build never finishes. It is 7 s with them.
12. **The study edition's `extracttext.py` truncates ~2/3 of its footnotes** (`[^}]+` against nesting three deep). Do not reuse it when Phase 6 lands.
13. **Batched Whisper drops whole stretches of speech.** It heard 2 of 52:6.4's 69 words, though all 30 seconds are there. `make align-repair` re-hears every mostly-unheard paragraph unbatched; what is still unheard after that was not read (`mh-unread.tsv`).
14. **Whisper starts the first word after a long pause too early**: 0:1.1's "The" at 2.74 s with the pause running to 4.7 s. The aligner therefore takes a unit's *second* word heard as the end of its window, and trusts word **ends**, not starts.
15. **`/Audio/Urantia/Urantia-MH-Audio` is a transcode, not the master.** The 1.7 GB set is the DVD re-encoded at 32 kbps mono: the same 1,629 files, each lagging the disc by the encoder's delay (50.1 ms; 75.1 ms for 22 of them), with no drift, correlating at 0.95–1.00. `tools/align/rebase.py` moved Whisper's word times across, so nothing was heard twice. Every gap it showed (the unread paragraphs, the 118:3.2 splice, `P105_05` running on into 105:6) is in the original too.
16. **A breath can fill the pause before a paragraph.** On the disc audio, 138:10.9's cut fell after "Eight.", because the pause after the number outlasted the breath-filled one before it. A cut may never come after the unit's first word heard has ended; `make align-spotcheck --lists` checks every list paragraph.
17. **`P040_11` and `P041_11` are not sections.** They are second encodes of `_10`, the same length to the millisecond, and `P000_13` is the Acknowledgment (0:12.10–14). `data/audio/mh-overrides.tsv` names all three; a file that fits no rule and no override fails the build.
18. **The Foundation's numbering differs from ours across a section boundary.**
    - It files 139's combined "9 and 10" under 10, so our 139:9.1–11 are its 139:10.1–11.
    - In 144:5 it numbers six separators, not one.
    
    The first survey, which went section by section, counted 95 differences; there are 107. `build/foundation.py` therefore aligns paper by paper.
19. **The 2080 Ti is the display GPU.** Under Whisper it reached 88 °C, against a rated maximum of 89 °C, and throttled to 735 MHz. Compute runs on the 3090: `CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1`.

---

## 8. Decisions on the record

- **One mode.** Reading mode was removed; the study apparatus is always on. The individual elements become switches under **Settings** — red letter, the margin index, paragraph references, the 1955 variants — rather than one coarse lever.
- **Slugs are data, not a function.** `data/slugs.tsv` is checked in and append-only. A headword keeps its slug for ever; collisions get a recorded numeric suffix (11 so far). A permalink that moves because someone improved the slugifier is a broken permalink.
- **An exact headword match wins the search.** bm25 has no notion that a query names an entry, so headwords are resolved separately: exact, then prefix, then full text.
- **Index chips carry concepts, not numbers.** `path_plain` strips the citations and the terminal period; on paper the numbers *are* the entry, on screen the chip is a link.
- **Blanket citations appear once** at the section head, never repeated under every paragraph. This is `read_pack.py`'s rule and the reason Paper 15's 470 citations are readable.
- **Appendices A–F live at `/appendix/A` … `/appendix/F`**, the letters of the printed volume (Tigran, 2026-10-09); `/index/A` was already the A–Z's letter A. An anchor there hashes what a row *is*, a name or an event's date and words, not what it cites, so an added citation moves no link. The three `conjunction of Jupiter and Saturn in Pisces` of 7 B.C. are one text on three dates, and three anchors.
- **An appendix chip never repeats the A–Z** (Tigran, 2026-10-09). A B–F entry stands beside a paragraph only when no entry of the same headword is already there: 131 of 1,865 remain (`CHIP_NEW` in `ubsite/queries.py`). What the other 1,734 carried, the kind of thing a headword names, is on its concept page instead, as "Listed in Appendix C, Celestial Beings, Individuals Named". Every Chronology chip stays, and carries its month: "January 14, 26 A.D.: Jesus baptized by John".
- **The Chronology is the printed list first** (Tigran, 2026-10-09). The log-scale timeline (ROADMAP item 4) is to be built on that page, never in place of it. In print a heading stands above its events and finishes seven of them ("Paul dies prior to", under 82 A.D.). An event's one line, `chronology_event.label`, therefore puts the date after those seven and before the rest, with "of" for a month without a day: "December of 25 A.D.".
- **`/101` redirects to `/101:0`.** Every paper opens with an introduction, and the section list is always in the left rail.
- **The left rail is the whole book, closed but for the paper being read** (Tigran, 2026-10-10). It lists the Foreword, the four parts, every paper and every section, as native `<details>` (`templates/_rail.html`). The part and the paper being read are open, so a reader can jump anywhere without scrolling back up. It is sticky beside the text on a wide screen and the first block of the page on a narrow one, scrolling away with the text (Tigran: "obviously"). **A page carries the tree down to the papers, plus its own paper's sections.** All 1,626 sections inline would add 111 KB raw (22 KB gzipped) to a section page of about 20 KB, and `listen.js` fetches whole pages when it swaps them. As built, the rail adds 22 KB raw, 3.5 KB gzipped. Another paper's sections come from `/rail/N` when it is opened (`ub.js`), asked for under `db_version()`, so the browser keeps them for good and never shows a stale one; `/rail/` is not counted as a visit. With JavaScript off such a paper is a plain link, its chevron hidden (`.lazy`, and the `js` class the head script sets). `ub.js` scrolls the rail, never the page, to put the paper being read a sixth of the way down, again whenever `listen.js` swaps `<main>` (`ub:swap`). Never give the rail's list a class of `tree`: that is the concept page's, and its `li` rule indented every wrapped section title. **A part's title opens the part's own page**, `/part/N` (Tigran, 2026-10-10): its divider as the book prints it, `PART IV`, the title on its printed lines and the sponsors' note, and none of the text. The words come from the press style's `\part<N>txt`, `up`, `mix` and `sub`, read by `readers/press.py` `read_parts` into the `part` table; the chevron beside the title still only opens the part.
- **The footer names its sources** by commit date: `Text (2026-10-03)` and `Index (2026-10-03)`, read from `build_source`. The full SHA and the date are in the tooltip, and the date, not the ID, is the link text. `/healthz` carries the full SHAs too. A dirty build says `(2026-10-03, dirty)`, deliberately ugly; do not deploy one. (Tigran, 2026-10-06, after `2:5.12` went uncited for three days on a stale database.)
- **Each date links to its GitHub commit**, built as `commit_url` from the `url` in `sources.toml`. Both repositories are private, so a public visitor gets a 404. Tigran chose to link them anyway (2026-10-06). `make data` warns `source-not-pushed` when a commit is on no remote branch.
- **The mark is an open book with an amber flame above the gutter** (`ubsite/static/favicon.svg`). Tigran chose it on 2026-10-06 from six candidates (a private comparison page, https://claude.ai/artifact/1RxS33wLdnfTHtejPutER2), after rejecting a first design of two rings and a dot. The one drawing is the tab icon, the home-page logo, and a small mark beside the name in every page's header (kept on the home page too, so the header never shifts). `app.py _mark()` inlines it with its own colours stripped, and `ub.css` colours it from `--link` and `--flame`, so it follows the site's theme switch as well as the system's. Never use the Foundation's concentric circles, which are its trademark. After editing the SVG, run `tools/make_icons.py`; it renders `favicon.ico` and `apple-touch-icon.png` with headless Chrome and ImageMagick.
- **A `\pc` paragraph is marked with a pilcrow** before its first word, faint like the paragraph numbers. It replaced an extra .85rem of space above the paragraph, which nobody could see (Tigran, 2026-10-06). It is the typeface's own ¶ (U+00B6), UB Goudy's with Goudy, as CSS generated content of an empty span: never a character in the text, so copying a paragraph still returns its text exactly. Until 2026-10-08 it was a drawn SVG (one of the logo candidates) used as a mask; Tigran asked why not the Unicode symbol, and the font's own is lighter, matches the face, follows the Typeface setting, and prints, which a mask did not.
- **Settings, per browser, no accounts** (2026-10-07, made a framework 2026-10-08):
  - Reading: Theme (System, Light, Dark; ◐ in the header stays as the shortcut), Text size (90–125% of the root, like zoom), Typeface (the book's Goudy, or the device's own serif or sans, scaled by `font-size-adjust` to Goudy's x-height and given a measure that keeps Goudy's characters per line), Width (Measured, the default: about 68 characters to a line in a 92rem frame; or Full, added 2026-10-10 for Tigran, who minds empty screen more than a long line: no frame and no measure, a rail of up to 24rem so that a paper's title stands on one line, lists in as many columns as fit; the two-column rules sit inside `min-width: 62.01rem`, or they override the phone layout and the page scrolls sideways).
  - Show: red letter, paragraph references, pilcrows, the index in the margin, the 1955 readings.
  - Listening: Merritt Horn, the AI voice, your browser's voice, or Off (Off hides every listening control); which of the browser's voices (its English ones, best first: online, Natural, Premium); Speed; Follow along; Carry on into the next section.
  - **Every setting is declared once, in `ubsite/settings.py`.** The dialog is rendered from it; the head script sets `data-<key>` on `<html>` before first paint for each value that is not its default; `ub.css` keys off that. A new setting is one entry there and one CSS rule. Only values that differ from the default are stored (`ub_settings`), so changing a default reaches everyone who never chose otherwise. A setting that means nothing while another is off (Speed, Follow along and Carry on, with Listening off) is listed in `NEEDS` there, and shown greyed and disabled.
- **Playing stops at the end of a section**, unless Settings' "Carry on into the next section" is on (off by default; added 2026-10-08), when it goes on by itself, across papers, through the whole book. Either way the next section, offered as "Next" or reached by carrying on, is fetched and swapped into the page (`main.reader` and `#ub-audio`, with `pushState`), never loaded as a new page: the same audio element plays on, so no browser asks for another tap, and it works with the screen locked. Back reloads the section it returns to, unless the bar is still open (next point).
- **With Follow along off, playing goes on wherever the reader goes** (Tigran, 2026-10-09). While the bar is open, `listen.js` follows the site's own links, and the search box, inside the page. It fetches the page, swaps its `<main>` (every page has exactly one) and calls `pushState`; Back and Forward work the same way. The document never unloads, so a recording plays on, and so does the browser's voice. The page then shows one section (`P`) while another is heard (`D`).
  - Carrying on at the end of a section moves the page with it only if the page shows the section that has ended.
  - A tap on the reference in the bar brings the paragraph back, fetching its section if the page shows another. Turning Follow along back on does the same.
  - With Follow along on, a link loads a new page and playing stops, as before.
  - Anything unexpected falls back to an ordinary page load: a fetch failure, a response that isn't HTML, a page without `<main>`.
- **Each paragraph is marked with its full reference**, `118:10.13`, not its bare number, so the reader always knows which paragraph this is (Tigran, 2026-10-09). On a desktop it stands in the gutter. On a phone it stands at the start of the paragraph with ▶ under it, like a drop capital, as wide as the section's longest reference (`--refw`, set in `section.html`). Settings' "Paragraph references" (key `paranum`) turns it off.
- **The player's ⏮ does not look at the playhead.** One press restarts the paragraph; two in quick succession (400 ms) go to the one before, and each further quick press goes back one more. Until 2026-10-09 it went back a paragraph within 3 s of the start and restarted otherwise, which seemed inconsistent. The speed opens a small list rather than cycling. A tap on the reference in the bar brings its paragraph into view. Hover is drawn only under `(hover: hover)`, because a touch screen keeps `:hover` on the last element tapped and left ⏮ and ⏭ lit on Android.
- **The browser's own voice is offered beside the recordings, never instead of the recorded AI reading** (Tigran, 2026-10-08, after a student's site read the book with Chrome's "Google UK English Female" and it sounded nearly as good). It costs nothing and needs no storage, but each listener hears whatever their browser has (Google's voices in desktop Chrome, Microsoft's in Edge, Apple's in Safari, eSpeak in Firefox on Linux); nobody can check what it says; and a phone stops it when the screen locks, so `listen.js` holds a screen wake lock while it speaks. A recording plays like a podcast, the same checked reading for everyone. It reads a sentence or so per utterance (≤160 characters, short sentences joined), because Chrome's online voices fall silent partway through long ones; pausing is cancelling, and resumes at the sentence.
- **The AI voice is recorded in advance by a local open model on the 3090**, not by a cloud service: corrections then cost seconds, not a bill, and the weights are pinned. It is chosen by ear from a listening test. It is never a clone of Merritt Horn, it gives the words of Jesus no separate voice, and it is labelled "an AI voice".
- **Bark (Suno) was tried and rejected** (Tigran, 2026-10-07: "horrible"). It reads about 14 seconds per call and then simply stops. Even fed clause by clause, it dropped "in explanation of the meanings" from 0:0.1, paused mid-phrase, and ran at 0.29× real time on the 3090, about 17 days for the book. Its code and its 19 GB of models and venv were removed.
- **Visits are counted server-side, with no IP address kept and no cookie for readers** (Tigran, 2026-10-09). Not Google Analytics, not a script: a page carries nothing for the counter. Each address is placed (country, region, city) and hashed with a salt replaced every UTC day, then dropped; a test greps the database file for the address. So a reader on two days counts as two visits, by design. Every search is recorded with what it found, because the ones that found nothing are a list for the index. `visits.db` stores facts; `stats.py` classifies at report time (bots, referrers, kinds of page), so a better classifier applies to the whole history. A person's view is one whose visitor-day fetched `/static/ub.css` and whose agent is no known bot. Its styles live in `stats.html`, so no reader downloads them. A footer line says so: "Visits are counted without cookies, and no IP address is kept."
- **The API's `ref` is ours; the Foundation's is beside it as `uf_ref`** (Tigran, 2026-10-11). The site, the index and every link use ours. Every translation, and so every site joining its translation to our English, uses the Foundation's, so `/api` tells them to join on `uf_ref`. 0:12.10 has none.
- **The API calls the English text public domain; credit is requested, not required** (Tigran, 2026-10-11). The credit line names the site's own base URL, taken from the request, so it follows the move to urantiabook.org.
- **A text version moves only when something a site receives changes**, and a number, once it may have reached a site, is never made again for other text. So the ledger is append-only, `tests/test_versions.py` holds it to HEAD's as a prefix, and `deploy.sh` refuses to ship while `data/text/` is uncommitted.
- **No 1955 page references in the API** (Tigran, 2026-10-11): they are obsolete. Tigran has asked Vladislav whether he can do without them. Should he need them, the page is in the same `<small>` that `foundation.py` already parses. Adding it is a few lines, and one version in which every record changes.
- **UB Goudy is OFL 1.1** — verified in the name table, a correctly renamed Sorts Mill Goudy derivative — so the site serves the book's own face, subsetted to the corpus with a gate that fails on a missing glyph. **Goudy Handtooled BT is Bitstream proprietary and must never be served.**

---

## 9. Things the editor has asked for, and facts easy to get wrong

- The index is **bound with the text in a single volume** for the seventh printing (third edition, 2026) — *not* a standalone volume. `tools/press/build_press.py` in the press repo: `book | pad | index | pad`, 2,192 pages, fixed by the spine width of an already-printed case.
- Say **"numerous corrections"**, not a number — the count is still moving and prints in October.
- Do not disparage the printed index. It is the achievement this site depends on. An early draft said it "has never been anything but ink" and that was rightly cut.
- The study edition's paragraph numbering was aligned to press on 2026-09-21 (commit `8af25c5`): ten numbered separators de-numbered, and `0:12.10` ACKNOWLEDGMENT restored as a numbered paragraph. Both editions now hold at 14,586 with no gaps.

---

## 10. Open questions

Carried from the plan, none blocking:

1. **Index rights** — publishing 32,837 entries as queryable data is a stronger act than quoting from it. The design keeps an `INDEX_MODE` switch so a change of footing is a config edit.
2. **Site licence** — the press repo is CC BY-NC-SA 4.0, and NC forecloses most of what a public API is for. For the text this is settled: the API serves it as public domain (2026-10-11, §8). The index's footing is still open.
3. **Domain and host**; whether `urantia-library` on this box merges or coexists. Port 80 is reportedly not forwarded, which affects certbot.
4. **The 58 rights-restricted images** — attribution cards, or seek permission.

---

## 11. Where we left off (2026-09-21)

The annotated reader is running and looks right. `make serve` → 8130.

Everything through Phase 5 is committed in seven commits, the last four of which are typography: the site was set too small and wanted 150% browser zoom to be comfortable, which is a Goudy problem — small x-height, long descenders, so it reads a full step below its nominal size.

**One open question, not a defect.** On a concept page the first line of the tree repeats the heading: `/i/adoption` shows "adoption" under the `<h1>` "adoption". On `/i/oaths` the same line reads "oaths. *See also* promises" and earns its place, because the level-1 entry carries citations and cross-references. Suppressing it when it adds nothing was offered and not yet ruled on.

**Next is Phase 6**, the study-edition apparatus, and it is the largest remaining import: 307 `\fnst` study footnotes, 54 human-source `\bibitem` records, 86 `\bibref` cross-references, the whole KJV (24,974 verses + 5,069 marginal notes), 819 quiz questions (**83 of them multi-answer** — a single-answer model marks correct responses wrong), and 84 figures of which **58 are rights-restricted** and must be separable at query time.

Note when starting it: the study edition's own `tools/extracttext.py` truncates about two thirds of its footnotes (`[^}]+` against braces nested three deep), and `\tunemarkup` there means the opposite of what it means in press — see §7.

The plan's later phases (human sources, chronology and map, deploy) are unchanged; read them in the plan file rather than duplicating them here, and `ROADMAP.md` for why each is worth doing.

---

## 12. Listening — where we left off (2026-10-08)

**Live on pi5 since 2026-10-08:** Merritt Horn's reading (the Uversa Press DVD, aligned to every paragraph), the Settings framework, "Carry on into the next section", and your browser's voice. Every gate passes.

**Not done, and decided: the recorded AI reading.** The browser's voice is a stopgap; the AI reading is still to be made, once, carefully (Tigran: "we are doing this only once, there is no rush, so we should make sure there are no errors in the final audio").

- **The voice is chosen:** `higgs3_mature`, Higgs TTS 3 through vLLM-Omni, cloned from `var/tts/refs/higgs2_mature_clean.wav` (a Higgs v2 *described* synthetic voice, its mains hum notched out). Never Merritt Horn's voice.
- **The pipeline is built:** `make tts` → `tools/tts/book.py`, which uses `higgs3.py`, `chunk.py`, `listen.py` and `store.py`. It makes every piece, checks it for faults, has Whisper hear it back, retries up to eight seeds, and assembles one MP3 per section into `var/audio/ai/higgs3_mature/` and `data/audio/ai*.tsv`. About 27 GPU hours on the 3090, resumable. The README's "The AI voice" covers it.
- **The trial is done:** Papers 1, 30 and 144 (`book.py --papers 1 30 144`, written to `var/tts/trial/`, never `data/`). All 1,051 pieces were heard as written.
- **The user is listening to the trial** on a private page with a mark-a-problem button, https://claude.ai/artifact/9ds9dYRRAgb3fdiSKkiNLY. Read the marks with `ArtifactData list`, collection `marks`. The one mark so far (1:0.2, "could beings") exposed a listener bug, which is fixed.
- **Next session:**
  1. Read the marks and fix what they show.
  2. Ask for the user's verdict on Paper 1. **Do not start the whole-book run before they approve it.**
  3. `make tts`, watched; then review `data/audio/ai-unsettled.tsv`.
  4. `make data` and `make check`, which picks up the `ai` source.
  5. `./deploy/deploy.sh --audio`, only when asked.

  Until `ai.tsv` exists, `make data` warns `audio-ai-unmade`, and the site offers Merritt Horn and the browser's voice. The plan is `~/.claude/plans/have-a-look-at-fancy-sketch.md`; the session-by-session detail is in memory (`audio-feature.md`).
