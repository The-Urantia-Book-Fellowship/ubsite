-- External-content tables: no duplicate storage.  The database is immutable
-- after the build, so no triggers are needed -- write that down, because the
-- usual FTS5 advice assumes a mutable table.  Serve with PRAGMA query_only.
CREATE VIRTUAL TABLE paragraph_fts USING fts5(
  text, content='paragraph', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');

-- Indexes text_expanded, NOT text: 3,025 entries abbreviate their own headword
-- ("c. belonged to mother"), and are unfindable without the expansion.
CREATE VIRTUAL TABLE index_entry_fts USING fts5(
  text_expanded, path, content='index_entry', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');

-- What a 1955 card says, one row per note (rowid = footnote.id): the reading
-- as the press gives it, and the SRT Committee's reasons the card shows -- its
-- own item's, and those of the item it refers to (see_id).  It stores its own
-- copy (~60 KB), because the reasons come from a join.  Never the committee's
-- quotation of 1955 (then_text), and none of its entries the site shows no
-- note for.  Every kind of footnote is here; search filters on kind.
CREATE VIRTUAL TABLE footnote_fts USING fts5(
  reading, reasons,
  tokenize='unicode61 remove_diacritics 2');
