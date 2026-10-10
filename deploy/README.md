# Deploying ubsite to pi5

`./deploy/deploy.sh` does everything that does not need root. This file names the four things that do, so they can be read before they are run.

They are **not** in the script on purpose. A deploy script that quietly acquires root is a deploy script nobody reads twice.

---

## The shape of it

nginx on pi5 serves two names on 443, told apart by name (TLS SNI):

```
ulib.ddns.net, urantia.zapto.org  ->  127.0.0.1:8000   urantia-library
ubsite.ddns.net                   ->  127.0.0.1:8130   ubsite
_  (no-sni-default)               ->  444
```

libnodes is the third service on pi5, LAN-only at `http://pi5:8090/` with nothing in front of it, so nginx has no block for it.

Each is one `server` block. The browser sends the hostname in the TLS ClientHello before any certificate is chosen, so nginx picks the block and presents that block's certificate.

**ubsite is public**, and so the nginx block gives it limits of its own: a rate limit on `/search`, `client_max_body_size 1k`, and nothing else exposed.

**The database is the artifact.** The three source repositories are not on pi5 and do not need to be. `make data` runs on the development machine, where the LaTeX lives, and `var/ub.db` is rsynced. pi5 needs no TeX and no sources.

---

## The four privileged steps

Run these by hand, once each. Step 4 is what makes every later deploy password-free.

### 1. The systemd unit

```
sudo cp deploy/ubsite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ubsite
```

### 2. The certificate

`ubsite.ddns.net` must resolve to this box first. The existing certificate renews with `authenticator = nginx`, i.e. the HTTP-01 challenge over port 80 — which is therefore forwarded on the router, and must stay so.

```
sudo certbot certonly --nginx -d ubsite.ddns.net --deploy-hook "systemctl reload nginx"
```

This comes **before** step 3, and the site must not be linked into `sites-enabled/` yet. `ubsite.nginx` names key files that do not exist until this step has run, and certbot runs `nginx -t` before doing anything, so an enabled site that points at a missing key stops it. With no server block claiming the name, certbot adds a temporary one of its own for the challenge.

`certonly` rather than plain `--nginx` so that certbot does not rewrite `ubsite.nginx` on the box: the installed file stays identical to this one. `--nginx` still records `installer = nginx` in the renewal config, and certbot reloads nginx after a renewal on that alone. The `--deploy-hook` (saved as `renew_hook`) is a second reload. It is harmless, and it still fires if the installer is ever changed.

Take a **separate** certificate rather than adding the name to `ulib.ddns.net`'s: independent renewal, and one name failing cannot take the other down. `certbot.timer` already runs twice daily and will pick it up.

### 3. The nginx site

```
sudo install -m0644 -o root -g root deploy/ubsite.nginx /etc/nginx/sites-available/ubsite.ddns.net
sudo ln -s /etc/nginx/sites-available/ubsite.ddns.net /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Two things that will break it silently if ignored:

* `no-sni-default` must remain the **only** `default_server` on 443.
* `ubsite.ddns.net` must not also appear in `ulib.ddns.net`'s `server_name`. Two blocks claiming one name means the first parsed wins.

### 4. The sudoers drop-in

```
sudo install -m0440 -o root -g root deploy/ubsite.sudoers /etc/sudoers.d/ubsite
```

Grants `systemctl restart|start|stop ubsite` and nothing else. Verify rather than assume:

```
sudo -n systemctl restart ubsite && echo AUTHORISED
```

---

## After that

```
./deploy/deploy.sh              # build here, ship, restart, poll /healthz
./deploy/deploy.sh --no-data    # code only; leave the database in place
```

Everything in it is unprivileged except the one `sudo systemctl restart ubsite` that step 4 authorised.

`/healthz` reports `{"ok":true,"paragraphs":14586}`. It queries the database rather than merely returning 200, so a deploy that ships a missing or truncated `ub.db` fails at the push instead of at a reader. The script polls it for 30s and prints the unit's status if it never comes up.

The database is shipped to `var/ub.db.new` and then `mv`d, so a half-transferred file is never the one being served.

---

## Backups

`var/ub.db` is **derived** and must never be backed up — it rebuilds in seconds from three git repositories, and a restored stale copy is worse than none.

The one piece of writable state is **`var/visits.db`**, the visit counter's record (README, "Visits"). Losing it loses the history of who came, and nothing else; the site does not read it except on `/stats`. It holds no IP addresses. To keep a copy:

```
ssh pi5 'sqlite3 ~/ubsite/var/visits.db ".backup /home/tigran/visits-$(date +%F).db"'
```

`var/stats.passwd` is the scrypt hash of the `/stats` password, and is remade, not restored (`python -m ubsite.stats passwd`). The DB-IP database in `var/geoip/` is shipped by `deploy.sh`.

When reader annotations arrive they go in a separate `var/user.db`, and that will need a real backup, and a restore tested once, because an untested backup is a rumour.
