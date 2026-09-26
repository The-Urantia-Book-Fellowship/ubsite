# Deploying ubsite to pi5

`./deploy/deploy.sh` does everything that does not need root. This file names
the four things that do, so they can be read before they are run.

They are **not** in the script on purpose. A deploy script that quietly acquires
root is a deploy script nobody reads twice.

---

## The shape of it

pi5 already runs two services behind nginx on 443, told apart by name (TLS SNI):

```
ulib.ddns.net, urantia.zapto.org  ->  127.0.0.1:8000   urantia-library
proxyai.ddns.net                  ->  127.0.0.1:8090   libnodes
ub.ddns.net                       ->  127.0.0.1:8130   ubsite      <- new
_  (no-sni-default)               ->  444
```

Adding a third is one more `server` block. The browser sends the hostname in the
TLS ClientHello before any certificate is chosen, so nginx picks the block and
presents that block's certificate.

**ubsite is public.** The other two sit behind `allow 78.147.193.57; deny all;`.
This one cannot, so the nginx block replaces that protection explicitly: a rate
limit on `/search`, `client_max_body_size 1k`, and nothing else exposed.

**The database is the artifact.** The three source repositories are not on pi5
and do not need to be. `make data` runs on the development machine, where the
LaTeX lives, and `var/ub.db` is rsynced. pi5 needs no TeX and no sources.

---

## The four privileged steps

Run these by hand, once each. Step 4 is what makes every later deploy
password-free.

### 1. The systemd unit

```
sudo cp deploy/ubsite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ubsite
```

### 2. The certificate

`ub.ddns.net` must resolve to this box first. The existing certificate renews
with `authenticator = nginx`, i.e. the HTTP-01 challenge over port 80 — which
is therefore forwarded on the router, and must stay so.

```
sudo certbot --nginx -d ub.ddns.net
```

Take a **separate** certificate rather than adding the name to
`ulib.ddns.net`'s: independent renewal, and one name failing cannot take the
other down. `certbot.timer` already runs twice daily and will pick it up.

### 3. The nginx site

```
sudo cp deploy/ubsite.nginx /etc/nginx/sites-available/ubsite
sudo ln -s /etc/nginx/sites-available/ubsite /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Two things that will break it silently if ignored:

* `no-sni-default` must remain the **only** `default_server` on 443.
* `ub.ddns.net` must not also appear in `ulib.ddns.net`'s `server_name`.
  Two blocks claiming one name means the first parsed wins.

### 4. The sudoers drop-in

```
sudo install -m0440 -o root -g root deploy/ubsite.sudoers /etc/sudoers.d/ubsite
```

Grants `systemctl restart|start|stop ubsite` and nothing else. Verify rather
than assume:

```
sudo -n systemctl restart ubsite && echo AUTHORISED
```

---

## After that

```
./deploy/deploy.sh              # build here, ship, restart, poll /healthz
./deploy/deploy.sh --no-data    # code only; leave the database in place
```

Everything in it is unprivileged except the one `sudo systemctl restart ubsite`
that step 4 authorised.

`/healthz` reports `{"ok":true,"paragraphs":14586}`. It queries the database
rather than merely returning 200, so a deploy that ships a missing or truncated
`ub.db` fails at the push instead of at a reader. The script polls it for 30s
and prints the unit's status if it never comes up.

The database is shipped to `var/ub.db.new` and then `mv`d, so a half-transferred
file is never the one being served.

---

## Backups

`var/ub.db` is **derived** and must never be backed up — it rebuilds in seconds
from three git repositories, and a restored stale copy is worse than none.

There is no writable state yet. When reader annotations arrive they go in a
separate `var/user.db`, and that one is the only thing needing a backup — and a
restore tested once, because an untested backup is a rumour.
