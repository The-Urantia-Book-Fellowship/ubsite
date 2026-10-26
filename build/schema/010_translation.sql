-- The translations shown beside the text (build/translation.py), each joined to
-- OUR numbering: a translated paragraph is stored under our paragraph, never as
-- a paragraph of its own, which every count and /healthz take to be the English.

-- A translation, as read: its key is sources.toml's and data/translations.toml's,
-- and what a reader's Settings store.
CREATE TABLE translation (
    key          TEXT PRIMARY KEY,
    lang         TEXT NOT NULL,         -- BCP 47: 'ru'
    title        TEXT NOT NULL,         -- the work's own title
    n_paragraphs INTEGER NOT NULL,      -- of ours it translates
    n_notes      INTEGER NOT NULL,      -- the translator's
    commit_id    TEXT NOT NULL,         -- of its repository, as read
    ord          INTEGER NOT NULL,      -- in data/translations.toml: Settings lists them so
    -- What a reader is told of it (data/translations.toml): who made it, in
    -- each language of the interface, and its short name, in none: "Aivazian".
    by_en        TEXT NOT NULL,
    by_ru        TEXT NOT NULL,
    label        TEXT NOT NULL
);

-- A rowid table, not WITHOUT ROWID: its rows are long, and stored by key they
-- took twice the room their text does.
CREATE TABLE tr_paragraph (
    translation  TEXT NOT NULL REFERENCES translation(key),
    paragraph_id INTEGER NOT NULL REFERENCES paragraph(id),
    src_ref      TEXT,                  -- its own address, where it numbers otherwise; NULL: ours
    text         TEXT NOT NULL,
    html_hy      TEXT NOT NULL,         -- with a U+00AD wherever its TeX lets a word break;
                                        -- without them, it is its HTML
    UNIQUE (translation, paragraph_id)
);
CREATE INDEX tr_paragraph_para ON tr_paragraph(paragraph_id);

-- A paper's title and author, a section's title, as the translation writes them,
-- for each paper it translates in part or whole.
CREATE TABLE tr_heading (
    translation  TEXT NOT NULL REFERENCES translation(key),
    paper_n      INTEGER NOT NULL,
    section_n    INTEGER,               -- NULL: the paper's
    kind         TEXT NOT NULL CHECK (kind IN ('title', 'author', 'section')),
    text         TEXT NOT NULL,
    html         TEXT NOT NULL
);

-- A translator's note, as written, at its place in the paragraph's text:
-- rendered when the reader shows it.
CREATE TABLE tr_note (
    translation  TEXT NOT NULL,
    paragraph_id INTEGER NOT NULL,
    num          INTEGER NOT NULL,      -- 1.. through its paper, in reading order
    at           INTEGER NOT NULL,      -- its offset in tr_paragraph.text
    tex          TEXT NOT NULL,
    FOREIGN KEY (translation, paragraph_id) REFERENCES tr_paragraph(translation, paragraph_id)
);
CREATE INDEX tr_note_para ON tr_note(translation, paragraph_id);
