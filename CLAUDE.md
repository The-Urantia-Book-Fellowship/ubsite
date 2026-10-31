# ubsite

An interactive presentation of the Urantia revelation: the Uversa Press text read together with the Uversa Press index, so that the index works in both directions — from a concept into the text, and from any paragraph back to everything the index says about it.

The plan this was built from is `~/.claude/plans/have-a-look-at-fluttering-peacock.md`. `ROADMAP.md` beside this file is the survey of what the data makes possible — seventeen ideas ranked, with what to build and what deliberately not to.

Read §0 and §1 here first. Before changing a feature, read its section of `ARCHITECTURE.md`, how it is built, and its group in `DECISIONS.md`, what was chosen and why: §3 and §8 here are their maps. `ROADMAP.md` is where this is going, the plan the phase-by-phase detail, and `ChangeLog.md` what has changed, which is also the site's What's new (§8).

---

## 0. The one thing to understand

**The product is the database.** The website, a future API, and any export are views over `var/ub.db`. Three LaTeX projects are read, verified against independent evidence, and loaded into one queryable store, with the translations beside the text since 2026-10-26. If you are tempted to put logic in a template or a route that belongs in the build, don't.

The second thing: **the source repos are masters and are never written to**, the translations' among them. Not their `tex/`, not even their gitignored derived directories. This is enforced mechanically, not by good intentions — see §6.

---

## 1. The sources

Paths live in `sources.toml` and **nowhere else**; `build/config.py` is the only module that reads it.

| key | repo | what it supplies |
|---|---|---|
| `press` | `../urantia-uversa-press-claude` | the authoritative text |
| `study` | `../urantia-study-edition` | apparatus: footnotes, human sources, KJV, quiz, images. Its notes reach the site one reviewed paper at a time (`ARCHITECTURE.md`, Study notes), and its quiz whole, its references one reviewed paper at a time (`ARCHITECTURE.md`, The quiz); the rest is not yet imported |
| `index` | `../index` | the Uversa Press index, revised for the third edition |
| `block` | `../block-sources` | Matthew Block's parallel charts of the human sources, one PDF per paper, and `MANIFEST.tsv` naming each chart's address, its version. No git; kept by `../explore-tools/block_fetch.py`. The build reads the manifest and `originals/LIBRARY.tsv`, `tools/study/` the PDFs. Its `originals/`, kept by hand, holds the works themselves where a note was checked against one, each with its official address in `originals/MANIFEST.tsv`, and in `originals/LIBRARY.tsv` the works checked in Tigran's own copies in `/Books`, by path, SHA-256 and their page in his library at ulib.sigmaai.au (sigmaai.au/library until 2026-10-25), with whether a reader who has not logged in can open it (`public`) |
| `ud` | `../ud` | Tigran's own Russian translation, «Урантийские документы», with notes of his own (`\fnst`): Papers 0–40, and 41, 43, 195 and 196 in part. GPL v3. Read at HEAD |
| `urantia-ru` | `../urantia-ru` | the late Lila Dogim's Russian translation, with Sergey Prokopov's corrections, as the Urantia Book Society of Greater New York publishes it (urantia.nyc): the whole book, no notes. Read at HEAD |
| `uf-ru` | `../urantia-rus/misc/uf-rus-001-1997-1.5-html.zip` | the Urantia Foundation's own Russian translation, its 2024 release, as its HTML: the whole book. A zip, fixed by SHA-256 and text id; `../urantia-rus`'s old TeX is never read. Shown by the Foundation's written permission |
| `audio.mh` | `/Audio/Urantia/Urantia-MH-Audio-DVD` | Merritt Horn's reading, one MP3 per section, 121 h, as on the Uversa Press DVD (2006): 128 kbps stereo, 44.1 kHz. On pi5 too, same path |

All three share one address space: the `\vs` macro addresses `\vs p133 1:3` (a Urantia paragraph) and `\vs Gen 1:1` (a Bible verse) alike.

The index is read **at HEAD** and the revision recorded in the build, because that repo is under active editorial work. Count gates against it are therefore reported bands; structural gates stay hard.

Until 2026-10-06 the first half of that was not true. The readers opened the working tree, while `config` reported HEAD as clean. Now `config` resolves `rev` to one SHA (`at`), `_io.read_tex` reads `tex/` at it, and `build_source` records it. `tests/test_read_tex.py` proves that worktree edits do not get through.

The study edition is read at HEAD too, since 2026-10-18, when its notes began to reach the site (`_io.read_tex_many`, one `git cat-file --batch` for all 197 papers), and so are the translations, since 2026-10-26: a translator's uncommitted paragraph never reaches the site. The Foundation's is a release, read from its zip, whose digest stands where a commit does.

Careful: there are three `urantia-study-edition` trees on this machine. `urantia-study-edition-latest` is the **oldest**. `sources.toml` pins the right one.

---

## 2. Commands

```
make venv           create .venv (uv) and sync requirements-dev.txt -- run this first
make lock           recompile requirements.txt and requirements-dev.txt from their .in files
make sources        the three repos and the revisions in use
make vendor-check   re-hash the vendored copies against upstream (fails with a diff)
make data           build var/ub.db          (~30 s)
make check          every gate               (~8 s; rebuilds the oracles first)
make offline        the copy Work offline keeps -> var/offline/  (~22 s, ~20 s more for its gates; needs Node)
make e2e            make offline, then Work offline end to end in Chrome  (~2 min more)
make test           the never-write-to-a-master guards
make paranoid       fingerprint every source tree, build, and prove nothing moved
make srt-snapshot   refetch the SRT Committee's page into data/srt/ (review the diff)
make serve          the reader on 127.0.0.1:8130 (HOST=0.0.0.0 to reach it from a phone)
make stop           stop it (by pid — never by pattern, see §6)

make align-transcribe   Whisper over the recordings, 3090 only (~1.5 h, resumable)
make align / align-repair   cut them at the paragraph -> data/audio/mh.tsv
make tts-bakeoff        the AI-voice listening test -> var/tts/bakeoff/
make tts                the whole book in the AI voice, 3090 only (~27 h, resumable)
make tts-assemble       one MP3 per section from what has been made -> data/audio/ai*.tsv

.venv/bin/python tools/study/draft.py N   a paper's study notes drafted for review -> var/study/
```

The ML environments (`venv-align`, `venv-tts`, `venv-chatterbox`, `venv-higgs`, `venv-vllm`) and their caches live in **`~/Software/ml`**, on the NVMe home, never in `requirements.txt` and never on `/Audio`. They are for the audio work on the GPU **and nothing else** (Tigran, 2026-10-16): a general tool's dependencies go in `.venv`, or are fetched into the tree by URL and digest (the SQLite release). TeX Live 2026 and Node 24 stay system installs; README, "What this machine needs besides". Playwright was in a `venv-browser` there until that day; it is now in `requirements-dev.in`.

`make data` never edits in place: it builds `var/ub.db.tmp` and swaps it in, so a failed build leaves the previous database untouched.

**Updating the live site and deploying it** is a fixed procedure, and it lives in `README.md`, not here: is pi5 behind, vendor drift, build, gate, look, commit, `./deploy/deploy.sh`, verify.

---

## 3. What is built

**Phases 0–5 are done.** The annotated reader runs.

- `build/` — LaTeX → `var/ub.db`, stdlib only
  - `expand.py` — the span-emitting expander. Plain text plus code-point spans.
  - `press_macros.py` — derived from press's own table, with 5 overrides; asserts key-set equality, so a new macro upstream fails our build too
  - `index_macros.py` — the index's closed 25-macro set, plain and HTML renderers
  - `readers/` — pure file → dataclasses; `_io.py` is the only module allowed to open a source path, always mode `'r'`
  - `render.py` — `(text, spans) → HTML`. **The only renderer.**
  - `load.py`, `derive.py`, `schema/*.sql`, `oracle.py`, `fonts.py`, `slugs.py`
  - `checks/` — the gates
- `ubsite/` — FastAPI + Jinja2, server-rendered, no build step, ~70 KB CSS, ~18 KB `ub.js` plus `listen.js` on section pages
- `vendor/` — copied by value with `UPSTREAM.lock`: press's tokenizer/macros/normalize, index's `cite.py`/`xref.py`, TeX Live's `hyphen.tex`, the SBL Greek and SBL Hebrew fonts (`fonts/`, each by its address on SBL's page and its SHA-256, served as published: `ARCHITECTURE.md`, Study notes), and SQLite 3.53.4's WebAssembly build (`sqlite-wasm/`, from the release zip `sources.toml` names by URL and SHA-256: `vendor-check` holds the copy to the lock without the network, and `vendor-sync` fetches the zip only for another release; until 2026-10-16 it was unpacked by hand in `~/Software`, and `make data` failed without it)
- `.venv/` — `uv venv` + `uv pip sync requirements-dev.txt`, gitignored; `requirements.txt` is compiled from `requirements.in` with `uv pip compile`, and `requirements-dev.txt` from `requirements-dev.in`: the same pins (`-c requirements.txt`) plus what only this machine's tools need, Playwright for `make e2e`. The hosts sync `requirements.txt` alone. Same arrangement as `../libnodes`. **Everything runs under it** — `make` sets `PY := .venv/bin/python`, so the build gets fontTools and the server gets uvicorn from one place.
  **Python 3.12**, pinned in `.python-version` to match `../libnodes` and `urantia-library`: all three will be hosted on the same Raspberry Pi 5 with uv-managed venvs, and sharing one interpreter saves fetching and storing a second. The full gate suite passes on it, with byte-identical output.
- `deploy/` — the systemd unit, the nginx server blocks, the sudoers drop-in and `deploy.sh`; its README names the four steps that need root on each host, all done on both. The site is live at **https://ubsite.sigmaai.au** (the VPS behind sigmaai.au, the main site) and **https://ubsite.ddns.net** (pi5), and both stay live. `deploy.sh` builds once and ships the same build to each, pi5 then sigmaai.au; `./deploy/deploy.sh sigmaai.au` deploys to one. **The database is the artifact**: the source repos are not on the hosts, so `make data` runs here and `var/ub.db` is shipped. More in `ARCHITECTURE.md`, Deploy.

**The features**, each a section of `ARCHITECTURE.md`, which says what each module and table does:

- **Listening** (2026-10-07): Merritt Horn's reading, cut at the paragraph, and the browser's voice, which reads the translations too since 2026-10-27, each from its own ▶ in Compare, in a voice Settings gives it (`tr_speech`, `/speech/<key>/<section>`, `listen.js trPlay`, `ub.js ubTrRead`). `build/audio.py`, `build/speech.py`, `tools/align/`, `tools/tts/`, `static/listen.js`; Settings in `ubsite/settings.py`.
- **The appendices** (2026-10-09): `/appendix/A` … `/F`, and every *q.v.*, B–F name and *See* linked (`derive.links`).
- **Visits** (2026-10-09): `ubsite/visits.py` → `var/visits.db`, and `/stats`.
- **The EPUB, retired** (2026-10-19): tag `epub-last` builds it.
- **The text API** (2026-10-11): `/api/v1`, its text versions in `data/text/` (`build/versions.py`), the Foundation's references (`build/foundation.py`), `ubsite/api.py`.
- **The 1955 readings and their reasons** (2026-10-12): rings and cards, the SRT Committee's reasons from `data/srt/` (`build/srt.py`), `queries.notes()`, `/lists/1955`, and in search.
- **Justified, hyphenated where the book hyphenates** (2026-10-12): `build/hyphen.py`, `paragraph.html_hy`, `check_hyphen`.
- **Reading paths** (2026-10-13): `/i/<slug>/read` and `/read/theme`; `derive.reading_path`, `queries.reading_path()`.
- **Work offline** (2026-10-13): `offline/` keeps the site's own pages in `var/offline/`; `sw.js`, `offline-core.js`, `offline.js` (Settings' Offline tab, since 2026-10-30; the cloud's menu before); its gate, `python -m offline check`.
- **Study notes** (2026-10-18): one reviewed paper at a time, `data/study/NNN.toml`, whose README holds the rules; `build/study.py`, `tools/study/draft.py`.
- **The interface in Russian** (2026-10-25): `ubsite/ru.toml`, `ubsite/l10n.py`, `/l10n.js`.
- **Translations beside the text** (2026-10-26): ud and urantia-ru under our numbering (`build/translation.py`, `tests/known-tr-*.tsv`), and the Foundation's from its HTML since 2026-10-27 (`readers/uf_html.py`, `tr_html.py`), in a fold under each paragraph, with the translator's notes, offline and in search, side by side in Compare, `/1:1/compare` (`ub.js cmpDraw`), and in the rail (`/rail/<key>`, 2026-10-27).
- **Whole paper** (2026-10-30): a paper on one page at `/N`, chosen in Settings, the choice made in the browser before paint (`base.html` `ubUnit`); its text from the same macros as a section's page (`templates/_text.html`, `paper.html`, `app.py paper_page`), listened to as one unit (`whole_audio`), and joined offline from the sections' pieces (`offline/pages.py holes`). `ARCHITECTURE.md`, The whole paper.
- **The quiz** (2026-10-28, live since 2026-10-30): the British Study Edition's `tex/quiz.tex` in the database, each question with its id for ever in `data/quiz/questions.tsv` and its paragraph reviewed paper by paper (`build/quiz.py`, `readers/quiz.py`, `tools/quiz/`, `data/quiz/README.md`); asked at `/quiz` and `/quiz/N`, invited at each paper's end, offline too (`queries.quiz`, `static/quiz.js`, Settings' `quiz`); and its board, opt-in, the site's first POSTs, kept by ubsite.sigmaai.au for both sites in `var/quiz.db` (`ubsite/board.py`, Settings' `quizboard`, `deploy/README.md`).

---

## 4. The numbers

Every asserted number lives in `verify/expectations.toml` with `measured_on` and `source_commit`, **never in code**. `verify/exceptions.toml` is currently empty and should stay that way.

```
papers 197 · sections 1,626 · paragraphs 14,586
separators 11 (3 of five stars, 8 of three) · the Foundation's 10 at the same places, all but 119:8.9
verse lines 144 in 10 blocks (48:6, 122:9, 144:3, 144:5 ×7) · set in further 4 (144:3.4, .6, .8, .10)
red-letter spans 1,267 · em spans 2,295 · 1955 variant notes 180
index entries 34,751 (32,964 A–Z + 1,351 appendix + 436 chronology events)
citations 39,885 → 50,842 targets {para 47,954, sec 2,254, paper 634}
cross-references 5,133 See/See also + 1,026 q.v., 0 dangling · headwords 4,736
B–F names that are A–Z headwords 1,332 · para_citers 113,992 · cocitation pairs 9,719
paragraphs continuing a range 8,822 of 47,958 paragraph targets (index at 2026-10-13)
headwords with a reading path 2,058 (3+ paragraphs), 1,820 of them with 2+ chapters (index at 2026-10-13)
paragraphs the Foundation numbers otherwise 106 · text API records 16,413, at version 8 (2026-10-13)
SRT changes considered 319 (303 entries) · 1955 notes with the committee's reason 167 of 180 (2026-10-12)
soft hyphens 530,865, of them the source's \- 1,392 (press 806c7ac, 2026-10-12)
translations 3: ud 3,579 paragraphs (45 papers) and 346 notes, citing 11 works, at cc37b29, urantia-ru 14,586 at 04146d5 (2026-10-26), uf-ru 14,586 and 2 editor's notes, its 2024 release (2026-10-27); ud numbers 2 of them otherwise, urantia-ru 93, uf-ru 106
offline copy 10,608 pages (3,877 reading paths, 126 of the quiz since 2026-10-30, 127 before, and the 197 whole papers since 2026-10-30, joined from the sections' pieces) + 1,626 spoken texts in 417 chunks: 47.9 MB to download and keep, 223 MB unpacked (2026-10-31, two chunks fewer since the paragraph's reference is text, not a link; 419 on 2026-10-30), and each translation a download of its own, chosen by the reader: ud 2.6 MB in 10 chunks, urantia-ru 11.8 MB in 22, uf-ru 11.8 MB in 22, each with its database for search (2026-10-26) and its spoken text (2026-10-27; how it grew: `ARCHITECTURE.md`, Work offline)
translations spoken (tr_speech): ud 3,579 paragraphs and 371 headings, urantia-ru and uf-ru 14,586 and 1,626 each (2026-10-27)
quiz 817 questions on 126 papers, 51 with more than one right answer, 3,686 answers (962 right), 63 slips open in tests/known-quiz-slips.tsv, all 817 reviewed: 774 by the text (24 by more than one passage, 18 by a run of paragraphs shown whole), 3 by a study note, 40 dropped (the Foreword's 8, 11 Q20, and 31 ruled on 2026-10-30, Paper 138's only question among them), so 777 asked on 125 papers (study d6c3206, 2026-10-30; 819 at 2474116, until Tigran mended 30 on 2026-10-29)
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

23. **Safari deletes everything a site keeps after seven days of Safari use without a visit to it**: the offline copy, the worker, the settings. A site added to the Home Screen is exempt, which is why Settings tells an iPhone reader to add it, and why `/manifest.webmanifest` says `standalone` (a Home Screen bookmark that opens in Safari is not exempt).
24. **`sw.js` names `__VERSIONS__` in its own header comment.** `app.py` puts the scripts' hashed addresses in place of the line `var V = __VERSIONS__;`, whole, and fails if it is missing. Replacing the first `__VERSIONS__` filled in the comment and left `V` undefined, and all Chrome said was "ServiceWorker script evaluation failed".
25. **A service worker runs only in a secure context**: HTTPS, or `localhost`. The dev server on `http://<LAN address>:8130` is neither, so a phone there shows no offline icon; test on this machine's `http://localhost:8130`, or on the live site.
26. **`tests/test_no_writes.py` finds `.write_bytes(` only after a word character.** `(tmp / name).write_bytes(…)` passes it unseen, so `offline/pack.py` writes through a named path.
27. **What a service worker posts to a page must be plain data.** `sw.js` once kept the running download's promise on `busy`, which it sends to the pages as the copy's state; `postMessage` cannot clone a promise, so every message while a copy downloaded failed. Settings went on saying "Update now" until the update had ended, with no sign that it had begun, and a second tap did nothing. Tigran reported an Update that did nothing on 2026-10-13. The promise is `running` now, apart.
28. **Nothing in `sw.js` writes back a `meta` it read before a wait.** A check reads meta, asks the network, and writes; a download that ended in between had its `current` put back to the copy before, whose cache it had deleted, and the copy was lost. Every change to meta goes through `updateMeta()`, one at a time, each on what the last one wrote.
29. **Nothing a stored page carries may move with a build that changes nothing.** The rail's `data-v` was `ub.db`'s mtime, which every `make data` moves, and every section page carries the rail. So each deploy changed all 197 papers' chunks of the offline copy, and asked every reader for a 5.5 MB update with the book unchanged; the update offered on 2026-10-14 after the licence footer was that. `data-v` is now a hash of what the rail draws (`app.py _book`). After changing a template, rebuild `ub.db` and the copy twice and compare the manifests: nothing may differ.
30. **Chrome installs an app from the manifest it read when the page loaded.** An Android tab kept alive across a deploy installs the old one, name, icons and all, and `chrome://webapks` is where to see what an installed app was given. On 2026-10-15 ubsite.sigmaai.au's app was installed at 14:56 from a tab loaded at 11:22, before its burgundy icons went live, and came out the same as ddns.net's (the visit record showed no load between). Reload the page before installing; an app already installed is put right by uninstalling and installing again from a fresh page, or by its Update button in `chrome://webapks`.
31. **The study edition is not the press text with notes.** It is British and metricated: 23:3.2 reads "299,789 kilometres" for "186,280 miles", 41:4.1 "$2\times 10^{30}$ kg" for "two octillion (2×10²⁷) tons", and 0:1.24 restores the 1955 "other" that the press gives as a reading. So a study note's place is never an offset in its text (each reviewed note names the press words it follows), and a note about a number or a reading may be about the study edition's own words, true there and false on the site.
32. **The study edition writes Hebrew word by word reversed**, visual order, for XeTeX without bidi: its Shema at 1:7.6 begins with אֶחָד. `tools/mktext.php` turned it round; `tools/study/draft.py` does now, and a reviewed note holds Hebrew in logical order, which nothing can check.
33. **A wrapper for the interface's words is never a span.** `ub.css` has a dozen rules for a span inside something: `.letters span {display:block}`, `.seg span` placed relative, `.railfold span` set small. Two spans for each string's two languages would have restyled every one of them, so they are `<x-en>` and `<x-ru>`. And `textContent` of anything holding them has both languages: read the English as `tools/offline_e2e.py` `EN` does, without the `x-ru`.
34. **The language is resolved from the setting, never from `data-lang`.** `ubLang()` first read the attribute and, where it found none, the browser's language; a tapped English removed the attribute, and the next call, from `ub.js` on the same tap, put Russian back from a Russian browser. It is handed `lang` itself now, `auto`, `en` or `ru`.
35. **A translation numbers the book as its source did, not as we do.** ud is the study edition's numbering before 2026-09-21: ten separators take a paragraph number (31:10.22 written `\separatorline`, the rest left empty), and everything after one in its section runs one ahead, six in 144:5. urantia-ru numbers 144:5 as the Foundation does, skipping a number at each separator. Neither has a 0:12.10: each sets the Acknowledgment's heading as a `\usection` inside 0:12, which its style's `\ackn` names. So a section's number is taken from the next paragraph's address, never by counting `\usection`.
36. **A translation's `\pc` comes after the address, and takes no argument.** The press's `\pc` has an optional one and stands before `\vs`; read with the press's spec, urantia-ru's `\vs p031 10:21 \pc [Под объединенным покровительством ...]` lost the whole paragraph as its argument (trap 2 again), and three more. Both styles define `\def\pc{...}`.
37. **TeX's `\'` stresses the letter after it.** ud's `призна\'ют` is признаю́т, not призна́ют, as ROADMAP's example first had it.
38. **The Foundation's Russian writes 650 stress marks as Latin letters**, чтó, бóльшую: other letters to search and hyphenation. `tr_html.LATIN_STRESS` reads them as Cyrillic and U+0301. Its two editor's notes stand unclosed at a paper's end, `{{* …`, their marks a bare `*` (62:4.2, 85:2.1).
39. **A font feature kept for one glyph tells the browser the face has it.** The Cyrillic subset kept `smcp` and `c2sc` for U+0301 alone (2026-10-26), so Chrome stopped synthesising Cyrillic small capitals and set them in lower case. `fonts.py` drops them, and fails a subset that keeps them.
40. **Chrome can say offline with the network working, until it is restarted.** On 2026-10-27, after Tigran's laptop moved from Wi-Fi to a cable, its worker had `navigator.onLine` false: it answered every page from the copy without asking the server (pi5's nginx log has no request for a page, while the worker's own fetches, an update of the copy, went through), and the cloud stayed struck through, reload after reload, until Chrome was restarted. The same state reproduced refused the recordings too. So nothing takes the browser's offline as final: the worker asks the network anyway (`sw.js`, past the browser's cache, which would otherwise answer a translation not kept), `offline.js` asks the site at once where a page starts offline, and `listen.js` tries a recording. `unshare -rn` reproduces it: with only loopback, Chrome says offline, and a server on 127.0.0.1 answers.

---

## 8. Decisions on the record

`DECISIONS.md` holds them, with who chose each and when, grouped by subject. A decision there is not undone without asking Tigran. Read the group of what you are about to change.

**What binds every change**, wherever it is made:

- **No setting reaches the server.** A switch is CSS keyed off `data-<key>` on `<html>`, set by the head script before first paint, so every page carries what every setting needs. Every setting is declared once, in `ubsite/settings.py`: a new one is an entry there and a CSS rule, and only values that differ from the default are stored. Its label is a bare noun phrase, with no article. (Settings)
- **A route or a search is made twice**, in `app.py` and in `ubsite/static/offline-core.js`, which the offline copy runs; `python -m offline check` holds the two byte for byte. (`ARCHITECTURE.md`, Work offline)
- **Nothing a stored page carries may move with a build that changes nothing** (trap 29).
- **With every change a reader will notice, add its line to `ChangeLog.md`** under Unreleased, at the top of its heading, in the commit that makes it: one plain sentence, no Markdown; what only developers need goes under For developers. A new revision of the index or the text is such a change, described from a comparison of the database before and after, never from the source's commit subjects. `/changelog` shows the file as written. (The changelog and What's new)
- **A text version moves only when something a site receives changes**, and a number is never made again for other text: `data/text/` is append-only. (The text API and the licence)
- **Only the press says what 1955 printed.** The SRT Committee's page supplies its reasons, under its name, and nothing else (trap 21). (The 1955 readings)
- **Every word the interface says is in English and Russian**, in `ubsite/ru.toml`, drawn by `l10n.py`'s `t()` and `l10n.js`'s `T()`; the book, its index, `/changelog`, `/api`'s documentation and `/stats` stay English. (Russian, and the translations)
- **A date in words is American, October 18, 2026**; one that names a build or a commit stays ISO. (The changelog and What's new)
- **Slugs are data**: `data/slugs.tsv` is append-only, and a headword keeps its slug for ever. (Moving about the book)
- **The book's text is black** (`--text`), everything around it `--ink`; **a link is grey** around the reading and **blue** where going somewhere is the page's job. (The text on the page)
- **Never serve Goudy Handtooled BT**, which is Bitstream's; **never use the Foundation's concentric circles**, its trademark. SBL Greek and SBL Hebrew are served byte for byte, never subset. (The text on the page; The sites; `ARCHITECTURE.md`, Study notes)

**The groups**, and what each decides:

- **The text on the page**: justified, with the book's hyphenation; dot-leader rows; a paper's head; the dropped capital; verse; separators; pilcrows; each paragraph's reference, ▶ and 1955 page; the small indent; a list's label; UB Goudy; the colours of the text and its links.
- **Moving about the book**: `/101` the whole paper, or its first section, by Settings' Whole paper, decided in the browser; paragraph addresses and ranges; the left rail and its fold; the transport bar; turning the page by keys and taps; the running head on demand; `/lists`; `/appendix/A` … `/F`; slugs.
- **The index beside the text**: chips; ordinals' superscripts; what a whole paper or section cites, once; a range at its first paragraph; *See* links; appendix chips; the Chronology and its windows; entries of one headword run on; reading paths in two orders; the index's fold, and the switch that turns it off.
- **Search**: an exact headword wins; Ctrl+X.
- **Settings**: one mode; the dialog, its tabs and every setting; Whole paper, a rule for addresses, not a CSS rule; a site's own defaults.
- **Listening**: no Listen button; the end of a section; a whole paper one unit; Follow along; ⏮; the browser's voice; the AI voice, made here; Bark, rejected.
- **The sites, their apps and their visitors**: the mark; the site's address under the name; each site's app and icons; the footer; visits counted with no IP address or cookie kept; robots.txt.
- **The text API and the licence**: `ref` and `uf_ref`; the text public domain, the edition CC BY-NC-SA 4.0; passages and papers by reference; HTML alone; text versions; what a paragraph record says.
- **The 1955 readings**: a ring and a card with the committee's reasons; the 1955 page references.
- **Work offline**: the copy a tick in Settings' Offline tab, the cloud a sign that opens it; updating by itself; everything but the recordings; the API's page; the whole paper joined from its sections' pieces.
- **The changelog and What's new**: `ChangeLog.md` is both; American dates.
- **Russian, and the translations**: the interface in both languages; the translations in a fold, chosen in Settings, offline, with their notes, and in search.
- **The quiz**: two ways in; one question at a time, a set for more than one right answer; references reviewed per paper, a study note among them; the book's spelling and dates; English only; on by default; kept in the browser; a board, opt-in, ranked by questions right the first time, on the main site.

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
2. **Site licence** — the press repo is CC BY-NC-SA 4.0, and NC forecloses most of what a public API is for. For the text this is settled: the API serves it as public domain (2026-10-11, `DECISIONS.md`). So is the index's (2026-10-14, `DECISIONS.md`): CC BY-NC-SA 4.0, with the edition as a whole, so it may go through the API, its licence marked on what is sent. Not built.
3. **Domain and host**; whether `urantia-library` on this box merges or coexists. Port 80 is reportedly not forwarded, which affects certbot.
4. **The 58 rights-restricted images** — attribution cards, or seek permission.
5. **Work offline and the index: answered** (2026-10-14). The copy puts the whole index on every device that asks, as pages and as a SQLite file DevTools can extract. Tigran asked Geoff, who asked Harry, who "is happy as long as our terms of use don't introduce the book into the public domain": the book as a whole, the index with it. The text of *The Urantia Book* stays public domain. Work offline was deployed the same day.
6. **A concept page's first line repeats its heading** where it adds nothing: `/i/adoption` shows "adoption" under the `<h1>` "adoption". On `/i/oaths` the same line reads "oaths. *See also* promises" and earns its place, because the level-1 entry carries citations and cross-references. Suppressing it when it adds nothing was offered and not yet ruled on.

---

## 11. What comes next

Phase 6, the study-edition apparatus, is under way: its `\fnst` notes reach the site paper by paper, Papers 0–8 and 32 so far, and the quiz is live (2026-10-30: its questions, their references all reviewed, its pages and its board). Then the KJV, and the figures behind the rights gate; then Phase 7 (human sources) and 8 (the timeline, the map). The plan has the phases, and `ROADMAP.md` why each is worth doing.

What Phase 6 imports: 404 `\fnst` study footnotes (307 on 2026-09-21, when this was first written; the human-source notes of Papers 1–6 came on 2026-10-07 and 09), 60 human-source `\bibitem` records, 116 `\bibref` cross-references, the whole KJV (24,974 verses + 5,069 marginal notes), 817 quiz questions (**51 of them multi-answer**, 962 right answers — a single-answer model marks correct responses wrong; this said 83 and 1,002, never measured, until 2026-10-28, and 819, 53 and 966 at 2474116; the quiz is in the database since then, `ARCHITECTURE.md`, The quiz), and 84 figures of which **58 are rights-restricted** and must be separable at query time.

Traps 1 and 12 are about the study edition's TeX and its own tools.

---

## 12. The recorded AI reading

Merritt Horn's reading and the browser's voice have been live since 2026-10-08. The recorded AI reading is still to be made, once and carefully (Tigran: "we are doing this only once, there is no rush, so we should make sure there are no errors in the final audio"). The voice is chosen (`higgs3_mature`), the pipeline is built (`make tts`), and a trial of Papers 1, 30 and 144 is on a private page for Tigran to hear and mark. **Do not start the whole-book run before Tigran approves the trial.** Where it stands and the next steps: `ARCHITECTURE.md`, Listening; the session-by-session detail is in memory (`audio-feature.md`).
