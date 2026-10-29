# The reader and urantiabook.org

How the reader in this repository and the Fellowship's Laravel site at urantiabook.org meet: who owns what, what passes between them, how a release reaches the Fellowship's servers, and what each side builds. It is the brief for the Fellowship's developers, and it is the agreement itself: a change to it is a pull request that both sides review.

It follows the correspondence between the Fellowship and the reader's maintainer that began on 15 October 2026. It was revised on 28 October for what the reader has gained since it was written: three Russian translations beside the text, the interface in Russian, and the server's specification, which the Fellowship asked for. Where something is not built yet, it says so.

---

## 1. The shape

The reader is its own web application, served at **https://read.urantiabook.org**. It is Python 3.12 (FastAPI, Jinja2), renders every page on the server, and reads one SQLite database, `var/ub.db`, built from its sources: the text and the index, whose repositories are in the Fellowship's GitHub organisation; the British Study Edition, whose notes reach the reader one reviewed paper at a time; and three Russian translations. A reader may show each translation beside the text, compare them with it, search them and hear them read aloud. They are the maintainer's own, the late Lila Dogim's with Sergey Prokopov's corrections as the Urantia Book Society of Greater New York publishes it, and the Urantia Foundation's, shown by the Foundation's written permission. Its pages need no frontend framework and no build step: a few small scripts of plain JavaScript, and SQLite's WebAssembly build for searching offline. Its interface is in English and Russian; the book, its index and the appendices stay in English, as printed. `README.md` says how to build and deploy it, `ARCHITECTURE.md` how each part works, and `DECISIONS.md` what was chosen, by whom and when.

urantiabook.org stays as it is. The two meet at five places, each a section below:

| where | section |
|---|---|
| the Fellowship's header and footer on the reader's pages | 5 |
| sign-in: one account across both sites | 6 |
| what members write: notes, bookmarks, highlights | 7 |
| search from urantiabook.org's navigation bar | 8 |
| a release: what the Fellowship's servers run | 3 |

**Why a subdomain, not a path such as urantiabook.org/read/.** The reader assumes it lives at the root of its site: every link it draws, some 48,000 links stored in its database, its offline copy and the worker that serves it, and its installed app. A subdomain needs none of that changed, and it keeps the reader's offline worker and browser storage on an origin of their own, apart from Laravel's. Everything the Fellowship asked of a path works on the subdomain: a shared header and footer (section 5), one sign-in, since Laravel's session cookie is already set for `.urantiabook.org` (section 6), and the app, whose tokens have no address in a browser at all.

---

## 2. Who owns what

| | the reader | Laravel |
|---|---|---|
| pages | everything under read.urantiabook.org | everything under urantiabook.org |
| layout | the reader's pages, one layout for every site that runs it | its own |
| data | `ub.db`, the text, the index, the study notes and the translations as built; members' notes, bookmarks and highlights (section 7) | members' accounts, sign-in and sessions; the app's tokens |
| look | | the Fellowship's header, footer, colours and logo, which the reader wears (section 5) |
| search | the search itself, and its results page | the box in its navigation bar (section 8) |

**What the Fellowship's readers see is the Fellowship's to decide**: through user testing, its advisory committee, or its project manager. If the decision is that something should go from read.urantiabook.org, it goes, after the two sides have talked it through.

**How that is done is the maintainer's to decide**: a switch in the Fellowship site's profile (section 4), a reader's setting that is off by default on the Fellowship's site, or a change for every site that runs the reader. A decision about the Fellowship's site therefore never forces a change on work in progress: either it changes only that site's configuration, or the maintainer has chosen to make the change everywhere.

The Fellowship's look reaches the reader through its header, footer, colours and logo. The reader's own layout stays one, so that every site runs the same pages and every improvement reaches all of them.

---

## 3. Servers and releases

### Servers

| server | whose | runs |
|---|---|---|
| https://ubsite.ddns.net, https://ubsite.sigmaai.au | the maintainer's | the latest code on `main`, deployed as often as it changes; where the community tries new features before anyone proposes them for a release |
| the Fellowship developers' dev server | the developers' | whatever they are testing: the joins with Laravel, sign-in and the header |
| a staging name for the reader, e.g. `read.staging.urantiabook.org` | the Fellowship's | a release the developers have chosen |
| https://read.urantiabook.org | the Fellowship's | a release the Fellowship has approved |

The maintainer has access to the developers' dev server for testing the joins with Laravel. The Fellowship's staging and production change only when its developers deploy a release, production only with the Fellowship's approval.

### One repository, one main line

- The Fellowship's servers run **tagged releases of this repository**, never a copy kept and edited elsewhere.
- Whatever the developers need changed in the reader (the header and footer, sign-in, deployment) goes into this repository, as configuration or a module of its own, as a pull request reviewed by both sides and merged by the maintainer. Where the two disagree, they settle it before anything is forked. If the maintainer is unavailable, the owners of the Fellowship's GitHub organisation merge without him.
- The maintainer commits to `main` freely. A commit reaches nobody on the Fellowship's servers until it is in a release they have chosen: the gate is at promotion, not at the commit.

### A release

A release is a tag `vX.Y.Z` on `main`, numbered by [Semantic Versioning](https://semver.org/spec/v2.0.0.html) as `ChangeLog.md` states: the first number goes up when anything that reads `ub.db`, the text API, or the class names in a paragraph's stored HTML has to change; the second when something is added; the third for a fix. `ChangeLog.md` says what each release changed, for readers under Added, Changed, Removed and Fixed, and for developers under For developers, which is where anything that breaks is announced. It is also the page https://read.urantiabook.org/changelog.

**The maintainer builds the database for every release.** Building and checking it needs the sources (below), TeX Live and Node, and runs gates that check the text against independent sources; the servers need none of that. Each release therefore carries, as assets of the GitHub release:

| asset | what |
|---|---|
| `ub.db` | the database, about 214 MB |
| `offline-<site>.tar` | the offline copy for each site's profile, about 73 MB each: the copy a reader downloads, 48 MB, and each translation's, a download of its own that a reader chooses (section 4) |
| `manifest.json` | the release, the code's commit, the schema version, the commits of the sources it was built from (for the Foundation's translation, the SHA-256 of its release), the text API's version, the counts, and the SHA-256 of each asset |

As `deploy.sh` does today, a release refuses a database built from uncommitted sources. The Fellowship's continuity does not rest on the maintainer's building it: `README.md` says how to build, and section 10 proposes a test of exactly that.

**What a build reads**, each named in `sources.toml`. The text's and the index's repositories are private, in the Fellowship's organisation. The study edition and two of the translations, the maintainer's own and Lila Dogim's, are public repositories in the maintainer's own account (`tigran123/urantia-study-edition`, `tigran123/ud`, `tigran123/urantia-ru`). The Foundation's translation is the zip of its HTML release, fixed by its SHA-256. Matthew Block's charts of the human sources, which the study notes are checked against, are a directory kept by a script, not a repository. The continuity test needs them all.

### Deploying a release

On a Fellowship server, a deploy:

1. checks out the tag;
2. fetches the release's assets with a read-only token, and checks each against `manifest.json`'s SHA-256;
3. syncs the Python environment from `requirements.txt`;
4. puts `ub.db` and the offline copy in place, each by a rename, and restarts the service;
5. asks `/healthz`, which answers with the paragraph count, the build time, the text version and the source commits, and switches back to the release before if it does not answer as expected.

Keep at least the release before, to switch back to. `deploy/deploy.sh` does steps 3 to 5 for the maintainer's servers today, and is the model.

### A fix to production

Production is fixed by a new patch release from `main`, never by an edit on the server. Features that `main` has gained since the release in production, and that the Fellowship has not approved, arrive with it switched off by the Fellowship site's profile (section 4).

---

## 4. The site profile

Every site that runs the reader has a profile, chosen by its host name, saying:

| what | example | status |
|---|---|---|
| its look | the Fellowship's header and footer, colours and logo | to build |
| its features | Work offline, listening, the text API, the index and appendices, the study notes, each translation, the interface in Russian, each on or off for the site | to build; the interface in Russian can already be switched off for a whole server, `UB_BILINGUAL=0` |
| its settings' defaults | the 1955 readings hidden until a reader shows them | built: `SITE_DEFAULTS` in `ubsite/settings.py`, empty until the Fellowship's site exists |
| its sign-in | Laravel's (section 6) on the Fellowship's site; the reader's own, by Google or by email, on the maintainer's | to build |
| its app's name and icon | the name and colour an installed app shows | built: `SITES` in `ubsite/app.py` |

A feature switched off by the profile is in the site's code but not drawn, linked, routed or offered. The profile holds a few large switches, not one for every element: every switch doubles what has to be tested. When testing finds a problem every reader would have, not only a preference of the Fellowship's audience, it is fixed for every site rather than switched off on one.

**Each profile has its own offline copy.** Work offline keeps the site's own pages in the reader's browser, and a page carries its header and footer. So the Fellowship's site gets a copy built with its own header, made with each release; the maintainer's sites share theirs. Each translation is a download of its own beside the copy, which a reader chooses in Settings; a translation the profile switches off is not offered.

Every gate runs under each profile.

---

## 5. The header and footer

**The Fellowship provides** its header and footer as static HTML and CSS, with a small script if one is needed, the same for every visitor: as files in a pull request to this repository, together with the address where the live version can be seen. A check, run with the others, reports when the live version has changed, as the reader already does for code it copies from elsewhere (`make vendor-check`).

**Static, because of the offline copy.** Every page of the reader is also kept in readers' browsers for reading offline. A header fetched from urantiabook.org as a page loads would be missing offline, and would differ from one copy to the next. Anything in it that differs between visitors (a member's name or picture, a basket) is filled in by its script after the page has loaded, from Laravel's identity endpoint (section 6), and is left out offline.

**Its rules:**

- Its links name urantiabook.org in full: the reader is another site.
- Its CSS is scoped to the header and footer, under a class of their own, so that it restyles nothing of the reader's.
- The reader's own controls stay: its search box, Contents, Index, the theme, Settings, Work offline and the two flags that switch its interface between English and Russian, as a bar of the reader's under the Fellowship's header.
- The footer keeps the reader's own two lines, in English or Russian with the rest of its interface. The first says that the text of *The Urantia Book* is in the public domain, and the edition as a whole, with its index, is licensed CC BY-NC-SA 4.0. This is a condition of the index's use (`CLAUDE.md` §10.5), and the offline copy carries it too. The second says that the site is not affiliated with Urantia Foundation, whose translations are its copyright and used by permission.
- Its words are in English unless the Fellowship provides them in Russian too (section 11).

---

## 6. Sign-in

**One account, Laravel's.** Laravel's session cookie is set for `.urantiabook.org` (checked on 15 October 2026), so a browser sends it to read.urantiabook.org as well. On the Fellowship's site the reader keeps no accounts and sets no cookies of its own: identity is the one piece each site's profile plugs in (section 4), and on the maintainer's servers it is the reader's own sign-in, by Google or by email.

**What Laravel provides:**

1. **An identity endpoint**, e.g. `GET https://urantiabook.org/api/reader/me`. Given the session cookie, or an app's token as `Authorization: Bearer …`, it answers `200` with the member, `{"id": …, "name": …}`, or `401`. It is the one thing the reader asks Laravel.
2. **CORS for the reader**: on that endpoint, `Access-Control-Allow-Origin: https://read.urantiabook.org` (and the staging name), with `Access-Control-Allow-Credentials: true`, so that the header's script can ask who is signed in.
3. **A return address on sign-in and sign-out**: Laravel's sign-in page accepts an address on read.urantiabook.org to come back to, on an allow-list, so that a member who signs in from the reader returns to the paragraph they were reading.

**How the reader uses it.** The browser's answer only draws the header. Whenever the reader acts on a member's behalf, storing a note, say, its server asks the endpoint itself, passing on the cookie or token it was sent, and keeps the answer for a few minutes. It never trusts an identity the browser asserts, and never logs the cookie.

**Staging** must get staging's session, not production's: the reader's staging name should be under the domain that staging's session cookie is set for, and that cookie should not be production's.

**Status:** not built on either side. Phase 2 (section 10).

---

## 7. Notes, bookmarks and highlights

**The reader keeps them**, in a database of its own, `var/user.db`, keyed by the member's id from the site's sign-in, Laravel's on the Fellowship's site: never in `ub.db`, which every build replaces whole.

**Why the reader.** A note is anchored to a paragraph and to a version of the text. When a correction moves the text, only the reader knows what moved, and it re-anchors the note by its stored quotation and text version. Kept by the reader, every feature for what members write is built once, for every site; on the Fellowship's servers the database is the Fellowship's, and backing it up is the server's job.

**The app** reads and writes them through the reader's API, with the token Laravel issued, which the reader checks with Laravel's endpoint (section 6).

**Offline:** what a member writes offline is to be kept in the browser and sent when the connection returns. Designed with the feature.

**Status:** not built. Phase 3.

---

## 8. Search from urantiabook.org's navigation bar

**Phase 1, a plain form.** Nothing to configure on the reader's side:

```html
<form action="https://read.urantiabook.org/search" method="get" role="search">
  <label for="ub-q">Search The Urantia Book</label>
  <input id="ub-q" name="q" type="search" placeholder="a word, or a reference like 101:4.2">
</form>
```

What the reader does with `q`:

- a paragraph or a range of paragraphs, `101:4.2` or `101:4.2-7`, opens the text there, by a `303` redirect;
- anything else, a section such as `101:4` included, opens the results page, each kind of result a list of its own. For a reader who has changed nothing that is the index's headwords, an exact match first, then its entries, then the text. The study notes, each translation the reader shows beside the text, and the 1955 readings are listed after them for a reader whose Settings ask for them. Every list is sent, and the reader's Settings, kept in the browser on read.urantiabook.org, decide which are shown, each kind of result with a switch of its own. `&in=index`, `&in=text`, `&in=study`, `&in=notes` (the 1955 readings) or a translation's key, `&in=ud`, opens one list whole.

Searches from the bar are counted with the reader's own, without cookies and without keeping any address. The reader's server limits how often one address may search, so an address shared by many people (an office, a proxy) may occasionally be asked to wait.

**Phase 2, if wanted: suggestions as one types.** A small JSON endpoint on the reader, e.g. `GET /search/suggest?q=`, answering with headwords and references for a dropdown under the box, with CORS for urantiabook.org. Not built; to be agreed.

---

## 9. Running the reader on a Fellowship server

**What a server needs:**

- Linux, Python 3.12 and [uv](https://docs.astral.sh/uv/), and the environment from `requirements.txt`. No TeX, no Node, no source repositories.
- A service that keeps the application running (`deploy/ubsite.service`, systemd; Uvicorn with two workers on `127.0.0.1:8130`), and nginx in front of it with TLS (`deploy/ubsite.nginx`, which also limits the search rate and compresses the stylesheet, scripts and fonts). `deploy/README.md` names the four steps that need root, which are done once.
- Disk: the release's assets (about 290 MB each, and the release before), and Merritt Horn's recordings, 6.6 GB, kept at the path the build names. The AI voice, when it is made, adds about 4 GB.
- The visit counter's place database, DB-IP City Lite, refreshed monthly (`make geoip`), and a password for the site's private `/stats` page. Each site counts its own visits, in `var/visits.db`, which backups should include, as they should `var/user.db` from phase 3.

**What size of server**, from the reader as it runs today, measured on 27 October 2026 on the maintainer's two servers and in a load test. It takes about 200 MB of memory at rest, and under 700 MB under a long burst of heavy traffic, with the two memory arenas `deploy/ubsite.service` gives it; without them it passed 1 GB. One ordinary CPU core serves about 100 pages a second, and two serve about 190; a page is about 20 KB as sent.

| | production | staging |
|---|---|---|
| CPU | 2 vCPU | 1 vCPU |
| memory | 8 GB | 4 GB |
| disk | 50 GB SSD | 30 GB SSD |

Both run Ubuntu LTS or Debian, on Intel, AMD or ARM, with root to install the service and the nginx site, and ports 80 and 443 open. The memory is a minimum, and it allows for how fast the reader has been growing, more than for what it needs today: today's reader would manage in 2 GB. Between 19 and 28 October its database grew from about 86 MB to 214 MB, as the study notes and three translations arrived, and more is planned: the quiz, the King James Bible, the figures, members' notes and bookmarks, and the Foundation's translations into other languages. 8 GB keeps the database in memory with room for all of that. Most of the bandwidth goes to listening, about 58 MB for each hour of audio; the offline copy is 48 MB once per device.

**Behind Cloudflare**, nginx must take the visitor's address from Cloudflare's header (`real_ip_header CF-Connecting-IP`, with `set_real_ip_from` for Cloudflare's ranges), or the search limit and the visit counter see Cloudflare's address for everyone. Cloudflare may cache what is under `/static/`, whose addresses change with their content; it must not cache pages.

**The reader's address today** holds a prototype of an online reader, served from Amazon S3 through CloudFront. Moving read.urantiabook.org to the reader is one DNS record.

---

## 10. Phases

**Phase 1: the reader at read.urantiabook.org.**

| the maintainer | the Fellowship's developers |
|---|---|
| the site profile: look, features, defaults | the header and footer, as files (section 5) |
| the Fellowship's profile, its offline copy | the server, its DNS and TLS, for staging and production |
| releases: tags, `manifest.json`, the assets | the deploy: fetch, check, switch, switch back |
| the schema version in `ub.db` | the search box in the navigation bar (section 8) |

**Phase 2: sign-in.** Laravel's identity endpoint, CORS and return addresses; the reader's use of them, and the member shown in the header.

**Phase 3: what members write.** Notes, bookmarks and highlights in the reader; the API the app uses for them.

**A continuity test, early in phase 1.** One of the Fellowship's developers, without the maintainer's help, takes the repositories, builds `ub.db`, passes `make check`, puts the reader up on a fresh server and makes one small change, with an AI coding agent if they like. If it takes more than a week, the documentation has a hole, and the maintainer fills it.

---

## 11. Open questions

1. **Where the reader runs.** The Fellowship will configure and manage the server itself, to the specification in section 9. Its staging and production are on hosting built around PHP. The reader needs a Python process kept running behind nginx, and root, or its equivalent, to install the service and the nginx site. Either that hosting can do it, or a small server in the Fellowship's own account will; its developers know which.
2. **Staging's name, and its session cookie** (section 6).
3. **Who approves a release for production**, and who is told when a deploy fails.
4. **The text API.** Every site running the reader serves it today; the Fellowship's profile can switch it off until the Fellowship wants it.
5. **Analytics.** The reader counts its own visits and adds no script for it. Anything else on read.urantiabook.org is a profile item to agree.
6. **The interface in Russian, under the Fellowship's header.** The reader starts in Russian for a browser whose first language is Russian, and its flags switch it. There are three choices: the Fellowship's header and footer come in Russian too, each word marked as the reader marks its own; the Fellowship's site starts every reader in English, which is a site default and needs nothing built (section 4); or its profile switches the Russian off.
7. **The translations on the Fellowship's site.** None is shown until a reader ticks it in Settings, and which ones the Fellowship's site offers is its to decide. The Foundation's written permission for its translation was given to the maintainer; whether it extends to read.urantiabook.org is to be asked of the Foundation.
