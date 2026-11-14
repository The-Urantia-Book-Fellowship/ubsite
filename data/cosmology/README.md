# The chart of the personalities

Alexander Alyuev's "Cosmology of Personalities in the Urantia Book" (https://github.com/alyuev/UniverseGenealogy_UrantiaBook_2D), which the site draws at `/cosmology`: the orders of personalities, each a card where it has its origin, in the units of the universe from Paradise to Urantia, and the lines of origin, of service and of ascent between them. His repository draws it in the reader's browser; here it is data, held to the book and drawn by the site (`ARCHITECTURE.md`, The chart of the personalities; `DECISIONS.md`, the same).

## His, and on what terms

The chart in his repository, its structure, its words in both languages and its engine are Alexander Alyuev's; the page at `/cosmology` is the site's, drawn from his data. He suggested joining it to this site; his repository has no licence file as of the commit below, and Tigran asked him on 2026-11-13 under what terms it may be used and how he is to be credited. This section is to say the terms when he answers. The site credits him for the data, "Data source by Alexander Alyuev", with his version and his name the link to his repository (Tigran, 2026-11-14: the page that draws it is the site's, and what is his is the data; `DECISIONS.md`, The chart of the personalities); how he himself would be named, if otherwise, is still his to say.

## `chart.json`, the snapshot

Made by `make cosmo-snapshot` (`tools/cosmo/snapshot.py`) from his repository at the commit `sources.toml` `[cosmology]` names, and **never edited by hand**: a slip in it is a slip of his, to be told to him and mended there. It holds, a record to a line:

| | |
|---|---|
| `source` | his repository's address, the commit and its day, his version |
| `canvas` | the size his page drew, a card's size, and how far apart a line's ends are before he calls it far |
| `classes`, `groups`, `functions` | the three keys a card is drawn by, each with its colour and its name in each language |
| `units` | the tree, a parent before what it holds: its colour, whether a line may end at it (`linkable`), his references, its name and what it is, its `box` on the canvas, and how wide his page drew its `title` in each language |
| `persons` | each with its class, its `origin` (a letter to each Deity it comes of, `T` the Trinity as one, `A` an Absolute, `E` evolutionary), its groups and functions, his references, its `pair`, and its words: `name`, `aka`, `desc`, `serves` (how it serves where it is drawn again) and `there` (its name there) |
| `places` | the cards: a personality in its unit, its row and its place in the row, and `at`, its corner on the canvas; `~michael` is Michael drawn again where he serves |
| `links` | each line's two ends and its type, and its `route` in each language: the corners it turns at |

What his data does not hold, the boxes and the routes, is read out of his own built page, `dist/cosmology.html`, opened unmodified in Chrome with the network closed to it, once in each language: a unit's title is in the lines' way, as wide as his page's font drew it, so the routes differ by language (94 of the 153 at his 1.2.3). The tool stops if the page's data is not what the commit's YAML makes, if the boxes differ by language, or at a key it does not know. The same commit makes the same file on this machine, whose fonts the titles were measured in.

## Refreshing it

```
git -C ../UniverseGenealogy_UrantiaBook_2D pull   # his repository, a master: read, never written
make cosmo-snapshot                               # needs Chrome; writes chart.json, or says it is unchanged
git diff data/cosmology/                          # what he changed: review it
make data && make check                           # the gates below
.venv/bin/python tools/cosmo_e2e.py               # the page in Chrome: the titles within his widths, above all
```

Then `verify/expectations.toml` `[cosmology]`, a line in `ChangeLog.md` described from the diff, and a commit of them together. `deploy.sh` refuses while anything here is not committed.

## What the build holds it to

Each a hard failure of `make data` (`build/cosmo.py`, `build/readers/cosmo.py`):

- **its shape**: every id one; every personality on one card where it has its origin; every card inside its unit and over no other; every line from the edge of one card, or of a unit a line may end at, to the edge of another, level or upright all the way, through no third card;
- **the book**: every reference a paper or a section there is;
- **the words**: every name and other name in the text, the English in the press's and the Russian in the Foundation's translation, which his `lang/ru.yaml` says its terms follow, by his own validator's rule (any ending). A name that is his own wording would be listed in `tests/known-cosmo-terms.tsv` (`id`, `lang`, `term`, `why`), and the build wants exactly that list; there is none so far;
- **the index**: every slug in `headwords.tsv` a headword's.

## `headwords.tsv`, ours

A unit's or a personality's headword in the index, where its name is not a headword as written: `id` (his), `slug` (the headword's address, `/i/<slug>`), `why`. Reviewed by Tigran. A name or another name that is a headword as written is found by itself and needs no line; one with two headwords has two. What has neither is listed by `make check`.
