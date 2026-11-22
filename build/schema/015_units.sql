-- Unit conversions (build/units.py, from data/units.toml): the units of time,
-- distance, speed, weight and temperature the Urantia Papers define or use,
-- beside the familiar ones, which /units converts each into all the others
-- (DECISIONS.md, Unit conversions).  A unit the book defines carries its
-- paragraph and its words there, in English and in the Foundation's Russian.

CREATE TABLE unit_group (
  key        TEXT PRIMARY KEY,               -- 'time', the table's id on the page
  n          INTEGER NOT NULL UNIQUE,        -- its place on the page, from 1
  name_en    TEXT NOT NULL,
  name_ru    TEXT NOT NULL,
  index_slug TEXT,                           -- the index's headword that gathers its units
  start_unit TEXT NOT NULL,                  -- the row the table opens at, and its value
  start_value REAL NOT NULL
);

CREATE TABLE unit_band (
  group_key  TEXT NOT NULL REFERENCES unit_group(key),
  key        TEXT NOT NULL,
  n          INTEGER NOT NULL,               -- its place in its table, from 1
  name_en    TEXT NOT NULL,
  name_ru    TEXT NOT NULL,
  PRIMARY KEY (group_key, key)
);

CREATE TABLE unit (
  key          TEXT PRIMARY KEY,             -- 'jday', what the page's address names
  group_key    TEXT NOT NULL REFERENCES unit_group(key),
  band_key     TEXT,                         -- NULL in a table with no bands
  n            INTEGER NOT NULL,             -- its row in its table, from 1
  name_en      TEXT NOT NULL,
  name_ru      TEXT NOT NULL,
  -- In the table's base unit: base = (value + offset) * scale.
  scale        REAL NOT NULL,
  scale_exact  TEXT NOT NULL,                -- the same as a fraction, 'p/q', where it is one; else ''
  offset       REAL NOT NULL DEFAULT 0,
  about        INTEGER NOT NULL,             -- 1: the book's figure is about, almost (it, or a unit it is made of)
  ref          TEXT,                         -- the paragraph that defines it, NULL for a familiar unit
  paragraph_id INTEGER REFERENCES paragraph(id),
  words        TEXT,                         -- its words there, exactly
  words_ru     TEXT,                         -- uf-ru's, NULL where uf-ru is not built
  def_en       TEXT,                         -- a familiar unit's standard
  def_ru       TEXT,
  UNIQUE (group_key, n)
);

CREATE TABLE unit_example (
  n            INTEGER PRIMARY KEY,          -- its place in the file, from 1
  group_key    TEXT NOT NULL REFERENCES unit_group(key),
  ref          TEXT NOT NULL,
  paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
  words        TEXT NOT NULL,
  words_ru     TEXT,
  unit_key     TEXT NOT NULL REFERENCES unit(key),
  value        REAL NOT NULL,                -- what a tap puts in the unit's row
  says_unit    TEXT REFERENCES unit(key),    -- where the book gives the figure in another unit
  says_value   REAL,
  within       REAL                          -- the fraction the table must agree to
);
