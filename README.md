# ubsite

The Uversa Press text of *The Urantia Book* read together with the Uversa Press
index, live at **https://ubsite.ddns.net**.

This file is the operating manual: how to bring the site up to date when its
sources change, and how to deploy it. For how it is built and why, read
[`CLAUDE.md`](CLAUDE.md). For where it is going, read [`ROADMAP.md`](ROADMAP.md).
The one-time root setup on pi5 (the unit, the certificate, nginx, sudoers) is in
[`deploy/README.md`](deploy/README.md). It is done and need not be repeated.

---

## The one idea

**The site shows `var/ub.db`, and nothing else.** That file is built on this machine
from three sibling repositories and shipped to pi5. Nothing updates by itself. When
the index session commits a correction, the site carries it only after someone
rebuilds and deploys. Until then, a paragraph can say "no entry cites this paragraph
precisely" while the index plainly cites it.

The footer of every page gives the date of each commit the database was built from:

> Text (2026-10-03): the Uversa Press edition. Index (2026-10-03): the Uversa Press index …

Hover over either date for the full commit ID. Each date links to its commit
on GitHub, at the `url` that `sources.toml` gives each repository. Both repositories
are **private**: a link opens for members of The-Urantia-Book-Fellowship who are
signed in, and is GitHub's 404 page for everyone else. That is a decision on the
record, not an oversight. Delete a `url` and rebuild to drop its link.

---

## Setup, once

The three source repositories must be at the paths `sources.toml` gives, relative to
this directory:

| key | path | read |
|---|---|---|
| `press` | `../urantia-uversa-press-claude` | from the working tree |
| `index` | `../index` | **at HEAD**, never the working tree |
| `study` | `../urantia-study-edition` | by `make check` only, until Phase 6 |

Then:

```
make venv          # .venv on the pinned Python 3.12, from requirements.txt
make sources       # the three repos and the commits a build would read
```

Merritt Horn's recordings must be at `/Audio/Urantia/Urantia-MH-Audio-DVD`, here **and
on pi5**: the build lists them, and the site on pi5 serves them from that path. They are
the Uversa Press DVD's MP3s (128 kbps stereo), copied once with the folder names
lowercased. `/Audio/Urantia/Urantia-MH-Audio` is a 32 kbps transcode of the same
recordings and is not used. `sources.toml`
names it under `[audio.mh]`. They are a master like the repos, and nothing writes to them.

---

## Updating the site

### 0. Is the live site behind?

```
curl -s https://ubsite.ddns.net/healthz
make sources
```

`/healthz` returns the full commit of each source the live database was built from:

```
{"ok":true,"paragraphs":14586,"built_at":"2026-10-06T14:28:35",
 "sources":{"press":{"commit":"39836454…","dirty":false},
            "index":{"commit":"b12500f4…","dirty":false}}}
```

`make sources` prints the commits a build would read now. If either differs, the
site is behind.

Two rules decide what a build sees:

- **The index is read at HEAD.** Uncommitted work in `../index` never reaches the
  site, by design: the index is edited in another session, and a build must not race
  an edit in progress. If a correction is missing, first check that it is
  *committed* there, with `git -C ../index log -1`.
- **Press is read from its working tree.** `make sources` marks it `+dirty` if a
  tracked file has uncommitted changes, or if `tex/` has an untracked file. An
  untracked directory elsewhere in press does not count. Do not deploy a dirty build:
  the footer would say `(2026-10-03, dirty)`, and the commit alone could not
  reproduce it.
- **Push the source commits.** The footer links to them on GitHub. If a commit is
  on no remote branch as of the last fetch, `make data` warns `source-not-pushed`.
  The link is then a 404 even for members, until that commit is pushed.

To ask whether one paragraph is cited in the database you have built:

```
sqlite3 var/ub.db "SELECT COUNT(*) FROM citation_target ct JOIN paragraph p
  ON p.id = ct.paragraph_id WHERE p.ref = '2:5.12' AND ct.precision = 'para'"
```

### 1. `make vendor-check`, and when it fails

Five files are copied by value from the sources into `vendor/`, and their hashes are
recorded in `vendor/UPSTREAM.lock`:

- `latex_tokenizer.py`, `macros.py` and `normalize.py` from press's `tools/text-verify/`;
- `cite.py` and `xref.py` from the index.

`make data` runs `vendor-check` first. If upstream has moved, the build stops and
prints a unified diff:

```
vendor: UPSTREAM MOVED  press:tools/text-verify/macros.py
--- vendor/press/macros.py
+++ …/urantia-uversa-press-claude/tools/text-verify/macros.py
+    "fill":          Spec(STRIP, note="infinite glue inside \\vspace*{\\fill} …"),
```

This is deliberate. Adopting upstream code is a reviewed commit, never a side effect
of a build. Read the diff and decide:

| the change | what to do |
|---|---|
| a `note=` or a comment only | adopt; nothing in `build/` reads `Spec.note` |
| a new `STRIP`, `EMIT_TEXT`, `EMIT_ARG`, `EMIT_SUP`, `EMIT_ARG_ITALIC` or `STRUCTURAL` macro | adopt; `build/press_macros.py` translates these automatically |
| a new action name | adopt, then `make data` fails with "has no translation": add it to `_TRANSLATE` in `build/press_macros.py` |
| a change to a macro named in `OVERRIDES` (`textcolor`, `fnc`, `pc`, `ublistelem`, `bibdf`) | think: our override hides upstream's change, which may be what is wanted, or may not |
| anything in `cite.py` or `xref.py` | adopt, and expect `make check`'s citation and cross-reference counts to move; explain any change |

To adopt:

```
make vendor-sync          # copies all five files and rewrites the lock
git diff vendor/          # only what you reviewed, plus the lock's commit fields
git commit -am 'vendor: adopt press macros.py at 3983645 (\fill, stripped)'
```

Keep the message form: `vendor: adopt <repo> <file> at <short sha> (<what changed>)`.
See `git log -- vendor/` for examples.

### 2. `make data`

Builds `var/ub.db` in about 14 seconds. The first two lines say what it is reading:

```
reading press text, worktree at 3983645 ...
reading index at b12500f ...
```

The build writes `var/ub.db.tmp` and moves it into place only on success, so a
failed build leaves the previous database untouched. Failures are loud by design. An
unknown macro, an unparseable citation, or a source line that nothing claimed is a
hard error, listed under `problems`. A macro that is new to the press TeX must first
be taught to press's own `tools/text-verify/macros.py`, and then adopted as in step 1.

### 3. `make check` and `make test`

```
make check        # every gate, about 8 s, after rebuilding the oracles from the sources
make test         # unit tests, including the never-write-to-a-master guard
make paranoid     # optional: fingerprint the three trees, build, prove nothing moved
```

When a gate fails because a source *legitimately* changed a number:

- **Hard counts** are in `QUERIES` in `build/checks/check_db.py`: papers, sections,
  paragraphs, red-letter and em spans, 1955 notes, chronology events, and the entries
  of each of Appendices B–F (the index's own `check_tex.py` asserts the same). Change the
  number, and add a comment naming the source commit and the reason. The `436` there
  is the model: index `6cd4d19` dropped one chronology event by ruling.
- **Index counts** (entries, citations, targets) are reported, not asserted, because
  the index is under daily editorial work.
- **The `tests/known-*-deltas.tsv` files** list the places where an oracle is wrong
  and we are right, and must match *exactly*. A new disagreement, or one that silently
  disappears, fails the gate. Decide it against the SRT HTML before changing the list.

### 4. Look at it

```
make serve        # http://127.0.0.1:8130, in the foreground; Ctrl-C to stop
```

Open the paragraph that prompted the update, for example `http://127.0.0.1:8130/2:5.12`,
and check the footer's two dates, and the commit IDs in their tooltips. To serve in the background, run `make serve-bg`, and
stop it with `make stop`. **Never** use `pkill -f` (see CLAUDE.md §6).

### 5. Commit

Commit anything that changed in this repository: the vendor adoption, a moved count.
`deploy.sh` rsyncs the working tree as it stands, and what runs on pi5 should be a
commit. Then `git push`: the history is kept on GitHub, in the Fellowship's private
repository `The-Urantia-Book-Fellowship/ubsite`.

### 6. Deploy

```
./deploy/deploy.sh               # rebuild + check here, ship code and database, restart
./deploy/deploy.sh --no-data     # code or templates only; leave pi5's database alone
./deploy/deploy.sh --audio       # also copy the AI voice first, after `make tts` changed it
```

The script:

1. runs `make data` and `make check` again, so a deploy never ships an unchecked
   database, and checks that pi5 holds every recording the database serves, at the
   path and size it records;
2. rsyncs the code to `pi5:/home/tigran/ubsite`, without `.git`, `.venv`, `var/`
   or `export/`;
3. ships `var/ub.db` as `ub.db.new` and `mv`s it into place, so a half-copied file is
   never the one being served;
4. copies `var/geoip/dbip-city-lite.mmdb` when `make geoip` has changed it (the visit
   counter's places; see [Visits](#visits)), and runs `uv pip sync` in pi5's venv;
5. runs `sudo systemctl restart ubsite`. This is password-free: the sudoers drop-in
   from `deploy/README.md` step 4 allows exactly that and nothing else;
6. polls `/healthz` for 30 s, and prints the unit's status if it never reports ok.

It takes about 30 s, mostly the rebuild and the gates. The script refuses to run
on pi5 against its own live tree.

### 7. Verify live

```
curl -s https://ubsite.ddns.net/healthz      # ok:true, and the commits from `make sources`
curl -s https://ubsite.ddns.net/2:5.12 | grep -c 'loses sight of love'
```

Then look at the page and its footer in a browser.

---

## Listening

Every section can be heard in Merritt Horn's reading, and from any paragraph once his
reading is aligned. The player and the Settings dialog are `ubsite/static/listen.js` and
`ub.js`. The build turns the recordings into the tables `audio_source`, `audio_file` and
`audio_segment`, through `build/audio.py`, from three checked-in files in `data/audio/`:

| file | what | made by |
|---|---|---|
| `mh-files.tsv` | every MP3, with its size, duration and SHA-256 | `.venv/bin/python -m tools.audio.manifest mh` |
| `mh-overrides.tsv` | the three files that break the naming rule, and why | by hand |
| `mh.tsv` | each paragraph's start and end in its file, and how much of it was heard | `make align` |
| `mh-unread.tsv` | paragraphs the recording does not contain | by hand, from the review |
| `mh-low-match.tsv` | paragraphs where the reading and today's text differ | by hand, from the review |

The alignment needs a GPU and runs on this machine only, in its own venv in
`~/Software/ml` (never in `requirements.txt`):

```
make align-venv          # once: faster-whisper and its CUDA libraries
make align-transcribe    # Whisper over all 121 hours on the 3090: about 1.5 h, resumable
make align               # match words to paragraphs, cut in the pauses: seconds
make align-repair        # re-hear, unbatched, what came out mostly unheard
make align               # again
less var/align/mh-review.tsv   # the paragraphs whose reading differs from the text
```

`make check` holds the differences to `mh-low-match.tsv` and `mh-unread.tsv`
**exactly**. A text correction that makes the reading and the text diverge shows up
there, and the gate fails until the paragraph is recorded. Use the 3090 alone: the 2080 Ti
drives the display, and under load it reached 88 °C and throttled.

The recordings do not change with the text, so none of this reruns after an ordinary
correction. Rerun it only when paragraphs are added, removed or renumbered.

With Settings' "Follow along" off, the reader can move anywhere on the site while a
section plays. `listen.js` follows the site's links inside the page instead of loading a
new one, so the reading goes on.

### Your browser's voice

Settings also offers the browser's own speech, the Web Speech API. Nothing is recorded:
`listen.js` fetches a section's spoken text from `/speech/<paper>:<section>` (the `speech`
table) and the browser reads it. How it sounds depends on the browser: Google's voices
in desktop Chrome, Microsoft's in Edge, Apple's in Safari. It is offered beside the
recordings, not instead of the AI voice below, because nobody can check what it says,
and because a phone stops it when the screen locks. `listen.js` keeps the screen on
while it speaks.

### The AI voice

The second voice is made here, by Higgs TTS 3 (Boson AI) on the 3090, from the spoken
text the build derives (`build/speech.py`, table `speech`). Each heading and paragraph is
read a sentence or two at a time. Every piece is checked for a drone, a dead pause or a
cut-off end, then heard back by Whisper word by word, and made again at another seed until
both pass (`tools/tts/higgs3.py`, `tools/tts/listen.py`). The pieces are joined into one
MP3 per section under `var/audio/ai/`, which `deploy.sh --audio` copies to pi5. Three
files in `data/audio/` come out of it and are checked in:

| file | what |
|---|---|
| `ai.tsv` | each paragraph's start and end in its section's file, and the SHA of the spoken text it was made from |
| `ai-files.tsv` | every MP3, with its size, duration and SHA-256 |
| `ai-unsettled.tsv` | pieces used although no try was heard exactly as written, with what Whisper heard instead |

```
make tts                 # make what is missing, then assemble: ~27 h for the whole book, resumable
make tts-assemble        # assemble only, from what has been made (no GPU)
```

**Unlike Merritt Horn's reading, the AI voice follows the text.** After a correction,
`make check` fails with "an AI reading is of the spoken text as it is now": the voice
would read words the page no longer says. `make tts` makes only the changed paragraphs,
in minutes; then deploy with `--audio`. Every piece ever made is kept in
`var/tts/chunks/`, so nothing is made twice.

Boson's licence requires its acknowledgment, "This audio was created with Boson AI's
Higgs Audio", beside the audio. `sources.toml` carries it as the source's `credit`, and
Settings and the player show it. The licence allows the name only as that
acknowledgment, so the voice is called "AI voice".

---

## Visits

The site counts its visitors itself, server-side, so a page carries nothing for it: no
script, and no cookie for readers. `ubsite/visits.py` is an ASGI middleware that notes
each request on a queue and goes on. A thread in each worker writes the queue to
**`var/visits.db`** every two seconds, kept apart from `ub.db` so that a deploy never
touches it. Each address is placed (country, region, city) and hashed with a salt that
is replaced every UTC day, and then dropped. **No IP address is stored.** The cost to a
page is lost in the noise: on the development machine a section page took a median
3.75 ms with it on and 3.76 ms with it off.

The numbers are on **`/stats`**, behind a password:

```
make geoip                                # DB-IP City Lite -> var/geoip/ (monthly; deploy ships it)
ssh pi5 'cd ~/ubsite && .venv/bin/python -m ubsite.stats passwd'   # prints a password, once
```

Without `var/stats.passwd`, `/stats` is a 404. The browser that logs in gets the cookie
`ub_me=1`, and its own visits stop counting; the page has a link to count them again.
The page shows:

- visits per day;
- countries and their cities;
- how each visit arrived, and every link from another site;
- the sections, papers and concepts read;
- every search, and **the searches that found nothing**;
- what is listened to, by voice;
- links shared into chats and posts (their preview fetches);
- devices, browsers and languages;
- crawlers;
- pages not found;
- the latest 50 views.

`ubsite/stats.py` derives all of it at report time: which agents are bots, which
referrers are external, what kind of page a path is. A *visit* is one browser on one UTC
day, so a reader who comes back tomorrow counts twice. A view counts as a person's only
if its visitor-day also fetched `/static/ub.css` and its user agent is no known bot.

`UB_VISITS=off` turns the counter off; `make test` sets it.

---

## The short form

```
make sources                         # what a build would read
make vendor-check                    # fails? review the diff, make vendor-sync, commit
make data && make check && make test
make serve                           # look; Ctrl-C
git status                           # commit anything here first
./deploy/deploy.sh
curl -s https://ubsite.ddns.net/healthz
```

---

## If a deploy goes wrong

- **The code:** check out the previous commit here and run `./deploy/deploy.sh --no-data`.
- **The index:** because the index is read at a revision, a bad index commit can be
  stepped round. Set `rev = "<good sha>"` under `[index]` in `sources.toml`, deploy,
  and put `HEAD` back once the index is fixed.
- **The database** on pi5 is derived and is never backed up. Rebuilding is the
  restore.

---

## Towards automation

- `make sources` against `/healthz` is the whole "is the site behind?" test, so a
  scheduled job can ask it without a person.
- The build must run on this machine: pi5 has no sources and needs none.
- A changed vendored file stops the build **on purpose**. An automated update should
  stop there, report the diff, and wait for a person, rather than run
  `vendor-sync` itself.
