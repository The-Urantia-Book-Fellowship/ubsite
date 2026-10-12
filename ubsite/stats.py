"""The private /stats page: what var/visits.db says, for the site's owner.

ubsite/visits.py records facts.  This derives the rest at report time: whether
a user agent is a person's browser, a crawler or a link preview; what kind of
page a path is; which referrers are other sites.  So a better classifier
applies to the whole history, not only from the day it was written.

A *visit* is one browser on one UTC day: the visitor number is salted afresh
each day, so the same reader on two days counts twice, by design.  A view
counts as a person's when its visitor-day also fetched /static/ub.css (a
browser that renders the page) and its user agent is no known bot.

The page is behind HTTP Basic auth, against an scrypt hash in var/stats.passwd
(`python -m ubsite.stats passwd`).  Without that file /stats does not exist.
"""

from __future__ import annotations

import base64
import binascii
import datetime
import functools
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
from collections import Counter, defaultdict
from urllib.parse import parse_qs, urlsplit

from ubsite.visits import ROOT, VISITS

PASSWD = ROOT / "var" / "stats.passwd"
PERIODS = {"1": 1, "7": 7, "30": 30, "90": 90, "all": 0}


# ---- the gate --------------------------------------------------------------------
def make_hash(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${h.hex()}"


def check(password: str, line: str) -> bool:
    try:
        _, n, r, p, salt, want = line.strip().split("$")
        h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                           n=int(n), r=int(r), p=int(p), dklen=len(want) // 2)
    except ValueError:
        return False
    return hmac.compare_digest(h.hex(), want)


def allowed(authorization: str | None) -> bool | None:
    """True for the right password, False for none or a wrong one, and None
    when no password has been set, which is when /stats does not exist."""
    try:
        line = PASSWD.read_text()
    except OSError:
        return None
    if not authorization or not authorization.startswith("Basic "):
        return False
    try:
        user_pass = base64.b64decode(authorization[6:], validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return False
    return check(user_pass.partition(":")[2], line)


# ---- user agents -------------------------------------------------------------------
# Link previews: someone pasted a link into a chat or a post, and the app
# fetched it to draw a card.  Each is a share.
PREVIEWS = [("facebookexternalhit", "Facebook"), ("Facebot", "Facebook"),
            ("WhatsApp", "WhatsApp"), ("TelegramBot", "Telegram"),
            ("Twitterbot", "X"), ("Slackbot", "Slack"), ("Discordbot", "Discord"),
            ("LinkedInBot", "LinkedIn"), ("SkypeUriPreview", "Skype"),
            ("redditbot", "Reddit"), ("Pinterest", "Pinterest"), ("Viber", "Viber"),
            ("vkShare", "VK"), ("Iframely", "Iframely"), ("Mastodon", "Mastodon"),
            ("Bluesky", "Bluesky"), ("Embedly", "Embedly")]
RE_BOT = re.compile(r"([\w.-]*(?:bot|crawler|spider|slurp|scanner|fetcher)[\w.-]*)", re.I)
TOOLS = re.compile(r"HeadlessChrome|PhantomJS|Lighthouse|zgrab|masscan|Nmap|Nuclei|"
                   r"CensysInspect|Expanse|l9explore|Palo Alto|python|curl|Wget|Go-http",
                   re.I)
BROWSERS = [("Edg", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser/", "Samsung Internet"),
            ("YaBrowser/", "Yandex"), ("Vivaldi/", "Vivaldi"), ("Firefox/", "Firefox"),
            ("FxiOS/", "Firefox"), ("CriOS/", "Chrome"), ("Chrome/", "Chrome"),
            ("Safari/", "Safari")]
SYSTEMS = [("Windows", "Windows"), ("iPhone", "iOS"), ("iPad", "iPadOS"),
           ("Android", "Android"), ("CrOS", "ChromeOS"), ("Macintosh", "macOS"),
           ("Linux", "Linux")]


@functools.lru_cache(maxsize=65536)
def classify(ua: str) -> dict:
    """{kind: 'person' | 'bot' | 'preview', name, browser, os, device}."""
    for token, name in PREVIEWS:
        if token in ua:
            return {"kind": "preview", "name": name}
    m = TOOLS.search(ua)
    if m:
        return {"kind": "bot", "name": m.group(0)}
    m = RE_BOT.search(ua)
    if m:
        return {"kind": "bot", "name": m.group(1)}
    if not ua.startswith("Mozilla/"):
        # A library or a script: name it by its first product token.
        return {"kind": "bot", "name": ua.split("/")[0].split()[0][:40] if ua.strip() else "(none)"}
    browser = next((n for t, n in BROWSERS if t in ua), "Other")
    system = next((n for t, n in SYSTEMS if t in ua), "Other")
    if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
        device = "Tablet"
    elif "Mobi" in ua or "iPhone" in ua:
        device = "Phone"
    else:
        device = "Desktop"
    return {"kind": "person", "browser": browser, "os": system, "device": device}


# ---- pages -------------------------------------------------------------------------
RE_SECTION = re.compile(r"^/(\d+):(\d+)(?:\.\d+(?:-\d+)?)?$")


def page_kind(path: str) -> tuple[str, str]:
    """(kind, key): ('section', '102:3'), ('concept', 'adoption'), ..."""
    m = RE_SECTION.match(path)
    if m:
        return "section", f"{int(m[1])}:{int(m[2])}"
    if path == "/":
        return "home", ""
    if path == "/read":
        return "contents", ""
    if path == "/search":
        return "search", ""
    if path.startswith("/i/"):
        return "concept", path[3:]
    if path == "/index" or path.startswith("/index/"):
        return "index", path[7:]
    if path == "/appendix" or path.startswith("/appendix/"):
        return "appendix", path[10:]
    if path == "/lists" or path.startswith("/lists/"):
        return "lists", path[7:]
    return "other", path


KIND_LABEL = {"section": "Sections of the text", "concept": "Concept pages",
              "index": "The index, by letter", "appendix": "Appendices",
              "search": "Search", "home": "Home page", "contents": "Contents", "lists": "Lists",
              "other": "Other"}


# ---- the report --------------------------------------------------------------------
def client_name(ua: str, kind: dict) -> str:
    """Who is calling the API: the User-Agent's first product, "ExampleSite/1.0"."""
    if kind.get("kind") == "person":
        return f"a browser ({kind['browser']}, {kind['os']})"
    return (ua.split()[0] if ua.strip() else "(no User-Agent)")[:60]


def api_report(con: sqlite3.Connection, ub: sqlite3.Connection, start: str,
               agents: dict) -> dict:
    """The text API's callers: other sites keeping their copy of the text in step.

    Each is told apart by its User-Agent, which /api asks them to make their
    site's name.  `held` is the version a caller has after its latest call to
    /text that succeeded: 200 sent it, 304 confirmed it.
    """
    try:
        current = ub.execute("SELECT MAX(n) FROM text_version").fetchone()[0]
    except sqlite3.Error:
        current = None
    try:
        rows = con.execute(
            "SELECT c.*, a.ua, p.city, p.country, p.country_name FROM api_call c"
            " LEFT JOIN agent a ON a.id = c.agent_id LEFT JOIN place p ON p.id = c.place_id"
            " WHERE c.day >= ? ORDER BY c.id", (start,)).fetchall()
    except sqlite3.OperationalError:
        rows = []                                  # no API call yet since api_call was added
    clients: dict[str, dict] = {}
    days = Counter()
    for row in rows:
        name = client_name(row["ua"] or "", agents.get(row["agent_id"], {}))
        c = clients.setdefault(name, {"name": name, "ua": row["ua"], "calls": 0, "whole": 0,
                                      "current": 0, "errors": 0, "held": None, "last": 0,
                                      "places": Counter()})
        c["calls"] += 1
        text = row["path"] == "/api/v1/text"
        c["whole"] += text and row["status"] == 200 and row["whole"] == 1
        c["current"] += text and (row["status"] == 304 or row["since"] == row["version"])
        c["errors"] += row["status"] >= 400
        if text and row["status"] in (200, 304):
            c["held"] = row["version"]
        c["last"] = row["ts"]
        place = ", ".join(x for x in (row["city"], row["country_name"]) if x)
        if place:
            c["places"][(flag(row["country"]), place)] += 1
        days[row["day"]] += 1
    out = sorted(clients.values(), key=lambda c: -c["last"])
    for c in out:
        c["last"] = when(c["last"])
        c["places"] = [f"{f} {p}" for (f, p), _ in c["places"].most_common(3)]
    return {"current": current, "clients": out, "calls": len(rows),
            "days": sorted(days.items(), reverse=True)[:14]}


def connect() -> sqlite3.Connection | None:
    if not VISITS.exists():
        return None
    con = sqlite3.connect(VISITS, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


def report(ub: sqlite3.Connection, days: int, recent: int = 50) -> dict:
    """Everything /stats shows, over the last `days` UTC days (0: all of it)."""
    con = connect()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    if con is None:
        return {"empty": True, "days": days}
    if days:
        start = (today - datetime.timedelta(days=days - 1)).isoformat()
    else:
        start = con.execute("SELECT MIN(day) FROM view").fetchone()[0] or today.isoformat()

    agents = {r["id"]: classify(r["ua"]) for r in con.execute("SELECT id, ua FROM agent")}
    con.create_function("kind", 1, lambda a: agents.get(a, {}).get("kind"), deterministic=True)
    # A person's view: not a bot, from a visitor-day that loaded the stylesheet.
    hv = ("WITH hv AS (SELECT v.* FROM view v WHERE v.day >= :start"
          " AND kind(v.agent_id) = 'person'"
          " AND EXISTS (SELECT 1 FROM browser b WHERE b.day = v.day AND b.visitor = v.visitor)) ")
    P = {"start": start}
    VIS = "COUNT(DISTINCT hv.day || ':' || hv.visitor)"

    def q(sql, **kw):
        return con.execute(hv + sql, {**P, **kw}).fetchall()

    r: dict = {"days": days, "start": start, "end": today.isoformat()}

    # -- tiles, and the days
    r["visits"], r["views"] = q(f"SELECT {VIS}, SUM(status = 200) FROM hv")[0]
    r["views"] = r["views"] or 0
    span = (today - datetime.date.fromisoformat(start)).days + 1
    r["per_day"] = r["visits"] / span if span else 0
    per = {row[0]: (row[1], row[2]) for row in q(
        "SELECT day, COUNT(DISTINCT visitor), SUM(status = 200) FROM hv GROUP BY day")}
    r["daily"] = []
    d = datetime.date.fromisoformat(start)
    while d <= today:
        v, n = per.get(d.isoformat(), (0, 0))
        r["daily"].append({"day": d.isoformat(), "visits": v, "views": n or 0})
        d += datetime.timedelta(days=1)
    r["all_rows"] = con.execute("SELECT COUNT(*) FROM view WHERE day >= ?", (start,)).fetchone()[0]

    # -- where from: places
    countries = q(f"SELECT p.country, p.country_name, {VIS} n FROM hv JOIN place p ON p.id = hv.place_id"
                  " GROUP BY p.country ORDER BY n DESC, p.country_name")
    cities = defaultdict(list)
    for row in q(f"SELECT p.country, p.city, p.region, {VIS} n FROM hv JOIN place p ON p.id = hv.place_id"
                 " GROUP BY p.id ORDER BY n DESC, p.city"):
        cities[row["country"]].append({"city": row["city"] or "(unknown)", "region": row["region"],
                                       "n": row["n"]})
    r["countries"] = [{"iso": c["country"], "name": c["country_name"], "n": c["n"],
                       "flag": flag(c["country"]), "cities": cities[c["country"]][:8]}
                      for c in countries]
    r["n_countries"] = len(countries)
    r["unplaced"] = q(f"SELECT {VIS} FROM hv WHERE place_id IS NULL")[0][0]

    # -- where from: how each visit arrived (its first page's referrer), and every link in
    arrived = Counter()
    for (ref,) in q("SELECT referrer FROM hv WHERE id IN (SELECT MIN(id) FROM hv GROUP BY day, visitor)"):
        arrived[host_of(ref) if ref and not ref.startswith("/") else "(direct)"] += 1
    r["arrived"] = arrived.most_common(25)
    links = defaultdict(Counter)
    for row in q(f"SELECT referrer, {VIS} n FROM hv WHERE referrer IS NOT NULL"
                 " AND referrer NOT LIKE '/%' GROUP BY referrer"):
        links[host_of(row["referrer"])][row["referrer"]] += row["n"]
    r["links"] = sorted(({"host": h, "n": sum(c.values()), "urls": c.most_common(6)}
                         for h, c in links.items()), key=lambda x: -x["n"])[:25]

    # -- what is read
    kinds, sections, concepts, other = Counter(), Counter(), Counter(), Counter()
    sec_vis, con_vis = Counter(), Counter()
    for row in q(f"SELECT path, COUNT(*) views, {VIS} n FROM hv WHERE status = 200 GROUP BY path"):
        kind, key = page_kind(row["path"])
        kinds[kind] += row["views"]
        if kind == "section":
            sections[key] += row["views"]
            sec_vis[key] += row["n"]
        elif kind == "concept":
            concepts[key] += row["views"]
            con_vis[key] += row["n"]
        elif kind in ("index", "appendix", "other"):
            other[row["path"]] += row["views"]
    r["kinds"] = [(KIND_LABEL[k], n) for k, n in kinds.most_common()]
    titles = section_titles(ub)
    r["sections"] = [{"ref": k, "title": titles.get(k, ""), "views": n, "n": sec_vis[k]}
                     for k, n in sections.most_common(30)]
    papers = Counter()
    for k, n in sections.items():
        papers[int(k.split(":")[0])] += n
    ptitles = dict(ub.execute("SELECT n, title FROM paper").fetchall())
    r["papers"] = [{"n": p, "title": ptitles.get(p, ""), "views": n} for p, n in papers.most_common(20)]
    heads = headwords(ub, list(concepts))
    r["concepts"] = [{"slug": k, "head": heads.get(k, k), "views": n, "n": con_vis[k]}
                     for k, n in concepts.most_common(30)]
    r["other_pages"] = other.most_common(20)

    # -- what is searched.  One count per visit and query, however many pages of it.
    searched, found, zero, jumps = Counter(), {}, Counter(), Counter()
    seen = set()
    for row in q("SELECT day, visitor, query, hits, status FROM hv WHERE path = '/search'"
                 " AND query IS NOT NULL"):
        text = " ".join(parse_qs(row["query"]).get("q", [""])[0].split())
        if not text:
            continue
        key = (row["day"], row["visitor"], text.lower())
        if key in seen:
            continue
        seen.add(key)
        if row["status"] == 303:
            jumps[text] += 1
        elif row["status"] == 200:
            searched[text.lower()] += 1
            found[text.lower()] = max(found.get(text.lower(), 0), row["hits"] or 0)
            if row["hits"] == 0:
                zero[text.lower()] += 1
    r["searches"] = sum(searched.values()) + sum(jumps.values())
    r["queries"] = [(t, n, found[t]) for t, n in searched.most_common(40)]
    r["zero"] = zero.most_common(100)
    r["jumps"] = jumps.most_common(15)
    r["n_jumps"] = sum(jumps.values())

    # -- listening
    voices = {row[0]: row[1] for row in ub.execute("SELECT key, label FROM audio_source")}
    voices["browser"] = "Your browser's voice"
    files = audio_sections(ub)
    by_voice, heard, listeners = Counter(), Counter(), defaultdict(set)
    for row in con.execute(
            "SELECT l.day, l.visitor, l.voice, l.item FROM listen l WHERE l.day >= ?"
            " AND EXISTS (SELECT 1 FROM browser b WHERE b.day = l.day AND b.visitor = l.visitor)",
            (start,)):
        ref = row["item"] if row["voice"] == "browser" else files.get(row["item"], row["item"])
        by_voice[row["voice"]] += 1
        heard[ref] += 1
        listeners[row["voice"]].add((row["day"], row["visitor"]))
    r["voices"] = [{"label": voices.get(v, v), "sections": n, "listeners": len(listeners[v])}
                   for v, n in by_voice.most_common()]
    r["heard"] = [{"ref": k, "title": titles.get(k, ""), "n": n} for k, n in heard.most_common(15)]
    r["listened"] = sum(by_voice.values())

    # -- who: devices, browsers, systems, languages
    dev, brw, sysm = Counter(), Counter(), Counter()
    for row in q(f"SELECT agent_id, {VIS} n FROM hv GROUP BY agent_id"):
        a = agents.get(row["agent_id"], {})
        dev[a.get("device", "?")] += row["n"]
        brw[a.get("browser", "?")] += row["n"]
        sysm[a.get("os", "?")] += row["n"]
    r["devices"], r["browsers"], r["systems"] = dev.most_common(), brw.most_common(10), sysm.most_common(10)
    r["langs"] = [(row[0] or "(none)", row[1]) for row in
                  q(f"SELECT lang, {VIS} n FROM hv GROUP BY lang ORDER BY n DESC LIMIT 15")]

    # -- the machines: crawlers, link previews (shares)
    bots, previews, shared = Counter(), Counter(), Counter()
    last = {}
    for row in con.execute("SELECT agent_id, COUNT(*) n, MAX(ts) t FROM view WHERE day >= ?"
                           " AND kind(agent_id) = 'bot' GROUP BY agent_id", (start,)):
        name = agents[row["agent_id"]]["name"]
        bots[name] += row["n"]
        last[name] = max(last.get(name, 0), row["t"])
    for row in con.execute("SELECT agent_id, path, COUNT(*) n FROM view WHERE day >= ?"
                           " AND kind(agent_id) = 'preview' GROUP BY agent_id, path", (start,)):
        name = agents[row["agent_id"]]["name"]
        previews[name] += row["n"]
        shared[(name, row["path"])] += row["n"]
    r["bots"] = [(name, n, when(last[name])) for name, n in bots.most_common(25)]
    r["bot_views"] = sum(bots.values())
    r["previews"] = previews.most_common()
    r["shared"] = [(app, path, n) for (app, path), n in shared.most_common(20)]

    r["api"] = api_report(con, ub, start, agents)

    # -- broken links: pages a person asked for that do not exist
    r["missing"] = [dict(row) for row in q(
        "SELECT path, referrer, COUNT(*) n FROM hv WHERE status = 404"
        " GROUP BY path, referrer ORDER BY n DESC LIMIT 25")]

    # -- the latest
    r["recent"] = [{"when": when(row["ts"]), "path": row["path"],
                    "q": " ".join(parse_qs(row["query"] or "").get("q", [""])[0].split()),
                    "place": ", ".join(x for x in (row["city"], row["country_name"]) if x),
                    "flag": flag(row["country"]), "ref": row["referrer"], "via": row["via"]}
                   for row in q("SELECT hv.ts, hv.path, hv.query, hv.referrer, hv.via, p.city,"
                                " p.country, p.country_name FROM hv LEFT JOIN place p"
                                " ON p.id = hv.place_id WHERE hv.status IN (200, 303)"
                                " ORDER BY hv.id DESC LIMIT :n", n=recent)]
    r["geoip"] = geoip_date()
    r["chart"] = chart(r["daily"])
    return r


def chart(daily: list[dict]) -> dict:
    """Visits per day as columns, in percentages of the axis, for stats.html.

    Drawn in HTML rather than SVG so that its labels stay legible at a phone's
    width.  One series, so no legend: the heading names it.  Clean ticks of 1, 2
    or 5 times a power of ten.
    """
    top = max((d["visits"] for d in daily), default=0)
    step = 1
    while step * 5 < top:                          # 1, 2, 5, 10, 20, 50 ...
        step = step * 5 // 2 if str(step)[0] == "2" else step * 2
    ymax = max(step * -(-top // step), 1)
    return {"bars": [{**d, "pct": round(100 * d["visits"] / ymax, 2)} for d in daily],
            "ticks": [{"v": v, "pct": round(100 * v / ymax, 2)} for v in range(0, ymax + 1, step)],
            "labels": [daily[0]["day"], daily[-1]["day"]] if len(daily) > 1
                      else [d["day"] for d in daily]}


def flag(iso: str | None) -> str:
    """The country's flag, from its two letters: regional indicator symbols."""
    if not iso or len(iso) != 2 or not iso.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso.upper())


def host_of(url: str) -> str:
    host = urlsplit(url).netloc or url
    return host[4:] if host.startswith("www.") else host


def when(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")


def section_titles(ub: sqlite3.Connection) -> dict:
    return {f"{p}:{n}": t for p, n, t in ub.execute("SELECT paper_n, n, title FROM section")}


def headwords(ub: sqlite3.Connection, slugs: list[str]) -> dict:
    if not slugs:
        return {}
    marks = ",".join("?" * len(slugs))
    return dict(ub.execute(f"SELECT slug, RTRIM(headword, '.') FROM index_entry"
                           f" WHERE slug IN ({marks})", slugs).fetchall())


def audio_sections(ub: sqlite3.Connection) -> dict:
    """A recording's file name -> the section it reads, as 'paper:section'."""
    try:
        return {name: ref for name, ref in ub.execute(
            "SELECT DISTINCT f.name, s.paper_n || ':' || s.n FROM audio_file f"
            " JOIN audio_segment g ON g.file_id = f.id JOIN section s ON s.id = g.section_id")}
    except sqlite3.Error:
        return {}


def geoip_date() -> str | None:
    from ubsite.visits import GEOIP
    try:
        import maxminddb
        with maxminddb.open_database(str(GEOIP)) as reader:
            return datetime.datetime.fromtimestamp(
                reader.metadata().build_epoch, datetime.timezone.utc).strftime("%Y-%m-%d")
    except (OSError, ValueError, ImportError):
        return None


# ---- python -m ubsite.stats passwd -------------------------------------------------
def main(argv: list[str]) -> int:
    if argv != ["passwd"]:
        print("usage: python -m ubsite.stats passwd", file=sys.stderr)
        return 2
    password = secrets.token_urlsafe(18)           # 24 characters
    PASSWD.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(PASSWD, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(make_hash(password) + "\n")
    print(f"/stats password (any user name), shown once:\n\n    {password}\n\n"
          f"Its hash is in {PASSWD}.  Run this again to change it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
