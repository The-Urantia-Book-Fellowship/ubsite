# Deploying ubsite

ubsite runs on two hosts, from the same build: **pi5**, at home, as `ubsite.ddns.net`, and the **VPS** that serves sigmaai.au, as `ubsite.sigmaai.au`. `./deploy/deploy.sh` does everything that does not need root, on both. This file names the four things on each host that do, so they can be read before they are run.

They are **not** in the script on purpose. A deploy script that quietly acquires root is a deploy script nobody reads twice.

---

## pi5: ubsite.ddns.net

nginx on pi5 serves two names on 443, told apart by name (TLS SNI):

```
ulib.ddns.net, urantia.zapto.org  ->  127.0.0.1:8000   urantia-library
ubsite.ddns.net                   ->  127.0.0.1:8130   ubsite
_  (no-sni-default)               ->  444
```

libnodes is the third service on pi5, LAN-only at `http://pi5:8090/` with nothing in front of it, so nginx has no block for it.

Each is one `server` block. The browser sends the hostname in the TLS ClientHello before any certificate is chosen, so nginx picks the block and presents that block's certificate.

**ubsite is public**, and so the nginx block gives it limits of its own: a rate limit on `/search`, `client_max_body_size 1k`, and nothing else exposed.

**The database is the artifact.** The three source repositories are not on the hosts and do not need to be. `make data` runs on the development machine, where the LaTeX lives, and `var/ub.db` is rsynced. The hosts need no TeX and no sources.

---

### The four privileged steps on pi5

Run these by hand, once each. Step 4 is what makes every later deploy password-free.

#### 1. The systemd unit

```
sudo cp deploy/ubsite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ubsite
```

#### 2. The certificate

`ubsite.ddns.net` must resolve to this box first. The existing certificate renews with `authenticator = nginx`, i.e. the HTTP-01 challenge over port 80 — which is therefore forwarded on the router, and must stay so.

```
sudo certbot certonly --nginx -d ubsite.ddns.net --deploy-hook "systemctl reload nginx"
```

This comes **before** step 3, and the site must not be linked into `sites-enabled/` yet. `ubsite.nginx` names key files that do not exist until this step has run, and certbot runs `nginx -t` before doing anything, so an enabled site that points at a missing key stops it. With no server block claiming the name, certbot adds a temporary one of its own for the challenge.

`certonly` rather than plain `--nginx` so that certbot does not rewrite `ubsite.nginx` on the box: the installed file stays identical to this one. `--nginx` still records `installer = nginx` in the renewal config, and certbot reloads nginx after a renewal on that alone. The `--deploy-hook` (saved as `renew_hook`) is a second reload. It is harmless, and it still fires if the installer is ever changed.

Take a **separate** certificate rather than adding the name to `ulib.ddns.net`'s: independent renewal, and one name failing cannot take the other down. `certbot.timer` already runs twice daily and will pick it up.

#### 3. The nginx site

```
sudo install -m0644 -o root -g root deploy/ubsite.nginx /etc/nginx/sites-available/ubsite.ddns.net
sudo ln -s /etc/nginx/sites-available/ubsite.ddns.net /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

The installed file is world-readable (0644), so checking it against this one needs no root: `ssh pi5 cat /etc/nginx/sites-available/ubsite.ddns.net | diff - deploy/ubsite.nginx`.

Two things that will break it silently if ignored:

* `no-sni-default` must remain the **only** `default_server` on 443.
* `ubsite.ddns.net` must not also appear in `ulib.ddns.net`'s `server_name`. Two blocks claiming one name means the first parsed wins.

#### 4. The sudoers drop-in

```
sudo install -m0440 -o root -g root deploy/ubsite.sudoers /etc/sudoers.d/ubsite
```

Grants `systemctl restart|start|stop ubsite` and nothing else. Verify rather than assume:

```
sudo -n systemctl restart ubsite && echo AUTHORISED
```

---

## The VPS: ubsite.sigmaai.au

The VPS is the machine that serves sigmaai.au, and `deploy.sh` reaches it by that name (x86_64, 8 cores, 31 GB, Ubuntu 26.04). ubsite runs there exactly as on pi5: the same unit, the same tree at `/home/tigran/ubsite`, port 8130, and the same build from every deploy. It went live on 2026-10-14.

nginx there serves two other sites. `sigmaai.au` serves by path: Open WebUI at `/`, CashReconAI at `/cashreconai/`. urantia-library has a name of its own, `ulib.sigmaai.au`, since 2026-10-25, as pi5's is `ulib.ddns.net`; until then it was at `sigmaai.au/library/`, which now only redirects there. ubsite has a name of its own instead of a path. It assumes it lives at `/`: its links, its service worker's scope and the links stored in `ub.db` all do. And under a name of its own its offline copy and settings live in an origin of their own, apart from those apps.

```
sigmaai.au         ->  Open WebUI, /cashreconai/   (the default, implicitly; /library/ redirects)
ubsite.sigmaai.au  ->  127.0.0.1:8130   ubsite
ulib.sigmaai.au    ->  127.0.0.1:8000   urantia-library
```

* **No `default_server`.** The VPS declares none: `sigmaai.au` is the default on 80 and 443 only because `sites-enabled/` is read in name order and it comes first. `ubsite-sigmaai.nginx` must never claim it.
* **The name is an A record at GoDaddy**, which holds sigmaai.au's DNS (`ns43`/`ns44.domaincontrol.com`): `ubsite` → `187.77.167.246`. No AAAA: nginx there listens on IPv4 only.
* **Port 80 is open** (a VPS has no router to forget it), and sigmaai.au's own certificate renews over HTTP-01 through it, as this one does.
* Merritt Horn's recordings are at `/Audio/Urantia/Urantia-MH-Audio-DVD`, as on pi5.
* tigran has no sudo there beyond what step 4's drop-in grants, so the steps below that need root are run as root, without `sudo`.

### The four privileged steps on the VPS

Run from `~/ubsite` on the VPS, after `./deploy/deploy.sh --no-restart sigmaai.au` has put the tree there:

```
# 1. the unit: the same file as pi5's
sudo cp deploy/ubsite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ubsite
curl -s 127.0.0.1:8130/healthz

# 2. the certificate, before the site is enabled (pi5's step 2 says why)
sudo certbot certonly --nginx -d ubsite.sigmaai.au --deploy-hook "systemctl reload nginx"

# 3. the nginx site
sudo install -m0644 -o root -g root deploy/ubsite-sigmaai.nginx /etc/nginx/sites-available/ubsite.sigmaai.au
sudo ln -s /etc/nginx/sites-available/ubsite.sigmaai.au /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 4. the sudoers drop-in: the same file as pi5's
sudo install -m0440 -o root -g root deploy/ubsite.sudoers /etc/sudoers.d/ubsite
sudo -n systemctl restart ubsite && echo AUTHORISED
```

`deploy/ubsite-sigmaai.nginx` is pi5's block with the other name and certificate, and `tests/test_nginx.py` fails if the two differ in anything else. Check the installed file as pi5's is checked: `ssh sigmaai.au cat /etc/nginx/sites-available/ubsite.sigmaai.au | diff - deploy/ubsite-sigmaai.nginx`.

The `/stats` password is pi5's: its hash was copied, so one password opens both. Each host counts its own visitors in its own `var/visits.db`.

---

## After that

```
./deploy/deploy.sh              # build here, ship to pi5 and then sigmaai.au, restart each, poll /healthz
./deploy/deploy.sh sigmaai.au   # to one host (pi5 or sigmaai.au)
./deploy/deploy.sh --no-data    # code only; leave the database in place
```

Everything in it is unprivileged except the one `sudo systemctl restart ubsite` on each host that its step 4 authorised.

`/healthz` reports `{"ok":true,"paragraphs":14586}`. It queries the database rather than merely returning 200, so a deploy that ships a missing or truncated `ub.db` fails at the push instead of at a reader. The script polls it for 30s and prints the unit's status if it never comes up, and then stops, before the next host.

The database is shipped to `var/ub.db.new` and then `mv`d, so a half-transferred file is never the one being served.

---

## Backups

`var/ub.db` is **derived** and must never be backed up — it rebuilds in seconds from three git repositories, and a restored stale copy is worse than none.

The one piece of writable state is **`var/visits.db`**, the visit counter's record (README, "Visits"). Losing it loses the history of who came, and nothing else; the site does not read it except on `/stats`. It holds no IP addresses. To keep a copy:

```
ssh pi5 'sqlite3 ~/ubsite/var/visits.db ".backup /home/tigran/visits-$(date +%F).db"'
ssh sigmaai.au 'cd ~/ubsite && .venv/bin/python -c "import sqlite3; sqlite3.connect(\"var/visits.db\").backup(sqlite3.connect(\"/home/tigran/visits-$(date +%F).db\"))"'
```

The VPS has no `sqlite3` command, so its copy goes through Python. The two hosts' records are separate, and both are worth keeping.

`var/stats.passwd` is the scrypt hash of the `/stats` password, and is remade, not restored (`python -m ubsite.stats passwd`). The DB-IP database in `var/geoip/` is shipped by `deploy.sh`.

**`var/quiz.db`** is the quiz's board (`ubsite/board.py`), on the VPS alone, which keeps it for both sites: the names readers chose and the first answers they gave, no IP address, no cookie. It is the one thing readers gave the site, and no build makes it again, so `deploy.sh` brings a copy of it here before every deploy that includes the VPS, made there by SQLite's own backup, to `var/board/quiz-<date>.db`. To restore one: stop the unit, put the copy at `~/ubsite/var/quiz.db` (and remove any `quiz.db-wal` and `quiz.db-shm` beside it), start the unit. `tests/test_board.py` restores a copy made the same way and reads the same board from it.

When reader annotations arrive they go in a separate `var/user.db`, and that will need a real backup, and a restore tested once, because an untested backup is a rumour.

---

## The quiz's board

Kept by **ubsite.sigmaai.au** (`UB_BOARD`, which defaults to it, so the unit stays the same file on both hosts). pi5's pages send to it and read from it across origins; pi5's app answers the board's routes 404 and never makes a `var/quiz.db`. Its only POSTs, `/quiz/board/join` and `/quiz/board/answers`, have nginx locations of their own, exact matches (trap 19), with a body of up to 16 KB and 10 a minute from one address; everything else keeps the 1 KB limit.

**The nginx files changed with it (2026-10-28), so each host's must be installed again**, as root, which is Tigran's to run (CLAUDE.md, Privilege):

```
# pi5
sudo install -m0644 -o root -g root deploy/ubsite.nginx /etc/nginx/sites-available/ubsite.ddns.net
sudo nginx -t && sudo systemctl reload nginx
# the VPS
sudo install -m0644 -o root -g root deploy/ubsite-sigmaai.nginx /etc/nginx/sites-available/ubsite.sigmaai.au
sudo nginx -t && sudo systemctl reload nginx
```

Then, through nginx itself (trap 19): `curl -sI https://ubsite.sigmaai.au/quiz/board` is a 200, not a 301; an `OPTIONS` to `/quiz/board/join` with `Origin: https://ubsite.ddns.net` is a 204 naming that origin; a POST of 40 KB is a 413; and a POST to ubsite.ddns.net's is the app's 404.

A name that should not be there is taken off on the VPS, its line kept and the name still taken:

```
cd ~/ubsite && .venv/bin/python -m ubsite.board list
.venv/bin/python -m ubsite.board hide "NAME"       # and `show` to put it back
.venv/bin/python -m ubsite.board rename "OLD" "NEW"
```

