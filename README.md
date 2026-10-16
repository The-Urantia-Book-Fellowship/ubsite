# ubsite

The Uversa Press text of *The Urantia Book* read together with the Uversa Press index, live at **https://ubsite.ddns.net** (pi5) and **https://ubsite.sigmaai.au** (the VPS behind sigmaai.au), the same build on both.

This file is the operating manual: how to bring the site up to date when its sources change, and how to deploy it. For how it is built and why, read [`CLAUDE.md`](CLAUDE.md). For where it is going, read [`ROADMAP.md`](ROADMAP.md). The one-time root setup on each host (the unit, the certificate, nginx, sudoers) is in [`deploy/README.md`](deploy/README.md). It is done on both and need not be repeated.

---

## The one idea

**The site shows `var/ub.db`, and nothing else.** That file is built on this machine from three sibling repositories and shipped to the two hosts, pi5 and the VPS behind sigmaai.au. Nothing updates by itself. When the index session commits a correction, the site carries it only after someone rebuilds and deploys. Until then, a paragraph can stand with nothing beside it while the index plainly cites it.

The footer of every page gives the date of each commit the database was built from:

> Text (2026-10-03): the Uversa Press edition. Index (2026-10-03): the Uversa Press index …

Hover over either date for the full commit ID. Each date links to its commit on GitHub, at the `url` that `sources.toml` gives each repository. Both repositories are **private**: a link opens for members of The-Urantia-Book-Fellowship who are signed in, and is GitHub's 404 page for everyone else. That is a decision on the record, not an oversight. Delete a `url` and rebuild to drop its link.

---

## Setup, once

The three source repositories must be at the paths `sources.toml` gives, relative to this directory:

| key | path | read |
|---|---|---|
| `press` | `../urantia-uversa-press-claude` | from the working tree |
| `index` | `../index` | **at HEAD**, never the working tree |
| `study` | `../urantia-study-edition` | by `make check` only, until Phase 6 |

Then:

```
make venv          # .venv on the pinned Python 3.12, from requirements-dev.txt (the site's pins, plus Playwright)
make sources       # the three repos and the commits a build would read
```

Merritt Horn's recordings must be at `/Audio/Urantia/Urantia-MH-Audio-DVD`, here **and on both hosts**: the build lists them, and each host serves them from that path. They are the Uversa Press DVD's MP3s (128 kbps stereo), copied once with the folder names lowercased. `/Audio/Urantia/Urantia-MH-Audio` is a 32 kbps transcode of the same recordings and is not used. `sources.toml` names it under `[audio.mh]`. They are a master like the repos, and nothing writes to them.

### What this machine needs besides

Two programs outside the tree are needed by every build, and so by every deploy:

- **TeX Live 2026**, at `/usr/local/texlive/2026` (`[texlive]` in `sources.toml`). `make data` begins with `make vendor-check`, which holds `vendor/tex/hyphen.tex` to TeX Live's `hyphen.tex` and fails without it. The press needs it anyway, to set the book.
- **Node 24**, on the `PATH` (24.16.0 here, installed with nvm). `make offline`'s gates run `offline-core.js` and SQLite's WebAssembly build in Node, as the service worker does. No other version has been tried.

The rest are needed only by the tool named:

| program | here | for |
|---|---|---|
| uv | 0.11 | `make venv`, `make lock` |
| Java (`openjdk-26-jre-headless`) | OpenJDK 26 | `make epub`'s last gate, epubcheck, which `make epub` fetches itself |
| Google Chrome (`/usr/bin/google-chrome`) | 155 | `make e2e` (Playwright, in `.venv`), `tools/make_icons.py`, `tools/make_cover.py` |
| ImageMagick 7 (`magick`) | 7.1 | `tools/make_icons.py`, `tools/make_cover.py` |
| `pdftotext` (poppler-utils) | 26.01 | `tools/hyphen_print.py` |
| `ffprobe` (ffmpeg) | 8.0 | `tools/audio/manifest.py` |

Nothing else a tool uses lives outside the tree, but the audio work's environments in `~/Software/ml` ([Listening](#listening)). epubcheck and SQLite's WebAssembly release are fetched by URL and held to a digest: epubcheck into `var/epubcheck/` by `make epub`, the SQLite files into `vendor/` by `make vendor-sync`. The hosts need none of this but uv: `deploy.sh` ships what was built here.

---

## Updating the site

### 0. Is the live site behind?

```
curl -s https://ubsite.ddns.net/healthz
curl -s https://ubsite.sigmaai.au/healthz
make sources
```

Every deploy gives both hosts the same build, so the two should agree; if they do not, a deploy stopped partway. `/healthz` returns the full commit of each source the live database was built from:

```
{"ok":true,"paragraphs":14586,"built_at":"2026-10-06T14:28:35",
 "sources":{"press":{"commit":"39836454…","dirty":false},
            "index":{"commit":"b12500f4…","dirty":false}}}
```

`make sources` prints the commits a build would read now. If either differs, the site is behind.

Two rules decide what a build sees:

- **The index is read at HEAD.** Uncommitted work in `../index` never reaches the site, by design: the index is edited in another session, and a build must not race an edit in progress. If a correction is missing, first check that it is *committed* there, with `git -C ../index log -1`.
- **Press is read from its working tree.** `make sources` marks it `+dirty` if a tracked file has uncommitted changes, or if `tex/` has an untracked file. An untracked directory elsewhere in press does not count. Do not deploy a dirty build: the footer would say `(2026-10-03, dirty)`, and the commit alone could not reproduce it.
- **Push the source commits.** The footer links to them on GitHub. If a commit is on no remote branch as of the last fetch, `make data` warns `source-not-pushed`. The link is then a 404 even for members, until that commit is pushed.

To ask whether one paragraph is cited in the database you have built:

```
sqlite3 var/ub.db "SELECT COUNT(*) FROM citation_target ct JOIN paragraph p
  ON p.id = ct.paragraph_id WHERE p.ref = '2:5.12' AND ct.precision = 'para'"
```

### 1. `make vendor-check`, and when it fails

Eight files are copied by value into `vendor/`, and their hashes are recorded in `vendor/UPSTREAM.lock`:

- `latex_tokenizer.py`, `macros.py` and `normalize.py` from press's `tools/text-verify/`;
- `cite.py` and `xref.py` from the index;
- `hyphen.tex`, Knuth's hyphenation patterns, from TeX Live (`[texlive]` in `sources.toml`). It is "NOT TO BE CHANGED IN ANY WAY", so a difference there means `sources.toml` names the wrong TeX Live tree.
- `sqlite3.js` and `sqlite3.wasm`, SQLite's WebAssembly build, from a release zip that `sources.toml` names by its URL and SHA-256 (`[sqlite_wasm]`). A release cannot move, so `vendor-check` holds the two files to the lock, and the lock to the release `sources.toml` names, without the network; `vendor-sync` fetches the zip only when `sources.toml` names another. To adopt a new release, give its URL and SHA-256 there, then `make vendor-sync`.

`make data` runs `vendor-check` first. If upstream has moved, the build stops and prints a unified diff:

```
vendor: UPSTREAM MOVED  press:tools/text-verify/macros.py
--- vendor/press/macros.py
+++ …/urantia-uversa-press-claude/tools/text-verify/macros.py
+    "fill":          Spec(STRIP, note="infinite glue inside \\vspace*{\\fill} …"),
```

This is deliberate. Adopting upstream code is a reviewed commit, never a side effect of a build. Read the diff and decide:

| the change | what to do |
|---|---|
| a `note=` or a comment only | adopt; nothing in `build/` reads `Spec.note` |
| a new `STRIP`, `EMIT_TEXT`, `EMIT_ARG`, `EMIT_SUP`, `EMIT_ARG_ITALIC` or `STRUCTURAL` macro | adopt; `build/press_macros.py` translates these automatically |
| a new action name | adopt, then `make data` fails with "has no translation": add it to `_TRANSLATE` in `build/press_macros.py` |
| a change to a macro named in `OVERRIDES` (`textcolor`, `fnc`, `pc`, `ublistelem`, `bibdf`, `-`) | think: our override hides upstream's change, which may be what is wanted, or may not |
| anything in `cite.py` or `xref.py` | adopt, and expect `make check`'s citation and cross-reference counts to move; explain any change |

To adopt:

```
make vendor-sync          # copies all eight files and rewrites the lock
git diff vendor/          # only what you reviewed, plus the lock's commit fields
git commit -am 'vendor: adopt press macros.py at 3983645 (\fill, stripped)'
```

Keep the message form: `vendor: adopt <repo> <file> at <short sha> (<what changed>)`. See `git log -- vendor/` for examples.

### 2. `make data`

Builds `var/ub.db` in about 20 seconds. The first two lines say what it is reading:

```
reading press text, worktree at 3983645 ...
reading index at b12500f ...
```

The build writes `var/ub.db.tmp` and moves it into place only on success, so a failed build leaves the previous database untouched. Failures are loud by design. An unknown macro, an unparseable citation, or a source line that nothing claimed is a hard error, listed under `problems`. A macro that is new to the press TeX must first be taught to press's own `tools/text-verify/macros.py`, and then adopted as in step 1.

Near the end it says where the [text API](#the-text-api) stands: `unchanged at version N`, or, when anything a syncing site receives has changed, `version N+1: … records new or changed`. In that case it has appended the new version to `data/text/`, which must be committed with the change that made it (step 5).

### 3. `make check` and `make test`

```
make check        # every gate, about 8 s, after rebuilding the oracles from the sources
make offline      # the copy Work offline keeps, and its gates, about 45 s (needs Node)
make test         # unit tests, including the never-write-to-a-master guard
make paranoid     # optional: fingerprint the three trees, build, prove nothing moved
```

When a gate fails because a source *legitimately* changed a number:

- **Hard counts** are in `QUERIES` in `build/checks/check_db.py`: papers, sections, paragraphs, red-letter and em spans, 1955 notes, chronology events, and the entries of each of Appendices B–F (the index's own `check_tex.py` asserts the same). Also the source's `\-` and the soft hyphens: these move whenever press edits `tex/urantia-hyphen-en.tex` or adds a `\-`. Before changing them, run `tools/hyphen_print.py` against a fresh build of the book: every printed break must still be offered. Change the number, and add a comment naming the source commit and the reason. The `436` there is the model: index `6cd4d19` dropped one chronology event by ruling.
- **Index counts** (entries, citations, targets) are reported, not asserted, because the index is under daily editorial work.
- **The `tests/known-*-deltas.tsv` files** list the places where an oracle is wrong and we are right, and must match *exactly*. A new disagreement, or one that silently disappears, fails the gate. Decide it against the SRT HTML before changing the list.

### 4. Look at it

```
make serve        # http://127.0.0.1:8130, in the foreground; Ctrl-C to stop
```

Open the paragraph that prompted the update, for example `http://127.0.0.1:8130/2:5.12`, and check the footer's two dates, and the commit IDs in their tooltips. To serve in the background, run `make serve-bg`, and stop it with `make stop`. **Never** use `pkill -f` (see CLAUDE.md §6).

### 5. Commit

Commit anything that changed in this repository: the vendor adoption, a moved count, and above all a new text version in `data/text/`. `deploy.sh` refuses to ship while `data/text/` is uncommitted, because a version number a site has been sent must never be made again for other text. `deploy.sh` rsyncs the working tree as it stands, and what runs on the hosts should be a commit. Then `git push`: the history is kept on GitHub, in the Fellowship's private repository `The-Urantia-Book-Fellowship/ubsite`.

### 6. Deploy

```
./deploy/deploy.sh               # rebuild + check here, ship code and database to both hosts, restart each
./deploy/deploy.sh sigmaai.au    # the same, to one host (pi5 or sigmaai.au)
./deploy/deploy.sh --no-data     # code or templates only; leave the hosts' databases alone
./deploy/deploy.sh --audio       # also copy the AI voice first, after `make tts` changed it
```

The script builds once, then does the rest for each host in turn, pi5 then sigmaai.au, and stops at the first that fails:

1. runs `make data`, `make check` and `make offline` again, so a deploy never ships an unchecked database or offline copy, and checks that the host holds every recording the database serves, at the path and size it records;
2. rsyncs the code to `<host>:/home/tigran/ubsite`, without `.git`, `.venv`, `var/` or `export/`;
3. ships `var/ub.db` as `ub.db.new` and `mv`s it into place, so a half-copied file is never the one being served; then the offline copy, its chunks before the manifest that names them, pruning chunks that neither it nor the manifest before it names (see [Work offline](#work-offline));
4. copies `var/geoip/dbip-city-lite.mmdb` when `make geoip` has changed it (the visit counter's places; see [Visits](#visits)), and runs `uv pip sync` in the host's venv;
5. runs `sudo systemctl restart ubsite`. This is password-free: the sudoers drop-in from `deploy/README.md` step 4 allows exactly that and nothing else;
6. polls `/healthz` for 30 s, and prints the unit's status if it never reports ok.

It takes about a minute and a half, mostly the rebuild and the gates. The big copies to pi5 go over its fast link, `pi5f`; to sigmaai.au, over the internet. The script refuses to run on a host against its own live tree.

### 7. Verify live

```
curl -s https://ubsite.ddns.net/healthz      # ok:true, and the commits from `make sources`
curl -s https://ubsite.sigmaai.au/healthz    # the same
curl -s https://ubsite.ddns.net/2:5.12 | grep -c 'loses sight of love'
```

Then look at the page and its footer in a browser.

---

## Work offline

A reader can keep the whole site in their browser and use it with no connection: the cloud at the header's corner opens a menu, "Work offline", with a button to download the copy (called "Read offline", and a switch in Settings, until 2026-10-14). The cloud always says whether the page is online or offline, whether a copy is kept, and whether it is out of date. There is no offline mode to turn on or off: online the site is read live, and without a connection the copy answers, and it stays through both. Removing it is a button of its own. It holds the book with its margin index and 1955 readings, every concept page and every headword's reading path in both orders, the appendices and the lists, search, and the text your browser's voice reads, so that listening works offline in that voice. Not the recordings. 44 MB to download, kept as it came, gzipped; unpacked it would be 191 MB, 132 of them the reading paths (2026-10-14).

- **The copy is the site's own pages.** `make offline` (`offline/`) asks the app for every page it will hold, in-process, cuts each into the build's shell, which every page shares, and what is the page's own, and writes them as gzipped chunks named by their hashes into `var/offline/`, with `manifest.json` listing them. A section's left rail is kept once for its paper. The reading paths go in chunks of about a megabyte, a letter of the index at a time, and Jesus's in one of its own.
- **The worker** (`ubsite/static/sw.js`) is registered only by a reader who turns it on. It goes to the network first, so online nothing changes and visits are counted as before. The copy answers when the network fails, takes over 4 s, or the server answers 5xx. `ubsite/static/offline-core.js` joins the pages again and runs search. The browser keeps each chunk gzipped and unpacks it when it is read; a copy kept before 2026-10-14 was unpacked, and an update packs it again rather than fetch it.
- **Listening offline** is in the browser's voice: each section's spoken text (`/speech/`) is in the copy, and offline `ub.js` picks one of the device's own voices, since Chrome's Google voices and Edge's Natural ones are spoken by a server. Offline, with a recording chosen in Settings, Listen does not play and says why: the voice Settings names is never swapped for another. On Linux, Chrome has no voice of its own unless started with `--enable-speech-dispatcher`; Firefox uses speech-dispatcher. DevTools' Offline does not stop Chrome's Google voices, which the browser fetches itself.
- **Search** runs on SQLite's own WebAssembly build (`vendor/sqlite-wasm/`), on two databases cut from `ub.db`, the text's and the index's, with the same FTS5 tables, tokenizer and queries as `app.py`.
- **The gates** (`python -m offline check`, run by `make offline`) have Node run `offline-core.js` on the copy and hold every page it makes to the page the server sends, byte for byte: all 10,283 stored pages, every section with all its paragraphs marked, the not-found pages and redirects, and every query in `tests/fixtures/offline-queries.txt` and in this machine's `var/visits.db`, in each list. Every link in every page must land.
- **Stale copies.** The manifest's `build` is a hash of what the copy holds, so it moves only when something in the copy does. While online, the worker asks for the manifest at most once an hour, and whenever the cloud's menu opens; when it differs, the cloud shows the flame's dot, and its menu says the copy is from such a date, and what the update costs ("Update now (0.1 MB)"); the reader taps it (Tigran, 2026-10-13). Until 2026-10-14 a line under the header said so too. The update fetches only the chunks whose hashes are new, carrying over any this browser holds in any copy, checks each, and becomes the copy only when it is whole; one that fails leaves the copy before it, and says why, in the menu. A site that cannot be reached counts as offline though the browser is online (the network failing, or the server answering 5xx, to the worker's check or to a page): the cloud is struck through and the menu offers nothing that needs the site, until a check reaches it again. The menu and the cloud's tooltip show it going on, in MB. The worker and the SQLite script it imports carry ETags, because a browser asks for them again after every page it loads. A build that changes nothing in the copy must leave its manifest as it was: until 2026-10-14 the rail carried `ub.db`'s mtime, and every deploy cost every reader 5.5 MB (CLAUDE.md trap 29).
- **What's new.** Beside Update now, "What's new" opens a popup over the menu, which stays open beneath it: what changed on the site after the copy was made, newest first, by day, and a line where the text or the index is newer than the copy's, with its date. The list is this repository's commit subjects, the 200 newest of those that touch `ubsite/`, `offline/`, `build/` or `data/`, each with its time, written into the manifest as `news` by `offline/news.py` when the copy is built (the hosts have no `.git`); it is not in `build`, so a commit that changes nothing in the copy offers no update. The index's and the press's own commits are never listed: their subjects are editorial notes. So a commit's subject is what a reader reads: write it for them.
- **Install as an app.** `/manifest.webmanifest` and `ubsite/static/icon-192.png`, `icon-512.png` (`tools/make_icons.py`) let a browser install the site. Chrome's own banner is held back; the cloud's menu offers the button, and on an iPhone says how, because Safari deletes what a site keeps after seven days without a visit, except for a Home Screen app. The menu's first line names the site at its right, `ubsite.ddns.net` or `ubsite.sigmaai.au`, as `ub.js` reads it from the page's address: an installed app shows no address. The two apps are told apart without opening them too (2026-10-15): the manifest's full name names the site ("The Urantia Book · ubsite.sigmaai.au", which Chrome shows when installing and in `chrome://webapks`; Android's own label, under the icon and in Settings → Apps, is the short name, "Urantia Book" on both), and ubsite.sigmaai.au's icons have a burgundy book (`icon-192-burgundy.png`, `icon-512-burgundy.png`, `apple-touch-icon-burgundy.png`), its tab's icon too (`favicon-burgundy.svg`, `.ico`). The manifest and the touch icon are answered by the host asked (`app.py SITES`), and so are never in the offline copy, which is one for both; the tab's icon is chosen by the page from its address, so the copy keeps both. The header's mark is the same on both.
- **To see it work**, end to end in Chrome: `make e2e`, which builds the copy and runs `tools/offline_e2e.py` under `.venv`, with Playwright driving the system's Chrome. It serves a scratch copy of `var/offline/` on port 8131, turns it on, reads and searches offline, unpacks the copy as the worker before 2026-10-14 kept it and updates from that, makes a newer build and takes it, fails an update, stops its server to show that a site out of reach counts as offline, and turns it off. On this machine the dev server works too, at `http://localhost:8130` (a secure context); a phone needs the HTTPS site.

---

## The EPUB

The whole site as one EPUB 3, for reading offline: the text, the index entries beneath each paragraph, the Index A–Z with every headword's concept page, Appendices A–F, and an outline down to every section. Everything but listening. It is built from `var/ub.db` alone, here, and is private for now: nothing ships it.

```
make data                  # if the database is stale
make epub                  # -> var/epub/the-urantia-book.epub, then every gate
```

The last gate is epubcheck, the W3C's validator. It needs Java, once:

```
sudo apt install openjdk-26-jre-headless      # any Java 11 or later
```

The first `make epub` fetches epubcheck 5.4.0 from its GitHub release into `var/epubcheck/`, held to the SHA-256 in the `Makefile` (`EPUBCHECK_SHA`); it was unpacked by hand into `~/Software` until 2026-10-16. `EPUBCHECK=/path/to/epubcheck.jar make epub` uses another copy. Without Java, every other gate still runs and the last one fails, naming the package.

The file carries a fixed identifier, so a reader takes a new build for a new version of the same book and keeps its highlights. The same database always builds the same bytes. `tools/make_cover.py` redraws `epub/cover.jpg` when the mark or the wording changes.

For a Kindle, send the EPUB with Send to Kindle, or convert it with Calibre: `ebook-convert var/epub/the-urantia-book.epub book.azw3` (about 3½ minutes).

---

## Listening

Every section can be heard in Merritt Horn's reading, and from any paragraph once his reading is aligned. The player and the Settings dialog are `ubsite/static/listen.js` and `ub.js`. The build turns the recordings into the tables `audio_source`, `audio_file` and `audio_segment`, through `build/audio.py`, from three checked-in files in `data/audio/`:

| file | what | made by |
|---|---|---|
| `mh-files.tsv` | every MP3, with its size, duration and SHA-256 | `.venv/bin/python -m tools.audio.manifest mh` |
| `mh-overrides.tsv` | the three files that break the naming rule, and why | by hand |
| `mh.tsv` | each paragraph's start and end in its file, and how much of it was heard | `make align` |
| `mh-unread.tsv` | paragraphs the recording does not contain | by hand, from the review |
| `mh-low-match.tsv` | paragraphs where the reading and today's text differ | by hand, from the review |

The alignment needs a GPU and runs on this machine only, in its own venv in `~/Software/ml` (never in `requirements.txt`):

```
make align-venv          # once: faster-whisper and its CUDA libraries
make align-transcribe    # Whisper over all 121 hours on the 3090: about 1.5 h, resumable
make align               # match words to paragraphs, cut in the pauses: seconds
make align-repair        # re-hear, unbatched, what came out mostly unheard
make align               # again
less var/align/mh-review.tsv   # the paragraphs whose reading differs from the text
```

`make check` holds the differences to `mh-low-match.tsv` and `mh-unread.tsv` **exactly**. A text correction that makes the reading and the text diverge shows up there, and the gate fails until the paragraph is recorded. Use the 3090 alone: the 2080 Ti drives the display, and under load it reached 88 °C and throttled.

The recordings do not change with the text, so none of this reruns after an ordinary correction. Rerun it only when paragraphs are added, removed or renumbered.

With Settings' "Follow along" off, the reader can move anywhere on the site while a section plays. `listen.js` follows the site's links inside the page instead of loading a new one, so the reading goes on.

### Your browser's voice

Settings also offers the browser's own speech, the Web Speech API. Nothing is recorded: `listen.js` fetches a section's spoken text from `/speech/<paper>:<section>` (the `speech` table) and the browser reads it. How it sounds depends on the browser: Google's voices in desktop Chrome, Microsoft's in Edge, Apple's in Safari. It is offered beside the recordings, not instead of the AI voice below, because nobody can check what it says, and because a phone stops it when the screen locks. `listen.js` keeps the screen on while it speaks.

### The AI voice

The second voice is made here, by Higgs TTS 3 (Boson AI) on the 3090, from the spoken text the build derives (`build/speech.py`, table `speech`). Each heading and paragraph is read a sentence or two at a time. Every piece is checked for a drone, a dead pause or a cut-off end, then heard back by Whisper word by word, and made again at another seed until both pass (`tools/tts/higgs3.py`, `tools/tts/listen.py`). The pieces are joined into one MP3 per section under `var/audio/ai/`, which `deploy.sh --audio` copies to the hosts. Three files in `data/audio/` come out of it and are checked in:

| file | what |
|---|---|
| `ai.tsv` | each paragraph's start and end in its section's file, and the SHA of the spoken text it was made from |
| `ai-files.tsv` | every MP3, with its size, duration and SHA-256 |
| `ai-unsettled.tsv` | pieces used although no try was heard exactly as written, with what Whisper heard instead |

```
make tts                 # make what is missing, then assemble: ~27 h for the whole book, resumable
make tts-assemble        # assemble only, from what has been made (no GPU)
```

**Unlike Merritt Horn's reading, the AI voice follows the text.** After a correction, `make check` fails with "an AI reading is of the spoken text as it is now": the voice would read words the page no longer says. `make tts` makes only the changed paragraphs, in minutes; then deploy with `--audio`. Every piece ever made is kept in `var/tts/chunks/`, so nothing is made twice.

Boson's licence requires its acknowledgment, "This audio was created with Boson AI's Higgs Audio", beside the audio. `sources.toml` carries it as the source's `credit`, and Settings and the player show it. The licence allows the name only as that acknowledgment, so the voice is called "AI voice".

---

## Visits

The site counts its visitors itself, server-side, so a page carries nothing for it: no script, and no cookie for readers. `ubsite/visits.py` is an ASGI middleware that notes each request on a queue and goes on. A thread in each worker writes the queue to **`var/visits.db`** every two seconds, kept apart from `ub.db` so that a deploy never touches it. Each address is placed (country, region, city) and hashed with a salt that is replaced every UTC day, and then dropped. **No IP address is stored.** The cost to a page is lost in the noise: on the development machine a section page took a median 3.75 ms with it on and 3.76 ms with it off.

The numbers are on **`/stats`**, behind a password:

```
make geoip                                # DB-IP City Lite -> var/geoip/ (monthly; deploy ships it)
ssh pi5 'cd ~/ubsite && .venv/bin/python -m ubsite.stats passwd'   # prints a password, once
```

Each host counts its own visitors, in its own `var/visits.db`, and has its own `/stats`. The VPS has a copy of pi5's `var/stats.passwd`, so one password opens both. Without `var/stats.passwd`, `/stats` is a 404. The browser that logs in gets the cookie `ub_me=1`, and its own visits stop counting; the page has a link to count them again. The page shows:

- visits per day;
- countries and their cities;
- how each visit arrived, and every link from another site;
- the sections, papers and concepts read;
- every search, and **the searches that found nothing**;
- what is listened to, by voice;
- links shared into chats and posts (their preview fetches);
- devices, browsers and languages;
- the text API's callers, each by the name its User-Agent gives, with the version it holds;
- crawlers;
- pages not found;
- the latest 50 views.

`ubsite/stats.py` derives all of it at report time: which agents are bots, which referrers are external, what kind of page a path is. A *visit* is one browser on one UTC day, so a reader who comes back tomorrow counts twice. A view counts as a person's only if its visitor-day also fetched `/static/ub.css` and its user agent is no known bot.

`UB_VISITS=off` turns the counter off; `make test` sets it.

---

## The 1955 readings and their reasons

Wherever the text departs from the 1955 first printing, the press TeX carries the 1955 reading (`\fnc`, 180 of them). On the site each is a small ring above the words that changed. A click opens a card under the line, with the 1955 reading as the press gives it, and the **SRT Committee's decision and its reasons**. The committee's page has errors of its own, and misquotes the 1955 text in places, so the card takes from it only its reasons, under its name. What 1955 printed is the press's to say. Without JavaScript, and in print, the same words are the section's endnotes. The EPUB has them as pop-up notes. Settings → "1955 readings" turns them off. Search finds them too, by the reading and by the committee's reasons, once Settings → "1955 readings in search results" is on (it is off by default): a 1955 spelling that today's text no longer has, such as *Badanon* or *forego*, then leads to its paragraph with the card open. The build keeps what each card says in `footnote_fts`. All 180 stand in one list, the List of 1955 readings at `/lists/1955`, by paper; there, and among the search results, each ring opens its card as it does in the text.

The reasons are the joint Fellowship–Foundation committee's, published by the Fellowship at https://members.urantiabook.org/text-standardization-Urantia-Book, the page the printed preface sends readers to as `urantiabook.org/SRT`.

- **`data/srt/considerations.html`** is a snapshot of the page's two tables of entries, exactly as served, with a header naming the URL, when it was fetched and the page's SHA-256. `make data` reads only the snapshot, never the network.
- **`build/srt.py`** reads it into `srt_item`, one row per change considered (319): its 1955 text, the verdict and the reasons, with links rewritten to our paragraphs. It then pairs each 1955 note with the change it shows (`footnote.srt_item_id`). An entry's reference is the Foundation's, mapped to ours through `uf_paragraph`.
- **`tests/known-srt-deltas.tsv`** lists, exactly, what does not pair one to one:
  - the 13 notes the page has no entry for;
  - the 5 whose entry is not "Adopted" though the text changed;
  - entries labelled "Adopted" that no note pairs with: in every case the 1955 printing already reads as our text does (the page swaps its columns at 85:4.1, and lists five places *Caesarea-Philippi* occurs as if they were changes);
  - the page's own slips, in its links and in quoting the 1955 text.

  A disagreement between the page and the press is settled by the 1955 printing itself, the Guardian plates in the press repo, never by the page alone.

To refresh it:

```
make srt-snapshot                       # fetches the page, keeps its two tables
git diff data/srt/                      # what the Fellowship changed
make data && make check                 # srt-undeclared / srt-declared-gone name what moved
```

Then update `tests/known-srt-deltas.tsv` and the SRT counts in `check_db.py` and `verify/expectations.toml`, and commit them all together.

## The text API

Other sites keep their own copies of the English text, and **`/api/v1`** lets them keep those copies in step with this one. **`/api`** documents it for them, with a client in Python.

The protocol is a **text version**. A site keeps the number it was last sent, and asks `/api/v1/text?since=N`. It gets every record new or changed since N, the keys of any removed, and the new number. Asked from 0, the reply is the whole text: 3 MB gzipped. A record is a part, a paper, a section or a paragraph, each with a hash for checking a copy. A paragraph is sent as HTML alone, the red letter and italics included; stripping its tags gives the plain text exactly. It also carries the Foundation's numbering (`uf_ref`), its 1955 page (`page_1955`), what stands before it, a separator's stars (`separator_before`, else `null`) and whether it begins a 1955 group, the site's ¶ (`group_before`), its `kind`: `prose`, `verse` (set one to a line) or `heading` (0:12.10), whether it is a line of verse set in further (`setoff`), and its 1955 readings: an empty `<span class="v1955">` in `html` where each stands, and `readings_1955`, what the 1955 printing reads there, in the same order.

A site may also ask for **a passage or a paper by reference**: `/api/v1/paragraphs/101:4.2-7,5:1.3,61:4` (paragraphs, ranges across sections and papers, whole sections) and `/api/v1/papers/0,101-103`. The reply holds the same records, byte for byte, in reading order and each once, with the section, paper and part each paragraph stands in. It has no `since`, `full` or `removed`, because it is not a step in keeping a copy. `?numbering=uf` reads the references as the Foundation numbers them. `/paragraphs/` refuses a bare number with a 400, because the index's `61:4.3,4` would otherwise fetch all of Paper 4. A reference not in the text is a 404 that lists each one under `missing`. The text version does not move for any of this.

- **`build/versions.py`** makes the versions. `ub.db` remembers no earlier build, so the history is a ledger in **`data/text/`**, checked in and append-only like `data/slugs.tsv`. A build that changes anything a site receives appends a version; one that changes nothing, which is almost every press commit, does not. The ledger is written only after the build passes, and `check_db` requires that it describes the database.
- **`build/foundation.py`** gives every paragraph and section the Urantia Foundation's reference, `uf_ref`, beside ours. It reads them from the Foundation's own HTML (SRT v1.22, a zip in the press repo). The two numberings differ in 106 paragraphs, and sites join their translations by the Foundation's. Both number the ACKNOWLEDGMENT 0:12.10, though the Foundation prints no number beside it. The differences must be exactly the runs in `tests/known-uf-refs.tsv`, or the build fails.
- **`ubsite/api.py`** only selects the stored records and concatenates them. Each worker keeps each reply gzipped, so the whole text is compressed once per deploy. Replies carry an ETag (a site that is up to date gets a 304) and `Access-Control-Allow-Origin: *`.
- **Calls are counted apart from page views**, in `api_call` in `var/visits.db`. `/stats` lists each caller by its User-Agent, which `/api` asks every site to set to its own name.
- **The licence:** the English text is public domain; credit is requested, not required (Tigran, 2026-10-11). The edition as a whole, with its index, is CC BY-NC-SA 4.0, as `/api` and every page's footer say (Tigran, 2026-10-14).
- **nginx** rate-limits `/api/` per address, with a burst of 5. The limit is 40 a minute while the first sites are built against the API, and is to come down to 10, since a syncing site needs one request a day. Every machine on this LAN shares one public address, and so one bucket.

`tests/test_api.py` builds a second database with one paragraph edited and one removed, and checks that the version after sends exactly those, and that a passage asked for by reference is the current text. `tests/test_versions.py` checks, on synthetic states, that a site at any version reaches the newest.

---

## The short form

```
make sources                         # what a build would read
make vendor-check                    # fails? review the diff, make vendor-sync, commit
make data && make check && make offline && make test
make serve                           # look; Ctrl-C
git status                           # commit anything here first, data/text/ above all
./deploy/deploy.sh
curl -s https://ubsite.ddns.net/healthz https://ubsite.sigmaai.au/healthz
```

---

## If a deploy goes wrong

- **The code:** check out the previous commit here and run `./deploy/deploy.sh --no-data`.
- **The index:** because the index is read at a revision, a bad index commit can be stepped round. Set `rev = "<good sha>"` under `[index]` in `sources.toml`, deploy, and put `HEAD` back once the index is fixed.
- **The database** on the hosts is derived and is never backed up. Rebuilding is the restore.

---

## Towards automation

- `make sources` against `/healthz` is the whole "is the site behind?" test, so a scheduled job can ask it without a person.
- The build must run on this machine: the hosts have no sources and need none.
- A changed vendored file stops the build **on purpose**. An automated update should stop there, report the diff, and wait for a person, rather than run `vendor-sync` itself.
