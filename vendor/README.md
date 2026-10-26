# vendor/

Nine files copied by value: five from two sibling repositories, two from TeX Live, and two from SQLite's WebAssembly release. They are pinned by SHA-256 in `UPSTREAM.lock`, and `make vendor-check` fails if either side moves (CLAUDE.md §6). They are copies, never edited here; adopting a change upstream is `make vendor-sync` and a reviewed commit.

The SQLite release is not a tree on this machine: `sources.toml` names its zip by URL and SHA-256, and the lock records that digest. A release cannot move, so `make vendor-check` holds the two files to the lock, and the lock to that digest, without the network; `make vendor-sync` fetches the zip, and checks it, only when `sources.toml` names another release.

| here | copied from |
|---|---|
| `press/latex_tokenizer.py` | the press repository, `tools/text-verify/latex_tokenizer.py` |
| `press/macros.py` | the press repository, `tools/text-verify/macros.py` |
| `press/normalize.py` | the press repository, `tools/text-verify/normalize.py` |
| `index/cite.py` | the index repository, `cite.py` |
| `index/xref.py` | the index repository, `xref.py` |
| `tex/hyphen.tex` | TeX Live, `texmf-dist/tex/generic/hyphen/hyphen.tex`: Knuth's hyphenation patterns, which the press sets the book with (`build/hyphen.py`) |
| `tex/hyph-ru.tex` | TeX Live, `texmf-dist/tex/generic/hyph-utf8/patterns/tex/hyph-ru.tex`: Alexander Lebedev's Russian patterns, which polyglossia's `russian` loads, and so both Russian translations' TeX (`build/hyphen.py`) |
| `sqlite-wasm/sqlite3.js` | SQLite 3.53.4's WebAssembly release (`sqlite-wasm-3530400.zip` from sqlite.org), `jswasm/sqlite3.js`: the classic script, which a service worker can load with `importScripts` |
| `sqlite-wasm/sqlite3.wasm` | the same release, `jswasm/sqlite3.wasm`: SQLite with FTS5, which searches the offline copy in a reader's browser (`ubsite/static/sw.js`) |

## Licence

The five Python files were written by Tigran Aivazian, who makes them available here under the GNU Affero General Public License v3.0, as the rest of this repository is (`../LICENSE`).

Their home repositories keep their own terms. The press repository is licensed as a whole under CC BY-NC-SA 4.0, and the index repository states no licence; neither changes. Nothing here licenses the text of *The Urantia Book*, the Uversa Press edition or the Uversa Press index, which these files only read.

`tex/hyphen.tex` is Donald Knuth's, and is copied here unmodified, as its own header requires: "Unlimited copying and redistribution of this file are permitted as long as this file is not modified."

`tex/hyph-ru.tex` is Alexander I. Lebedev's, part of the hyph-utf8 package, under the LaTeX Project Public License 1.2 or later, and is copied here unmodified.

The two SQLite files are SQLite's, which its authors have dedicated to the public domain (https://sqlite.org/copyright.html), and are copied here unmodified.
