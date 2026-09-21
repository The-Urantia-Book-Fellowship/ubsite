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
