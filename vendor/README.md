# vendor/

Five files copied by value from two sibling repositories. They are pinned by SHA-256 in
`UPSTREAM.lock`, and `make vendor-check` fails if either side moves (CLAUDE.md §6). They
are copies, never edited here; adopting a change upstream is `make vendor-sync` and a
reviewed commit.

| here | copied from |
|---|---|
| `press/latex_tokenizer.py` | the press repository, `tools/text-verify/latex_tokenizer.py` |
| `press/macros.py` | the press repository, `tools/text-verify/macros.py` |
| `press/normalize.py` | the press repository, `tools/text-verify/normalize.py` |
| `index/cite.py` | the index repository, `cite.py` |
| `index/xref.py` | the index repository, `xref.py` |

## Licence

All five were written by Tigran Aivazian, who makes them available here under the GNU
Affero General Public License v3.0, as the rest of this repository is (`../LICENSE`).

Their home repositories keep their own terms. The press repository is licensed as a
whole under CC BY-NC-SA 4.0, and the index repository states no licence; neither changes.
Nothing here licenses the text of *The Urantia Book*, the Uversa Press edition or the
Uversa Press index, which these files only read.
