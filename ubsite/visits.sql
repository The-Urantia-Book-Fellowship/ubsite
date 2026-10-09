-- var/visits.db: what the visit counter (ubsite/visits.py) records.
--
-- Facts only.  ubsite/stats.py derives the rest at report time -- what kind of
-- page a path is, which referrers are external, which agents are bots, which
-- visitors are people -- so a better classifier applies to the whole history.
--
-- No IP address is ever written here.  The writer looks it up (place) and
-- hashes it with the day's salt (visitor), then drops it.  The salt is
-- replaced every UTC day and the old one deleted, so a visitor hash can be
-- neither recomputed nor followed from one day to the next.

CREATE TABLE IF NOT EXISTS salt (
    day   TEXT PRIMARY KEY,                -- UTC, YYYY-MM-DD; only today's is kept
    value BLOB NOT NULL
);

-- User agents, once each.
CREATE TABLE IF NOT EXISTS agent (
    id INTEGER PRIMARY KEY,
    ua TEXT NOT NULL UNIQUE
);

-- Where an address was, per DB-IP City Lite.  '' for a part it does not know,
-- not NULL, so that UNIQUE holds; an address it does not know at all
-- (loopback, a private range) gets no place.
CREATE TABLE IF NOT EXISTS place (
    id           INTEGER PRIMARY KEY,
    country      TEXT NOT NULL,            -- ISO 3166 alpha-2
    country_name TEXT NOT NULL,
    region       TEXT NOT NULL,
    city         TEXT NOT NULL,
    UNIQUE (country, region, city)
);

-- One row per page asked for: every GET that is not a static file, a
-- recording, the speech text, /healthz, an icon or /stats.
CREATE TABLE IF NOT EXISTS view (
    id       INTEGER PRIMARY KEY,
    ts       INTEGER NOT NULL,             -- unix seconds
    day      TEXT NOT NULL,                -- the UTC day whose salt made `visitor`
    visitor  INTEGER NOT NULL,             -- sha256(salt, ip, ua), first 8 bytes
    path     TEXT NOT NULL,
    query    TEXT,                         -- the raw query string, /search's q among it
    status   INTEGER NOT NULL,
    referrer TEXT,                         -- without its query string or fragment
    agent_id INTEGER REFERENCES agent(id),
    place_id INTEGER REFERENCES place(id),
    lang     TEXT,                         -- Accept-Language's first tag
    via      TEXT,                         -- NULL a page load; 'swap' or 'next' fetched by listen.js
    hits     INTEGER                       -- /search: what it found
);
CREATE INDEX IF NOT EXISTS view_day ON view(day, visitor);
CREATE INDEX IF NOT EXISTS view_ts ON view(ts);

-- A visitor-day that fetched /static/ub.css: a browser that renders pages.
-- Every page load revalidates it (Cache-Control: no-cache), so a person always
-- appears here and a scanner almost never does.
CREATE TABLE IF NOT EXISTS browser (
    day     TEXT NOT NULL,
    visitor INTEGER NOT NULL,
    PRIMARY KEY (day, visitor)
) WITHOUT ROWID;

-- Something heard, once per visitor-day: a recording's file (`voice` its
-- audio_source key) or a section's text fetched for the browser's own voice
-- (`voice` 'browser', `item` the section's reference).
CREATE TABLE IF NOT EXISTS listen (
    day      TEXT NOT NULL,
    visitor  INTEGER NOT NULL,
    voice    TEXT NOT NULL,
    item     TEXT NOT NULL,
    ts       INTEGER NOT NULL,
    place_id INTEGER REFERENCES place(id),
    PRIMARY KEY (day, visitor, voice, item)
) WITHOUT ROWID;
