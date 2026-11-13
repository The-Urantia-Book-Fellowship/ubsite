-- The chart of the personalities (build/cosmo.py): Alexander Alyuev's
-- "Cosmology of Personalities in the Urantia Book", from the snapshot of his
-- repository in data/cosmology/chart.json (tools/cosmo/snapshot.py).  The
-- orders of personalities, each a card where it has its origin; the units of
-- the universe they stand in, nested from Paradise to Urantia; and the lines
-- between them, of origin, of service and of ascent.  Empty where the
-- snapshot is absent: the page is then not there.

-- What the snapshot was taken from, and the canvas his page drew: url, commit,
-- date, version; w, h, card_w, card_h.
CREATE TABLE cosmo_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- The three keys a card is drawn by, each with its colour: its class of
-- origin, one, which tints it; its groups, the stripes along its top; its
-- functions.  In his order, which the legend keeps.
CREATE TABLE cosmo_key (
  kind  TEXT NOT NULL CHECK (kind IN ('class', 'group', 'func')),
  key   TEXT NOT NULL,
  ord   INTEGER NOT NULL,
  color TEXT NOT NULL,
  PRIMARY KEY (kind, key)
);

-- A unit: Paradise, the Trinity within it, a superuniverse, Salvington.  A
-- box on the canvas, inside its parent's.  `linkable`: a line may end at it,
-- as the lines from the Trinity do.  `ord` is the order of the tree, a parent
-- before what it holds.
CREATE TABLE cosmo_unit (
  id       TEXT PRIMARY KEY,
  parent   TEXT REFERENCES cosmo_unit(id),
  ord      INTEGER NOT NULL UNIQUE,
  depth    INTEGER NOT NULL,
  color    TEXT NOT NULL,
  linkable INTEGER NOT NULL,
  x INTEGER NOT NULL, y INTEGER NOT NULL, w INTEGER NOT NULL, h INTEGER NOT NULL
);

-- How wide his page drew a unit's title, in each language: what the lines
-- were kept clear of, and so the most the site's own title may take.
CREATE TABLE cosmo_title (
  unit TEXT NOT NULL REFERENCES cosmo_unit(id),
  lang TEXT NOT NULL,
  w    INTEGER NOT NULL,
  PRIMARY KEY (unit, lang)
);

-- An order of personalities.  `origin`: which Deities it comes of, a letter
-- to each (F, S, D), T the Trinity as one, A an Absolute, E evolutionary;
-- empty where it is not revealed.  `glyph` is the sign its card carries and
-- `glyph_group` the group whose colour draws it: the first of its groups in
-- the order his engine weighs them (build/cosmo.py GLYPHS).
CREATE TABLE cosmo_person (
  id          TEXT PRIMARY KEY,
  ord         INTEGER NOT NULL UNIQUE,
  class       TEXT NOT NULL,
  origin      TEXT NOT NULL,
  pair        TEXT REFERENCES cosmo_person(id),
  glyph       TEXT NOT NULL,
  glyph_group TEXT NOT NULL
);

-- A personality's groups and functions, in his order, and what fuses to make
-- it ('fuse': a mortal and an Adjuster).
CREATE TABLE cosmo_tag (
  person TEXT NOT NULL REFERENCES cosmo_person(id),
  kind   TEXT NOT NULL CHECK (kind IN ('group', 'func', 'fuse')),
  key    TEXT NOT NULL,
  ord    INTEGER NOT NULL,
  PRIMARY KEY (person, kind, key)
);

-- A card: a personality where it has its origin (its id), or again where it
-- serves ('~' and its id, `ghost`).  In `unit`, in its `row` there and its
-- place in the row; (x, y) its top left corner on the canvas.
CREATE TABLE cosmo_place (
  id     TEXT PRIMARY KEY,
  person TEXT NOT NULL REFERENCES cosmo_person(id),
  ghost  INTEGER NOT NULL,
  unit   TEXT NOT NULL REFERENCES cosmo_unit(id),
  row    INTEGER NOT NULL,
  col    INTEGER NOT NULL,
  x INTEGER NOT NULL, y INTEGER NOT NULL
);

-- A line, from `a` to `b`: each a card's id or a linkable unit's.  `far`: its
-- ends are more than the canvas's `long` apart, and it is shown only with one
-- of them chosen, as his page shows it.
CREATE TABLE cosmo_link (
  id   INTEGER PRIMARY KEY,
  a    TEXT NOT NULL,
  b    TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('origin', 'service', 'ascent')),
  far  INTEGER NOT NULL
);

-- Where a line runs, in each language, the units' titles being in its way:
-- `points`, the corners it turns at, as his page found them ("x,y x,y ..."),
-- and `d`, the same as a path with its corners rounded.
CREATE TABLE cosmo_route (
  link_id INTEGER NOT NULL REFERENCES cosmo_link(id),
  lang    TEXT NOT NULL,
  points  TEXT NOT NULL,
  d       TEXT NOT NULL,
  PRIMARY KEY (link_id, lang)
);

-- Every word of his: a key's, a unit's or a personality's name, another name
-- it goes by (aka, several), what it is (desc), how it serves where it is
-- drawn again (serves), and its name there (there: a Material Son is Adam).
CREATE TABLE cosmo_text (
  kind  TEXT NOT NULL CHECK (kind IN ('class', 'group', 'func', 'unit', 'person')),
  key   TEXT NOT NULL,
  field TEXT NOT NULL CHECK (field IN ('name', 'aka', 'desc', 'serves', 'there')),
  lang  TEXT NOT NULL,
  ord   INTEGER NOT NULL DEFAULT 0,
  text  TEXT NOT NULL,
  PRIMARY KEY (kind, key, field, lang, ord)
);

-- Where the book speaks of it: a paper, or a section, each of which is.
CREATE TABLE cosmo_ref (
  kind      TEXT NOT NULL CHECK (kind IN ('unit', 'person')),
  key       TEXT NOT NULL,
  ord       INTEGER NOT NULL,
  paper_n   INTEGER NOT NULL,
  section_n INTEGER,
  PRIMARY KEY (kind, key, ord)
);

-- Its headwords in the index: by its name or another name of its, where that
-- is a headword as written, or by data/cosmology/headwords.tsv.
CREATE TABLE cosmo_head (
  kind TEXT NOT NULL CHECK (kind IN ('unit', 'person')),
  key  TEXT NOT NULL,
  ord  INTEGER NOT NULL,
  slug TEXT NOT NULL,
  via  TEXT NOT NULL CHECK (via IN ('name', 'aka', 'table')),
  PRIMARY KEY (kind, key, slug)
);
CREATE INDEX cosmo_head_slug ON cosmo_head(slug);
