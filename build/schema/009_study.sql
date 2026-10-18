-- The British Study Edition's notes, one reviewed paper at a time
-- (build/study.py, data/study/).  Each note is a footnote of kind 'study',
-- whose marker in the text carries its number; these tables say what the
-- footnote row cannot: the number, where the note came from, what it cites.

-- A paper whose notes are on the site, and what they were reviewed against.
CREATE TABLE study_paper (
    paper_n      INTEGER PRIMARY KEY,
    file_sha256  TEXT NOT NULL,        -- data/study/NNN.toml, as built
    study_commit TEXT NOT NULL,        -- the edition's commit its originals were read at
    block_url    TEXT,                 -- Block's chart, as reviewed; NULL: the paper has none
    block_month  TEXT,                 -- 'YYYY-MM', from the chart's address
    n_notes      INTEGER NOT NULL,
    n_dropped    INTEGER NOT NULL      -- the edition's notes not carried, each with its reason
);

-- A source the paper's notes cite: a \bibitem of the edition, as reviewed.
CREATE TABLE study_source (
    id      INTEGER PRIMARY KEY,
    paper_n INTEGER NOT NULL REFERENCES study_paper(paper_n),
    key     TEXT NOT NULL,             -- as \cite names it
    origin  TEXT NOT NULL,             -- the \bibitem it was made from (readers/study.py digest)
    text    TEXT NOT NULL,
    html    TEXT NOT NULL,
    UNIQUE (paper_n, key)
);

CREATE TABLE study_note (
    footnote_id  INTEGER PRIMARY KEY REFERENCES footnote(id),
    paper_n      INTEGER NOT NULL REFERENCES study_paper(paper_n),
    num          INTEGER NOT NULL,     -- the marker's number: 1.. in the paper, in reading order
    key          TEXT NOT NULL UNIQUE, -- st<paper>_<section>_<para>_<k>: #fn<key>, #fnref<key>
    origin       TEXT NOT NULL,        -- the \fnst it was made from
    after        TEXT NOT NULL,        -- the words of the press text the marker follows
    edited       INTEGER NOT NULL,     -- 1 where the note differs from the edition's
    human_source INTEGER NOT NULL,     -- 1 where it cites a source or rests on Block's chart
    credit       TEXT,                 -- 'block', or a contributor's name
    UNIQUE (paper_n, num)
);

CREATE TABLE study_cite (
    footnote_id INTEGER NOT NULL REFERENCES study_note(footnote_id),
    source_id   INTEGER NOT NULL REFERENCES study_source(id),
    ord         INTEGER NOT NULL,      -- [1], [2] ... in the note
    PRIMARY KEY (footnote_id, ord)
);
