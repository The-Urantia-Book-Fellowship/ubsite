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

-- The translations beside the text (010_translation.sql), their paragraphs and
-- their translators' notes, each over a view that reads ё as е: Russian is
-- mostly written without it, ud writes it and urantia-ru never does, and a
-- reader's е should find both, as a reader's ё should.  One letter for one, so
-- every offset in the view is the text's, and a snippet of it is turned back
-- into the translation's own letters by its place (ubsite/app.py _unfold).  A
-- stress mark (U+0301) needs no view: the tokenizer drops it.  Search filters
-- on the translation by joining the table; the views are its content.
CREATE VIEW tr_paragraph_folded AS
  SELECT id, replace(replace(text, 'ё', 'е'), 'Ё', 'Е') AS text FROM tr_paragraph;
CREATE VIRTUAL TABLE tr_paragraph_fts USING fts5(
  text, content='tr_paragraph_folded', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');

CREATE VIEW tr_note_folded AS
  SELECT id, replace(replace(text, 'ё', 'е'), 'Ё', 'Е') AS text FROM tr_note;
CREATE VIRTUAL TABLE tr_note_fts USING fts5(
  text, content='tr_note_folded', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');
