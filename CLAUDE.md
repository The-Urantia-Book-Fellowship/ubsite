# ubsite

An interactive presentation of the Urantia revelation: the Uversa Press text
read together with the Uversa Press index, so that the index works in both
directions — from a concept into the text, and from any paragraph back to
everything the index says about it.

The plan this was built from is `~/.claude/plans/have-a-look-at-fluttering-peacock.md`.
`ROADMAP.md` beside this file is the survey of what the data makes possible —
seventeen ideas ranked, with what to build and what deliberately not to.

Read §0 and §1 here first; `ROADMAP.md` for where this is going; the plan for
the phase-by-phase detail.

---

## 0. The one thing to understand

**The product is the database.** The website, a future API, and any export are
views over `var/ub.db`. Three LaTeX projects are read, verified against
independent evidence, and loaded into one queryable store. If you are tempted to
put logic in a template or a route that belongs in the build, don't.

The second thing: **the three source repos are masters and are never written
to.** Not their `tex/`, not even their gitignored derived directories. This is
enforced mechanically, not by good intentions — see §6.

---

## 1. The sources

Paths live in `sources.toml` and **nowhere else**; `build/config.py` is the only
module that reads it.

| key | repo | what it supplies |
|---|---|---|
| `press` | `../urantia-uversa-press-claude` | the authoritative text |
| `study` | `../urantia-study-edition` | apparatus: footnotes, human sources, KJV, quiz, images *(not yet imported)* |
| `index` | `../index` | the Uversa Press index, revised for the seventh printing |

All three share one address space: the `\vs` macro addresses `\vs p133 1:3` (a
Urantia paragraph) and `\vs Gen 1:1` (a Bible verse) alike.

The index is read **at HEAD** and the revision recorded in the build, because
that repo is under active editorial work. Count gates against it are therefore
reported bands; structural gates stay hard.

Careful: there are three `urantia-study-edition` trees on this machine.
`urantia-study-edition-latest` is the **oldest**. `sources.toml` pins the right one.

---

## 2. Commands

```
make venv           create .venv (uv) and sync requirements.txt -- run this first
make lock           recompile requirements.txt from requirements.in
make sources        the three repos and the revisions in use
make vendor-check   re-hash the vendored copies against upstream (fails with a diff)
make data           build var/ub.db          (~14 s)
make check          every gate               (~8 s; rebuilds the oracles first)
make test           the never-write-to-a-master guards
make paranoid       fingerprint all three trees, build, and prove nothing moved
make serve          the reader on 127.0.0.1:8130
make stop           stop it (by pid — never by pattern, see §6)
```

`make data` never edits in place: it builds `var/ub.db.tmp` and swaps it in, so a
failed build leaves the previous database untouched.

---

## 3. What is built

**Phases 0–5 are done.** The annotated reader runs.

- `build/` — LaTeX → `var/ub.db`, stdlib only
  - `expand.py` — the span-emitting expander. Plain text plus code-point spans.
  - `press_macros.py` — derived from press's own table, with 5 overrides; asserts
    key-set equality, so a new macro upstream fails our build too
  - `index_macros.py` — the index's closed 24-macro set, plain and HTML renderers
  - `readers/` — pure file → dataclasses; `_io.py` is the only module allowed to
    open a source path, always mode `'r'`
  - `render.py` — `(text, spans) → HTML`. **The only renderer.**
  - `load.py`, `derive.py`, `schema/*.sql`, `oracle.py`, `fonts.py`, `slugs.py`
  - `checks/` — the gates
- `ubsite/` — FastAPI + Jinja2, server-rendered, no build step, ~10 KB CSS, 556 B JS
- `vendor/` — copied by value with `UPSTREAM.lock`: press's tokenizer/macros/
  normalize, index's `cite.py`/`xref.py`
- `.venv/` — `uv venv` + `uv pip sync requirements.txt`, gitignored;
  `requirements.txt` is compiled from `requirements.in` with `uv pip compile`.
  Same arrangement as `../libnodes`. **Everything runs under it** — `make` sets
  `PY := .venv/bin/python`, so the build gets fontTools and the server gets
  uvicorn from one place.
  **Python 3.12**, pinned in `.python-version` to match `../libnodes` and
  `urantia-library`: all three will be hosted on the same Raspberry Pi 5 with
  uv-managed venvs, and sharing one interpreter saves fetching and storing a
  second. The full gate suite passes on it, with byte-identical output.

- `deploy/` — the systemd unit, the nginx server block, the sudoers drop-in and
  `deploy.sh`, with a README naming the four steps that need root. Written, not
  yet run. **The database is the artifact**: the three source repos are not on
  pi5 and do not need to be, so `make data` runs here and `var/ub.db` is shipped.

Next: Phase 6 (the study-edition apparatus — `\fnst` notes, KJV, the quiz,
figures behind the rights gate), then 7 (human sources), 8 (chronology, map).

---

## 4. The numbers

Every asserted number lives in `verify/expectations.toml` with `measured_on` and
`source_commit`, **never in code**. `verify/exceptions.toml` is currently empty
and should stay that way.

```
papers 197 · sections 1,626 · paragraphs 14,586
red-letter spans 1,267 · em spans 2,295 · 1955 variant notes 177
index entries 34,625 (32,837 A–Z + 1,351 appendix + 437 chronology events)
citations 39,771 → 50,758 targets {para 47,871, sec 2,254, paper 633}
cross-references 5,133, 0 dangling · headwords 4,736
para_citers 113,846 · cocitation pairs 9,721
```

**The best single structural check** is that every one of the 1,626 sections
numbers its paragraphs 1..N with no gap and no duplicate. It holds in both
editions. A verse block numbered wrongly shows up immediately as a hole.

---

## 5. Three oracles, and what each can prove

The comparison sources are **not the text**. Our text and all its spans come
from our own parse; the oracles exist to prove that parse is right rather than
merely self-consistent.

| source | proves |
|---|---|
| `build_srt.py` output | the plain text of all 14,586 paragraphs |
| press `extract_tex.py` output | the `em` spans, **by offset** |
| press `misc/html/` | dot-leader rows (26), `<sup>` (23), the 1955 page refs |

Both derived oracles are gitignored and regenerate in seconds, so a stale one
would silently describe an older book. `make check` therefore **rebuilds them
first**, by running the sibling projects' own tools unmodified in sandboxes
under `var/` with the inputs symlinked in. Neither tool takes an output path;
both write relative to the working directory, so giving them the right working
directory is the whole trick.

**Nothing external marks the red letter.** The SRT HTML sets "Fear not." plain.
Those 1,267 spans exist only in the press TeX — unverifiable, and the most
distinctive thing the site carries.

Three places where the oracle is wrong and we are right are recorded in
`tests/known-oracle-deltas.tsv`, each arbitrated against the SRT HTML. The gate
requires **exactly** that set: a new disagreement fails, and so does one of these
silently going away.

---

## 6. Rules

**Never write to a source repo.** `build/readers/_io.py` is the only module that
may open a source path. `tests/test_no_writes.py` greps the package for
write-mode opens and for writes near a sibling path; allowlisted writers must
name their target and it must resolve inside this project. `make paranoid`
fingerprints all three trees before and after a build.

**Vendor by value, never `sys.path` into a live sibling.** Press rewrites
paragraph wrappers on every build; the index is edited daily. `make check-vendor`
re-hashes and fails with a unified diff. Refreshing is a reviewed commit.

**Fail loudly.** An unknown macro, an unparseable citation, a span outside its
paragraph, a source line nothing claimed — all are hard failures. The upstream
readers *skip* what they do not recognise; we invert that everywhere.

**Never `pkill -f <pattern>`** where the pattern appears in the command you are
typing. It matches the shell running it, kills itself, and orphans the process.
This is how four dev servers ended up listening at once. Use `make stop`.

**Round-trip is the contract.** Stripping the tags from any rendered HTML must
return the stored text byte for byte — 14,586 paragraphs and 34,625 index
entries, both gated. This is why dot leaders and footnote markers are drawn in
CSS: markup must not inject characters a reader would copy.

---

## 7. Traps, each of which has already cost something

1. **`\tunemarkup` means the opposite thing in the two repos.** Study defines it
   as a conditional *include*; press strips both arguments. One shared macro
   table would silently delete all 84 figures and 19 bibliographies.
2. **`\pc` takes an optional argument**, and `159:1.7`'s text really begins with
   `[`. Reassembling a `\vs` line by concatenation swallowed the whole paragraph
   as a false optional arg. Parse the prefix and the body separately.
3. **`\kern-1pt` takes an unbraced length**; `\makeatletter` lines are a skip region.
4. **`\itshape` switches to italic for the remainder of its group**, wherever in
   the group it appears — in the one live case (`0:12.10`) it sits after an
   `\hspace*`, so testing the leading token misses it.
5. **Appendix A contains no `\iapp`.** Keying an appendix reader on it imports A
   as empty — the exact bug that hid its 470 citations from every check in the
   index project until 2026-09-13.
6. **`\chrontext` vs `\chronsubtext` is the parentage signal, not document
   position.** A `\chrontext` can follow a `\chronmonth` and still hang off the
   year. `read_pack.py` gets this subtly wrong; don't copy it.
7. **The terminal period on a headword is a convention with 15 documented
   exceptions**, not a rule — the index project's CLAUDE.md §13 records that
   assuming one "set 373 lines wrong". Classify by what the second argument
   *contains*.
8. **`xref.fold()` collides**: 4,736 headwords → 4,734 folded keys. Never a key.
9. **`p139` has no section 10.** `\usectiontwo{9 and 10}` is one heading over one
   block; paragraphs run `139:9.x` then jump to 11. Sections are derived from
   paragraphs, with `combined_with` recording the second number.
10. **One cross-reference resolves to seven headwords** — `Master Spirit #1 – #7`.
    `xref` records a `route` (`head` / `conjunction` / `range`); the gate requires
    a route, not a head.
11. **Two indexes are load-bearing for build time**: `paragraph(paper_n,
    section_n)` and `citation_target(entry_id)`. Without the second, `entry_stats`
    runs 34,600 × 50,758 × 3 row scans and the build never finishes. It is 7 s with
    them.
12. **The study edition's `extracttext.py` truncates ~2/3 of its footnotes**
    (`[^}]+` against nesting three deep). Do not reuse it when Phase 6 lands.

---

## 8. Decisions on the record

- **One mode.** Reading mode was removed; the study apparatus is always on. The
  individual elements become switches under **Settings** — red letter, the margin
  index, paragraph numbers, the 1955 variants — rather than one coarse lever.
- **Slugs are data, not a function.** `data/slugs.tsv` is checked in and
  append-only. A headword keeps its slug for ever; collisions get a recorded
  numeric suffix (11 so far). A permalink that moves because someone improved the
  slugifier is a broken permalink.
- **An exact headword match wins the search.** bm25 has no notion that a query
  names an entry, so headwords are resolved separately: exact, then prefix, then
  full text.
- **Index chips carry concepts, not numbers.** `path_plain` strips the citations
  and the terminal period; on paper the numbers *are* the entry, on screen the
  chip is a link.
- **Blanket citations appear once** at the section head, never repeated under
  every paragraph. This is `read_pack.py`'s rule and the reason Paper 15's 470
  citations are readable.
- **`/101` redirects to `/101:0`.** Every paper opens with an introduction, and
  the section list is always in the left rail.
- **UB Goudy is OFL 1.1** — verified in the name table, a correctly renamed Sorts
  Mill Goudy derivative — so the site serves the book's own face, subsetted to
  the corpus with a gate that fails on a missing glyph. **Goudy Handtooled BT is
  Bitstream proprietary and must never be served.**

---

## 9. Things the editor has asked for, and facts easy to get wrong

- The index is **bound with the text in a single volume** for the seventh
  printing (third edition, 2026) — *not* a standalone volume. `tools/press/build_press.py`
  in the press repo: `book | pad | index | pad`, 2,192 pages, fixed by the spine
  width of an already-printed case.
- Say **"numerous corrections"**, not a number — the count is still moving and
  prints in October.
- Do not disparage the printed index. It is the achievement this site depends
  on. An early draft said it "has never been anything but ink" and that was
  rightly cut.
- The site will be shown to the Executive Director of the Urantia Book
  Fellowship. Tone accordingly.
- The study edition's paragraph numbering was aligned to press on 2026-09-21
  (commit `8af25c5`): ten numbered separators de-numbered, and `0:12.10`
  ACKNOWLEDGMENT restored as a numbered paragraph. Both editions now hold at
  14,586 with no gaps.

---

## 10. Open questions

Carried from the plan, none blocking:

1. **Index rights** — publishing 32,837 entries as queryable data is a stronger
   act than quoting from it. The design keeps an `INDEX_MODE` switch so a change
   of footing is a config edit.
2. **Trademark, not copyright**, is the likely first letter. The 1955 text is
   public domain in the US; "Urantia" and the concentric circles are marks. The
   footer carries a non-affiliation line; do not use the symbol.
3. **Site licence** — the press repo is CC BY-NC-SA 4.0, and NC forecloses most
   of what a public API is for.
4. **Domain and host**; whether `urantia-library` on this box merges or coexists.
   Port 80 is reportedly not forwarded, which affects certbot.
5. **The 58 rights-restricted images** — attribution cards, or seek permission.

---

## 11. Where we left off (2026-09-21)

The annotated reader is running and looks right. `make serve` → 8130.

Everything through Phase 5 is committed in seven commits, the last four of
which are typography: the site was set too small and wanted 150% browser zoom
to be comfortable, which is a Goudy problem — small x-height, long descenders,
so it reads a full step below its nominal size.

**One open question, not a defect.** On a concept page the first line of the
tree repeats the heading: `/i/adoption` shows "adoption" under the `<h1>`
"adoption". On `/i/oaths` the same line reads "oaths. *See also* promises" and
earns its place, because the level-1 entry carries citations and cross-
references. Suppressing it when it adds nothing was offered and not yet ruled on.

**Next is Phase 6**, the study-edition apparatus, and it is the largest
remaining import: 307 `\fnst` study footnotes, 54 human-source `\bibitem`
records, 86 `\bibref` cross-references, the whole KJV (24,974 verses + 5,069
marginal notes), 819 quiz questions (**83 of them multi-answer** — a
single-answer model marks correct responses wrong), and 84 figures of which
**58 are rights-restricted** and must be separable at query time.

Note when starting it: the study edition's own `tools/extracttext.py` truncates
about two thirds of its footnotes (`[^}]+` against braces nested three deep),
and `\tunemarkup` there means the opposite of what it means in press — see §7.

The plan's later phases (human sources, chronology and map, deploy) are
unchanged; read them in the plan file rather than duplicating them here, and
`ROADMAP.md` for why each is worth doing.
