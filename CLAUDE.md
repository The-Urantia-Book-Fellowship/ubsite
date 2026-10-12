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
make data           build var/ub.db          (~20 s)
make check          every gate               (~8 s; rebuilds the oracles first)
make epub           the whole site as an EPUB -> var/epub/  (~3 s, ~10 s more for its gates)
make test           the never-write-to-a-master guards
make paranoid       fingerprint all three trees, build, and prove nothing moved
make srt-snapshot   refetch the SRT Committee's page into data/srt/ (review the diff)
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
- **The text API** (2026-10-11). `/api/v1` lets other sites keep their copy of the English text in step with ours, and `/api` documents it, with a client in Python.
  - **The protocol is a text version.** A site keeps the number it was sent and asks `/api/v1/text?since=N`. It gets every record new or changed since N, the keys of any removed, and the new number. From 0 it gets the whole text, 3 MB gzipped.
  - **A record** is a part, a paper, a section or a paragraph, each with a hash. A paragraph also has `html`, `uf_ref`, `page_1955`, `separator_before` and `group_before`. The `html` is `render.py`'s, without the note markers.
  - **`build/versions.py`** keeps the versions in an append-only ledger, `data/text/`, because `ub.db` remembers no earlier build. The ledger is appended only after a build passes.
  - **`build/foundation.py`** gives every paragraph and section the Foundation's reference, `uf_ref`. It reads its SRT HTML (the zip in the press repo) and aligns it with ours paper by paper. Its differences must be exactly `tests/known-uf-refs.tsv`.
  - **`ubsite/api.py`** only concatenates stored records. Each worker gzips a reply once. Replies carry an ETag, so an unchanged one is a 304, and `Access-Control-Allow-Origin: *`.
  - **Calls are counted apart from views**, in `api_call` in `visits.db`. `/stats` lists each caller by its User-Agent.
- **The 1955 readings and their reasons** (2026-10-12). Each `\fnc` is a small ring above the words that changed; a click opens a card under the line with the 1955 reading **as the press gives it** and the **SRT Committee's decision and reasons**. The margin holds the index alone. **Only the press says what 1955 printed** (Tigran, 2026-10-12): the committee's page has errors of its own, in quoting 1955 among them (trap 21), so it supplies its reasons, under its name, and nothing else. Its quotation of the 1955 text pairs a note with its entry and is never shown.
  - `tools/srt/snapshot.py` (`make srt-snapshot`) keeps the two tables of the Fellowship's page (`sources.toml [srt]`) in `data/srt/considerations.html`, verbatim, with the URL, fetch time and page hash in its header. The build reads the snapshot, never the network, and records it in `build_source` as `srt`.
  - `build/srt.py` reads it into `srt_item`, one row per change (an entry may hold several: 134:3.3 has three), maps the page's references (the Foundation's numbering) to ours through `uf_paragraph`, rewrites its links to our paragraphs, and pairs each note with its change (`footnote.srt_item_id`). What does not pair one to one is exactly `tests/known-srt-deltas.tsv`.
  - `section.html` puts the notes after the text as endnotes (what a reader sees without JavaScript, and in print); `ub.js` opens each as a card at its ring, positioned in `<article>` so it scrolls with the text. `ubsite/queries.py` decides what a note shows, for the site and the EPUB alike.
  - **Search finds them too** (Tigran, 2026-10-12), by the reading and by the reasons its card shows: `footnote_fts` (`004_fts.sql`, filled by `derive.fts`), one row per note, never the committee's quotation of 1955 and none of its entries that have no note. `/search` lists the hits as "In the 1955 readings": the reading, today's words around the ring, the committee's words where they matched, and a link, `/93:5.8#note93_5_8_0`, that lands on the paragraph with the card open (`#note`, not the ring's own `#fnref`, which the browser would scroll to itself, over `ub.js`). The list is always sent and shown only when Settings' "1955 readings in search results" is on (off by default), so no setting reaches the server. 48 readings hold a word today's text never uses: *Badanon*, *Tannach*, *forego*, *commerical*.
  - **The List of 1955 readings**, `/lists/1955` (Tigran, 2026-10-12): all 180 by paper, each with its reading, today's words around the ring, and the committee's verdict. Its rings are the text's own `a.fn` and open the same card in place, and so do the rings among the search results: `ub.js` frames a card in `main.results` where there is no `<article>`. A note is selected once, by **`queries.notes()`**, for a section, the list, a search and the EPUB, and drawn once, by `templates/_note.html`; a list line is `templates/_old.html`. The list keeps its rings with the readings turned off in the text, because a reader asked for it.
- **Justified, hyphenated where the book hyphenates** (2026-10-12). The text is set justified, and a word breaks at a line's end only where the press lets it. `build/hyphen.py` runs the press's own model: Knuth's `hyphen.tex` (vendored from TeX Live, `vendor/tex/`), hyphenmins 2/3, the 523 entries of `tex/urantia-hyphen-en.tex`, and the source's 1,392 `\-`, which the expander now keeps as zero-width `shy` spans. `paragraph.html_hy` is `paragraph.html` with a U+00AD at each of those points, and only the section page uses it. `html`, the API and the EPUB are byte-identical to before, so the text version did not move.
  - `build/checks/check_hyphen.py` gates it: removing every U+00AD gives `html`; every `\-` is kept; nothing breaks under the minimums; every listed word breaks as its entry says.
  - `tools/hyphen_print.py` holds it to a built PDF of the book. On 2026-10-12 all 23,494 breaks printed in words of the text were offered, against 1,217 missed with the patterns alone. It is not a gate, because the PDF can be stale (§5).
  - Ragged right is a setting (§8). Chrome copies soft hyphens, so `ub.js` takes them out of the selected text for the moment of a copy and puts them back before the next paint. The copy is then the browser's own: plain text and HTML, with its styles, byte-identical to a copy from the page without them (checked 2026-10-12: one paragraph, three with the margin between, part of a word, red letter with a 1955 ring, dot-leader rows, verse, the whole page).
- `deploy/` — the systemd unit, the nginx server block, the sudoers drop-in and `deploy.sh`, with a README naming the four steps that need root. All four have been run; the site is live at **https://ubsite.ddns.net**. **The database is the artifact**: the three source repos are not on pi5 and do not need to be, so `make data` runs here and `var/ub.db` is shipped.

Next: Phase 6 (the study-edition apparatus — `\fnst` notes, KJV, the quiz, figures behind the rights gate), then 7 (human sources), 8 (the timeline, the map).

---

## 4. The numbers

Every asserted number lives in `verify/expectations.toml` with `measured_on` and `source_commit`, **never in code**. `verify/exceptions.toml` is currently empty and should stay that way.

```
papers 197 · sections 1,626 · paragraphs 14,586
separators 11 (3 of five stars, 8 of three) · the Foundation's 10 at the same places, all but 119:8.9
red-letter spans 1,267 · em spans 2,295 · 1955 variant notes 180
index entries 34,751 (32,964 A–Z + 1,351 appendix + 436 chronology events)
citations 39,885 → 50,842 targets {para 47,954, sec 2,254, paper 634}
cross-references 5,133 See/See also + 1,026 q.v., 0 dangling · headwords 4,736
B–F names that are A–Z headwords 1,332 · para_citers 113,992 · cocitation pairs 9,719
paragraphs the Foundation numbers otherwise 106 · text API records 16,413, at version 5 (2026-10-12)
SRT changes considered 319 (303 entries) · 1955 notes with the committee's reason 167 of 180 (2026-10-12)
soft hyphens 530,865, of them the source's \- 1,392 (press 806c7ac, 2026-10-12)
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
    - Its HTML marks the eleven entries it prints without a reference with an F after the id (`U0_12_10F`): ten `* * *` separators and the ACKNOWLEDGMENT. Seven separators take a number of their own (134:6, and six in 144:5), three repeat the number before them (after 31:10.21, 56:10.22 and 120:3.11), and the ACKNOWLEDGMENT takes 0:12.10, as ours does. Its page, 16.7, is the place its neighbours leave, and the 1955 plates (page 16) confirm it. Until 2026-10-12 the reader skipped all eleven, and `/api` said the Foundation did not number the ACKNOWLEDGMENT.

    The first survey, which went section by section, counted 95 differences; there are 106. `build/foundation.py` therefore aligns paper by paper.
19. **nginx's `location /api/` answers `/api` with a 301 to `/api/`.** It does that for any prefix location that ends in a slash and has `proxy_pass`. The app redirects `/api/` back to `/api` with a 307, so the docs page was a redirect loop that the rate limit ended with a 429, and no test of the app can see it. `location = /api` in `deploy/ubsite.nginx` is the fix. Try a page through nginx itself after changing a location.
20. **The 2080 Ti is the display GPU.** Under Whisper it reached 88 °C, against a rated maximum of 89 °C, and throttled to 735 MHz. Compute runs on the 3090: `CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1`.
21. **The SRT Committee's page has slips of its own, and the build trusts none of them silently.**
    - A link's words and its anchor can disagree: 136:3.5's "See SRT note for 24:1.11" points at 24:1.1, and 46:5.24's "73:7.4" points at a 73:0.4 that does not exist. The words are followed.
    - Its "120:1.1" entry is the Part IV sponsors' note.
    - It misquotes the 1955 text. 85:4.1 has its "1955 text" and "Review" swapped: the printing reads "Greeks", and "Creeks" was only proposed. Its 90:2.9 quotes *Teuskwatawa* where the printing, and the press note, have *Teuskwatowa*.
    - It lists places a name occurs as if each were a change: five *Caesarea Philippi* rows, where the 1955 printing already has the hyphen.

    Each of these is a line in `tests/known-srt-deltas.tsv`. **Never call a disagreement between the page and the press a press error without the 1955 printing itself:** the Guardian plates are in the press repo (`The-Urantia-Book-1955-Guardian-Plates-600dpi.djvu`, no text layer; book page N is djvu page N+66, `ddjvu` and `tesseract` read it). On 2026-10-12 three such "press gaps" were reported to Tigran from the page alone, and all three were the page's errors.
22. **pyphen is not the book's hyphenation, nor is any browser's.** The press sets the text with polyglossia `english`, which is Knuth's original `hyphen.tex`, not `hyph-en-us`. pyphen's `en_US` is LibreOffice's dictionary, which is also Firefox's, and it disagrees with 387 of the press list's 523 entries (`su-per-crea-t-u-ral`, `mo-ron-ti-aize`). Two further CSS facts:
    - A soft hyphen is honoured by `hyphens: manual`, the **initial** value. Only `hyphens: none` silences it, which is how Ragged right turns them off.
    - Chrome puts U+00AD on the clipboard with the text it copies (checked in Chrome 154). Building the clipboard's contents in a `copy` handler instead loses the inline styles the browser adds to its HTML, and with them the red letter in a paste into Docs or Word. So `ub.js` removes the hyphens from the DOM with `deleteData`, which the selection's ends follow, and restores them in `requestAnimationFrame`. A microtask would run before the browser copies.

---

## 8. Decisions on the record

- **One mode.** Reading mode was removed; the study apparatus is always on. The individual elements become switches under **Settings** — red letter, the margin index, paragraph references, the 1955 variants — rather than one coarse lever.
- **Slugs are data, not a function.** `data/slugs.tsv` is checked in and append-only. A headword keeps its slug for ever; collisions get a recorded numeric suffix (11 so far). A permalink that moves because someone improved the slugifier is a broken permalink.
- **An exact headword match wins the search.** bm25 has no notion that a query names an entry, so headwords are resolved separately: exact, then prefix, then full text.
- **Index chips carry concepts, not numbers.** `path_plain` strips the citations and the terminal period; on paper the numbers *are* the entry, on screen the chip is a link.
- **Blanket citations appear once** at the section head, never repeated under every paragraph. This is `read_pack.py`'s rule and the reason Paper 15's 470 citations are readable.
- **The edition's lists live under `/lists`** (Tigran, 2026-10-12), as a book's front matter names them: "List of 1955 readings" at `/lists/1955` now, the illustrations and the study notes with Phase 6. `/lists` names them all, and the home page links to them in one line.
- **Appendices A–F live at `/appendix/A` … `/appendix/F`**, the letters of the printed volume (Tigran, 2026-10-09); `/index/A` was already the A–Z's letter A. An anchor there hashes what a row *is*, a name or an event's date and words, not what it cites, so an added citation moves no link. The three `conjunction of Jupiter and Saturn in Pisces` of 7 B.C. are one text on three dates, and three anchors.
- **An appendix chip never repeats the A–Z** (Tigran, 2026-10-09). A B–F entry stands beside a paragraph only when no entry of the same headword is already there: 131 of 1,865 remain (`CHIP_NEW` in `ubsite/queries.py`). What the other 1,734 carried, the kind of thing a headword names, is on its concept page instead, as "Listed in Appendix C, Celestial Beings, Individuals Named". Every Chronology chip stays, and carries its month: "January 14, 26 A.D.: Jesus baptized by John".
- **A link is grey around the reading and blue where going somewhere is the page's job** (Tigran, 2026-10-12). Grey: the header, the rail, the margin index, the box of entries cited across a section, all on screen the whole time. Blue: the Contents page, the index's letters, the Chronology's periods, "next ›", and the row at the top of each appendix (`_appnav.html`). That row was grey like the header until 2026-10-12, so on a phone, with no hover, its letters read as a caption; each letter is now padded to a thumb's width. The concept page's "Listed in Appendix C, …" stays grey: it is a statement about the headword, and the link is extra.
- **The Chronology is the printed list first** (Tigran, 2026-10-09). The log-scale timeline (ROADMAP item 4) is to be built on that page, never in place of it. In print a heading stands above its events and finishes seven of them ("Paul dies prior to", under 82 A.D.). An event's one line, `chronology_event.label`, therefore puts the date after those seven and before the rest, with "of" for a month without a day: "December of 25 A.D.".
- **`/101` redirects to `/101:0`.** Every paper opens with an introduction, and the section list is always in the left rail.
- **The text is justified, as the book is, and breaks a word only where the book does** (Tigran, 2026-10-12, choosing the book's own hyphenation over pyphen's or the browser's). Settings' Alignment is Justified by default, or Ragged right (key `align`), because WCAG 1.4.8 asks for a way to unjustified text. The 144 verse lines stay start-aligned (`p.t.verse`), and 0:12.10 stays centred.
  - **A browser is not TeX.** It fills each line greedily and has no penalty for a hyphen, or for two running, so loose lines and more hyphens than print are the price, worst on a phone. Safari alone takes `-webkit-hyphenate-limit-lines: 1`.
  - **The EPUB is still unhyphenated.** It follows once Tigran has looked at the site; its gates and the font subset will need U+00AD (the subset already has it, with U+2010).
- **A dot-leader row is split at its leader on the section page** (2026-10-12). `section.html` makes it a `.leadrow` flex line of the words (`.lab`) and the figure (`.fig`, which begins with the dots); the paragraph around it is an ordinary block. So its reference and ▶ stand as every other paragraph's do, and a row too long for its line breaks before the figure, dots and all, at any width. Before this, the paragraph itself was the flex line:
  - on a phone the reference and ▶ stood side by side and pushed 15:2's long rows past the screen, and the phone's `1fr` column grew with them, taking the whole section along. That column is now `minmax(0, 1fr)`.
  - once the text was justified, the words of a long row were spread across it.
  - `check_db` holds every leader outside all other spans, one to a paragraph, so that each half is whole HTML. The stored text, the API and the EPUB are untouched.
- **A paper's head is centred, as the book sets it** (Tigran, 2026-10-12): its number, title and author, the section's title, and the Listen button under them. It is as wide as the text column, never the margin as well, so it is centred over the text in both Widths. So is 0:12.10 ACKNOWLEDGMENT, the one heading within the text: the press reader marks it `paragraph.heading` from its `\hspace*{0.15\columnwidth}`, and a gate holds it to that one paragraph. An introduction has no title over its text; the left rail names it "0. Introduction", numbered as a reference like 13:0.2 numbers it.
- **The left rail is the whole book, closed but for the paper being read** (Tigran, 2026-10-10). It lists the Foreword, the four parts, every paper and every section, as native `<details>` (`templates/_rail.html`). The part and the paper being read are open, so a reader can jump anywhere without scrolling back up. It is sticky beside the text on a wide screen and the first block of the page on a narrow one, scrolling away with the text (Tigran: "obviously"). **A page carries the tree down to the papers, plus its own paper's sections.** All 1,626 sections inline would add 111 KB raw (22 KB gzipped) to a section page of about 20 KB, and `listen.js` fetches whole pages when it swaps them. As built, the rail adds 22 KB raw, 3.5 KB gzipped. Another paper's sections come from `/rail/N` when it is opened (`ub.js`), asked for under `db_version()`, so the browser keeps them for good and never shows a stale one; `/rail/` is not counted as a visit. With JavaScript off such a paper is a plain link, its chevron hidden (`.lazy`, and the `js` class the head script sets). `ub.js` scrolls the rail, never the page, to put the paper being read a sixth of the way down, again whenever `listen.js` swaps `<main>` (`ub:swap`). Never give the rail's list a class of `tree`: that is the concept page's, and its `li` rule indented every wrapped section title. **A part's title opens the part's own page**, `/part/N` (Tigran, 2026-10-10): its divider as the book prints it, `PART IV`, the title on its printed lines and the sponsors' note, and none of the text. The words come from the press style's `\part<N>txt`, `up`, `mix` and `sub`, read by `readers/press.py` `read_parts` into the `part` table; the chevron beside the title still only opens the part.
- **The footer names its sources** by commit date: `Text (2026-10-03)` and `Index (2026-10-03)`, read from `build_source`. The full SHA and the date are in the tooltip, and the date, not the ID, is the link text. `/healthz` carries the full SHAs too. A dirty build says `(2026-10-03, dirty)`, deliberately ugly; do not deploy one. (Tigran, 2026-10-06, after `2:5.12` went uncited for three days on a stale database.)
- **Each date links to its GitHub commit**, built as `commit_url` from the `url` in `sources.toml`. Both repositories are private, so a public visitor gets a 404. Tigran chose to link them anyway (2026-10-06). `make data` warns `source-not-pushed` when a commit is on no remote branch.
- **The mark is an open book with an amber flame above the gutter** (`ubsite/static/favicon.svg`). Tigran chose it on 2026-10-06 from six candidates (a private comparison page, https://claude.ai/artifact/1RxS33wLdnfTHtejPutER2), after rejecting a first design of two rings and a dot. The one drawing is the tab icon, the home-page logo, and a small mark beside the name in every page's header (kept on the home page too, so the header never shifts). `app.py _mark()` inlines it with its own colours stripped, and `ub.css` colours it from `--link` and `--flame`, so it follows the site's theme switch as well as the system's. Never use the Foundation's concentric circles, which are its trademark. After editing the SVG, run `tools/make_icons.py`; it renders `favicon.ico` and `apple-touch-icon.png` with headless Chrome and ImageMagick.
- **A separator is drawn where the press prints one** (Tigran, 2026-10-12, on finding that the site showed none). The press sets eleven: `\separatorline`, five stars set wider, before the closing notes of Parts I–III (31:10.22, 56:10.23, 119:8.9), and `\separatorshort`, three, in 120:3, 134:6 and six times between the prayers of 144:5. Until 2026-10-12 `readers/press.py` skipped them as layout. Each is now kept on the paragraph after it, `paragraph.sep_before`, and `build/foundation.py` holds them to the Foundation's ten: the same places and stars, but 119:8.9, which is the press's own (`tests/known-separator-deltas.tsv`).
  - The section page draws each as a row of its own across the grid, laid on the grid's columns (`subgrid`), so the stars stand centred over the text column, at every width and with the margin off. They are generated content (`.stars`), like the pilcrow, so a copy never takes them. The EPUB has them as real text.
  - **The API sends each as `separator_before`** on the paragraph after it (version 5, below). Whether the edition takes the Foundation's numbering for the separators and for 139:9–10 is not decided (see trap 18).
- **A `\pc` paragraph is marked with a pilcrow** before its first word, faint like the paragraph numbers. It replaced an extra .85rem of space above the paragraph, which nobody could see (Tigran, 2026-10-06). It is the typeface's own ¶ (U+00B6), UB Goudy's with Goudy, as CSS generated content of an empty span: never a character in the text, so copying a paragraph still returns its text exactly. Until 2026-10-08 it was a drawn SVG (one of the logo candidates) used as a mask; Tigran asked why not the Unicode symbol, and the font's own is lighter, matches the face, follows the Typeface setting, and prints, which a mask did not. The API sends it as `group_before` (version 5).
- **Settings, per browser, no accounts** (2026-10-07, made a framework 2026-10-08):
  - Reading: Theme (System, Light, Dark; ◐ in the header stays as the shortcut), Text size (90–125% of the root, like zoom), Line spacing (added 2026-10-12 for Tigran, who found the text's 1.55 too open, worst on a phone; **the book's text**, `p.t`, and a 1955 reading's card and endnote, read as the text is, "not the whole site's UI", which is set at 1.4 and no setting moves: 1.05, 1.1 (the printed book's 10 on 11, measured from its PDF), 1.25 the default, and 1.45, each drawn as three bars; a 1955 reading's ring stands in the descenders of the line above, so it comes down by `max(0, 1.29 − --line)` em, `--line` being the leading of the text it stands in (none in the list or search), keeping about a pixel clear of the deepest (all 180 photographed at every step, none nearer than 1 px; https://claude.ai/artifact/X46iyWpkiBf2e2oqVnayjM); the gutter's reference, ▶ and 1955 page were placed for 1.55 and move by `--dl`, the difference, which Playwright held to within a pixel of 1.55's placing at every width, size and typeface; the space between paragraphs does not change), Typeface (the book's Goudy, or the device's own serif or sans, scaled by `font-size-adjust` to Goudy's x-height and given a measure that keeps Goudy's characters per line), Width (Measured, the default: about 68 characters to a line in a 92rem frame; or Full, added 2026-10-10 for Tigran, who minds empty screen more than a long line: no frame and no measure, a rail of up to 24rem so that a paper's title stands on one line, lists in as many columns as fit; the two-column rules sit inside `min-width: 62.01rem`, or they override the phone layout and the page scrolls sideways).
  - Show: red letter, paragraph references, the 1955 page references (off by default), pilcrows, the index in the margin, the 1955 readings, and those readings in search results (off by default). The labels are bare noun phrases, "Words of Jesus in red" and "1955 readings" among them, with no article (Tigran, 2026-10-12).
  - Listening: Merritt Horn, the AI voice, your browser's voice, or Off (Off hides every listening control); which of the browser's voices (its English ones, best first: online, Natural, Premium); Speed; Follow along; Carry on into the next section.
  - **Every setting is declared once, in `ubsite/settings.py`.** The dialog is rendered from it; the head script sets `data-<key>` on `<html>` before first paint for each value that is not its default; `ub.css` keys off that. A new setting is one entry there and one CSS rule. Only values that differ from the default are stored (`ub_settings`), so changing a default reaches everyone who never chose otherwise. A setting that means nothing while another is off (Speed, Follow along and Carry on, with Listening off) is listed in `NEEDS` there, and shown greyed and disabled; so is "1955 readings in search results" while the 1955 readings are off.
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
- **The API's `ref` is ours; the Foundation's is beside it as `uf_ref`** (Tigran, 2026-10-11). The site, the index and every link use ours. Every translation, and so every site joining its translation to our English, uses the Foundation's, so `/api` tells them to join on `uf_ref`. 0:12.10 is 0:12.10 in both: the Foundation prints no number beside it, and its 1955 page, 16.7, is the place its neighbours leave (text version 4, 2026-10-12).
- **The API calls the English text public domain; credit is requested, not required** (Tigran, 2026-10-11). The credit line names the site's own base URL, taken from the request, so it follows the move to urantiabook.org.
- **A paragraph is sent as HTML alone, with no plain copy beside it** (Tigran, 2026-10-11). Stripping its tags gives the text exactly, which `check_db` holds, and the text has no `&`, `<` or `>` to unescape. A second copy saved consumers one regex, cost 0.33 MB gzipped, and could in principle disagree with the first. Dropping it made version 2.
- **A text version moves only when something a site receives changes**, and a number, once it may have reached a site, is never made again for other text. So the ledger is append-only, `tests/test_versions.py` holds it to HEAD's as a prefix, and `deploy.sh` refuses to ship while `data/text/` is uncommitted.
- **A 1955 reading is a ring and a card, with the committee's reasons** (Tigran, 2026-10-11 and 12). He chose them from a mockup (https://claude.ai/artifact/8mCnzY2KhkrjqL5JqEuCi4):
  - **The card** opens at the ring: style A. Others offered were a column-wide card, a bottom sheet and inline.
  - **The ring** is "Smallest", in link blue, drawn by CSS (`a.fn::after`) so copying never takes it. It is an inline of font size 0 whose padding and border make the circle, holding a word joiner (U+2060), sized by `--ring` (`@property`, the text's em). It was an inline-block until 2026-10-12, and a browser may break a line before one wherever it stands: eight rings stood alone at the start of a line ("en route", 30:3.12). Now no line breaks beside it, at any width or spacing. `build/fonts.py` reads a CSS escape as its character and lists U+2060 in `ELSEWHERE`.
  - **The reasons** come in full from the SRT Committee's page, as a snapshot, and **only the reasons**: the page has errors of its own (trap 21), so the 1955 reading in the card is the press's note, never the page's quotation of 1955.
  - **What is left out:** the committee's entries where the text was kept as printed. They have no note here.
  - **The six italics-only notes** lost the site's own wording ("the semicolon is upright in 1955, italic here", `footnote.gloss`), because the committee explains each of them. `build/variants.py` now only checks that a note differs from the text.
  - **The EPUB** carries the same words, offline: links out of the book become text, and the credit reads "SRT Committee, urantiabook.org/SRT".
  - **Study-edition notes**, numbered, will use the same mechanism (Phase 6).
- **The 1955 page references are in the API and on the site, and off on the site unless a reader asks** (Tigran, 2026-10-11). They are obsolete as a way to cite the book, but other sites and older literature still use them. `foundation.py` takes each from the Foundation's HTML with its reference, as `uf_paragraph.page` (`"1109.3"`, page then paragraph on it). `check_db` requires them to run forward through the book. The API sends `page_1955`, which made text version 3. Settings' "1955 page references" (key `pages`, default off) shows them in the gutter, on the reference's second line with the play button beside it, or third in the stack on a phone. They are drawn from `data-pg`, like the pilcrow, so copying never takes them along.
- **A paragraph record says what stands before it** (Tigran, 2026-10-12): `separator_before`, the stars of a separator (`"* * *"`, `"* * * * *"`, else `null`), and `group_before`, whether it begins a 1955 group, the site's ¶ (`true` or `false`). Both are on every record, so that every record has one shape. They made text version 5, which sent all 14,586 paragraphs again, so the API, a day old, would carry everything the site shows before any more sites held a copy. `check_db`'s record round-trip holds both to the database.
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
