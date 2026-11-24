-- var/embed.db (tools/embed/build.py, `make embed`): the units Search by
-- meaning searches, each with its vector.  A database of its own beside ub.db
-- and bible.db, made from them and from the model (sources.toml [embed]), and
-- shipped with them: it is 4 kB a unit, and changes only where a unit's text
-- does.  Not build/schema/, which db.create runs for ub.db.
--
-- Nothing in it moves with a build that changes nothing: no date, no path, no
-- word of where or how a vector was made (var/embed/cache.db keeps that).

-- model, rev, dim and `sha256 <file>`: the model, as sources.toml names it.
-- recipe: build/embed.py RECIPE.  units: the digest of the list of units
-- (build/embed.py digest()), by which a build knows the file is today's.
-- n and `n <kind>`: how many.  probe, probe_v: a sentence and its vector,
-- which a host embeds again as it loads the model (ubsite/meaning.py): one
-- whose model or runtime is not the maker's finds it out there.
CREATE TABLE embed_meta (
  key   TEXT PRIMARY KEY,
  value NOT NULL
) WITHOUT ROWID;

-- A unit: what it is, its name, and where it leads (build/embed.py, whose
-- order this is: the matrix a host searches is these rows, one after another).
--   para   label 101:4.2, the paragraph
--   entry  label the entry's path as the index shows it, target its id in the
--          ub.db this was made beside; a host holds the id to the path
--   note   label the study note's key, target its paragraph
--   kjv    label Gen 1:1-5
-- `hash` is the SHA-256 of the text the vector was made of, and `v` the
-- vector: 1,024 float32, little-endian, of unit length.
CREATE TABLE unit (
  id     INTEGER PRIMARY KEY,
  kind   TEXT NOT NULL CHECK (kind IN ('para', 'entry', 'note', 'kjv')),
  label  TEXT NOT NULL,
  target TEXT NOT NULL,
  hash   BLOB NOT NULL CHECK (length(hash) = 32),
  v      BLOB NOT NULL CHECK (length(v) = 4096)
);
