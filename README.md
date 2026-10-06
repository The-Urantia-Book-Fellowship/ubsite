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

The footer of every page names the commits the database was built from:

> Text (3983645): the Uversa Press edition. Index (b12500f): the Uversa Press index …

Hover over either ID for the full commit and its date.

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
  the footer would say `-dirty`, and the commit alone could not reproduce it.

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
  paragraphs, red-letter and em spans, 1955 notes, and chronology events. Change the
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
and check the footer's two IDs. To serve in the background, run `make serve-bg`, and
stop it with `make stop`. **Never** use `pkill -f` (see CLAUDE.md §6).

### 5. Commit

Commit anything that changed in this repository: the vendor adoption, a moved count.
`deploy.sh` rsyncs the working tree as it stands, and what runs on pi5 should be a
commit. There is no git remote; the history lives here.

### 6. Deploy

```
./deploy/deploy.sh               # rebuild + check here, ship code and database, restart
./deploy/deploy.sh --no-data     # code or templates only; leave pi5's database alone
```

The script:

1. runs `make data` and `make check` again, so a deploy never ships an unchecked
   database;
2. rsyncs the code to `pi5:/home/tigran/ubsite`, without `.git`, `.venv`, `var/`
   or `export/`;
3. ships `var/ub.db` as `ub.db.new` and `mv`s it into place, so a half-copied file is
   never the one being served;
4. runs `uv pip sync` in pi5's venv;
5. runs `sudo systemctl restart ubsite`. This is password-free: the sudoers drop-in
   from `deploy/README.md` step 4 allows exactly that and nothing else;
6. polls `/healthz` for 30 s, and prints the unit's status if it never reports ok.

It takes about a minute. The script refuses to run on pi5 against its own live tree.

### 7. Verify live

```
curl -s https://ubsite.ddns.net/healthz      # ok:true, and the commits from `make sources`
curl -s https://ubsite.ddns.net/2:5.12 | grep -c 'loses sight of love'
```

Then look at the page and its footer in a browser.

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
