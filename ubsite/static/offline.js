// Work offline, the page's side: the menu that the icon at the header's corner
// opens (#offmenu in base.html), with the switch, what it says about the copy,
// and the offer to install the site as an app; and what the icon shows of the
// copy, data-have: none, kept, stale (an update is waiting: the flame's dot)
// or busy.  ub.js shows the icon, says online or offline, and loads this when
// the menu opens, or at once on a page the worker controls.  The worker
// (static/sw.js) does the work, and answers {cmd} on a message port with its
// state:
//
//   have    the copy kept: {build, made, text, index, bytes, raw}, or null
//   latest  the site's, when it is another: {made, fetch, full, ...}, or null
//   busy    {done, total} in bytes while downloading
//   error   why the last download stopped
//
// Downloading registers the worker, which fetches the copy; updating asks for
// the site's worker first, and reloads the page once the copy is in; removing
// it removes the copy and unregisters the worker.  Nothing else does: the copy
// stays through going offline and online again, and the worker answers from
// it whenever the network does not.  An out-of-date copy is said, with what
// the update costs, whenever the menu shows it, and the icon has the flame's
// dot.  Until 2026-10-14 all this was in Settings, a switch turned on or off,
// and a reader who turned it off to be "online" again lost the copy; a stale
// copy was announced by a line under the header too (Tigran).
//
// Unless Settings' "Keep the offline copy up to date" is off (settings.py
// OFFLINE), an out-of-date copy is updated by itself, as if Update now had
// been tapped, whenever a check finds it so with the site reached and this
// page in view: as a page loads, as the browser comes online, and as the page
// comes into view again (keepUp).  Only from a page the reader has open, never
// in the background.  At its end What's new opens, saying what changed since
// the copy before, and the page reloads once it is closed (told).  Update now
// is for a reader who keeps the copy as it was until they choose; most would
// forget it, and find the copy "broken" (Tigran, 2026-10-25).
(function () {
  var box = document.getElementById('offmenu'), icon = document.querySelector('.top .offline');
  if (!box || !icon || !('serviceWorker' in navigator) || !window.isSecureContext || window.ubOfflineUI) return;
  window.ubOfflineUI = true;
  var sw = navigator.serviceWorker, line = box.querySelector('.state'), drop = box.querySelector('p.remove'),
      inst = box.querySelector('.install'), kept = false;
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
                'October', 'November', 'December'];

  function mb(n) { return Math.max(0.1, n / 1e6).toFixed(1) + ' MB'; }
  // "October 18": the American order, as the site writes every date in words
  // (Tigran, 2026-10-18).
  function day(iso) {
    var d = new Date(iso);
    return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate();
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  // The index turned off in Settings: what the menu says of the copy leaves it
  // out, as the page does (settings.py `index`).
  function noIndex() { return !!window.ubSettings && window.ubSettings.get().index === false; }
  // Kept up to date by itself (settings.py `autoupdate`), on unless turned off.
  function byItself() { return !window.ubSettings || window.ubSettings.get().autoupdate !== false; }
  // Listening: closing What's new then reloads nothing, which would stop it.
  function listening() { return !!document.querySelector('.player'); }
  function ask(cmd, more) {
    return sw.ready.then(function (reg) {
      return new Promise(function (resolve) {
        var ch = new MessageChannel();
        ch.port1.onmessage = function (e) { resolve(e.data); };
        var msg = { cmd: cmd };
        for (var k in more || {}) msg[k] = more[k];
        reg.active.postMessage(msg, [ch.port2]);
      });
    });
  }

  // The icon: what the copy is, and while online, what it would say of it.
  // ub.js words the rest of its label, by whether this page is online.
  function mark(have, say) {
    icon.dataset.have = have;
    if (say) icon.dataset.say = say; else delete icon.dataset.say;
    document.dispatchEvent(new Event('ub:offline'));
  }

  // An update can be had only online; offline, the menu says so instead.
  // Online is the site reached, not the browser's word alone: ub.js says it
  // from the browser and from where this page came, and the worker's check
  // of the manifest says it again (heard).  A server that is not there is
  // offline, its buttons would do nothing (Tigran, 2026-10-16).
  function online() { return icon.dataset.net === 'on'; }
  function reach(on) { icon.dataset.net = on ? 'on' : 'off'; }
  function heard(s) {
    if (s && 'reached' in s) reach(s.reached);
    show(s);
    keepUp(s);
  }
  var last = null;
  function show(s) {
    last = s;
    watch(s);
    kept = !!s && !s.removed;
    // Not while it downloads, nor offline, when it is all the site there is.
    drop.hidden = !kept || !!(s && s.busy) || !online();
    if (!kept) {
      mark('none');
      return sized();
    }
    var have = s.have, up = s.latest, err = s.error ? esc(s.error) : '';
    if (s.busy) {
      line.textContent = (have ? 'Updating' : 'Downloading') + (s.busy.total
        ? ': ' + mb(s.busy.done) + ' of ' + mb(s.busy.total) : '…');
      mark('busy', (have ? 'Updating the offline copy' : 'Downloading the offline copy') + (s.busy.total
        ? ': ' + mb(s.busy.done) + ' of ' + mb(s.busy.total) : '…'));
    } else if (!have) {
      line.innerHTML = (err ? 'The download stopped: ' + err + '.' : 'The download did not finish.') +
                       (online() ? ' <button type="button" class="get"><span>Try again</span></button>' : '');
      mark('none', 'Online; the offline copy did not finish downloading');
    } else if (up) {
      line.innerHTML = 'Out of date: kept as the site was on ' + day(have.made) + ', which has changed since. ' +
                       (online() ? '<br><button type="button" class="get"><span>Update now (' + mb(up.fetch) + ')</span></button>' +
                                   ' <button type="button" class="newsbtn" popovertarget="offnews"><span>What’s new</span></button>'
                                 : byItself() ? 'It updates by itself once online.' : 'It can be updated once online.') +
                       (err ? '<br>The last update stopped: ' + err + '.' : '');
      mark('stale', 'An update to the offline copy is waiting (' + mb(up.fetch) + ')');
    } else {
      line.textContent = 'Up to date: kept as the site was on ' + day(have.made) + ', with the text of ' +
                         day(have.text.date) + (noIndex() ? '' : ' and the index of ' + day(have.index.date)) + ', ' +
                         mb(have.bytes) + ' in this browser. ' +
                         'Without a connection, the site reads from it by itself.';
      mark('kept');
    }
  }
  // While a download goes on, the worker says how far it is.  A worker can be
  // stopped by the browser mid-way and say nothing more; if it is quiet for a
  // while, ask it, and show what it says: the copy before, and the button.
  var quiet = null;
  function watch(s) {
    clearTimeout(quiet);
    if (s && s.busy) quiet = setTimeout(function () { ask('state').then(show); }, 20000);
  }
  // Before there is a copy: what it would cost, and the button.  A site that
  // does not answer, or answers 5xx, is offline here too.
  function sized() {
    line.textContent = '';
    var gone = function () { reach(false); return Promise.reject(); };
    fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (r.status >= 500) return gone();
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }, gone).then(function (m) {
      if (!kept) line.innerHTML = 'About ' + mb(m.bytes) + ' to download and keep in this browser.' +
                                  '<br><button type="button" class="keep"><span>Download it</span></button>';
    }, function () {
      if (kept) return;
      line.textContent = !online() ? 'It can be downloaded only online.' : 'This site has no offline copy yet.';
      mark('none');
    });
  }

  // What's new: what changed on the site after this copy was made, from the
  // manifest an update would fetch (offline/news.py), newest first, by day.
  // Until 2026-10-23 it added a line of its own where the text or the index
  // was newer than the copy's, "The index as of October 23"; a new revision of
  // either has a line in the changelog now, which that only repeated (Tigran).
  // A popup over the menu, which stays open
  // beneath it with its Update button: a popover inside the menu's, so the
  // browser counts it the menu's own.  At its foot, the whole changelog, the
  // page /changelog (2026-10-18).  After an update made by itself, it says so,
  // and lists what changed since the copy before, whose date is `since` until
  // it closes (told).
  var news = document.createElement('div'), since = null;
  news.id = 'offnews';
  news.className = 'offnews';
  news.setAttribute('popover', '');
  news.setAttribute('role', 'dialog');
  news.setAttribute('aria-labelledby', 'offnews-title');
  box.appendChild(news);
  news.addEventListener('beforetoggle', function (ev) { if (ev.newState === 'open') whatsNew(); });
  news.addEventListener('toggle', function (ev) { if (ev.newState === 'closed') since = null; });
  function manifest() {
    return fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }
  // What the manifest lists after `made`, by day, newest first: '' for nothing.
  function listed(m, made) {
    var days = {}, order = [], n = m.news || { items: [] };
    function put(d, html) {
      if (!days[d]) { days[d] = []; order.push(d); }
      days[d].push(html);
    }
    // The times are UTC, written alike, so they compare as strings.
    n.items.forEach(function (x) { if (x.t > made) put(x.d, esc(x.s)); });
    order.sort().reverse();
    var oldest = n.items[n.items.length - 1];
    return order.length ? order.map(function (d) {
      return '<h3>' + day(d) + '</h3><ul><li>' + days[d].join('</li><li>') + '</li></ul>';
    }).join('') + (n.earlier && oldest && made < oldest.t ? '<p class="earlier">And earlier changes.</p>' : '') : '';
  }
  function whatsNew() {
    var made = since || (last && last.have && last.have.made);
    news.innerHTML = '<div class="bar"><h2 id="offnews-title">What’s new</h2>' +
      '<button type="button" class="x" popovertarget="offnews" popovertargetaction="hide" aria-label="Close" ' +
      'title="Close"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/>' +
      '</svg></button></div><p class="since">' +
      (since ? 'The offline copy has just been updated. New since its last update, on ' + day(since) + ':'
             : made ? 'Since your copy, kept as the site was on ' + day(made) + ':' : '') +
      '</p><div class="days">…</div>' +
      (since ? '<p class="then">' + (listening() ? 'The next page you open is the new one.'
                                                 : 'Closing this reloads the page, so that it is the new one too.') + '</p>'
             : '') +
      '<p class="all"><a href="/changelog">The whole changelog</a></p>';
    var out = news.querySelector('.days');
    if (!made) { out.textContent = ''; return; }
    manifest().then(function (m) {
      out.innerHTML = listed(m, made) || '<p>Nothing is listed for this update.</p>';
    }, function () {
      out.textContent = 'The list could not be fetched just now.';
    });
  }

  // A download that stopped asks whether the site is still there: if not, its
  // buttons go with it, rather than come back to do nothing again.  An update
  // that ends whole reloads this page, so that it is the new one too, playing
  // or not (Tigran, 2026-10-18); while What's new is open, once it closes.
  // One made by itself (`was`, the date of the copy before) says so first
  // (told).  One that stops is not made by itself again for an hour (failed).
  function get(update, was) {
    return ask('get').then(function (s) {
      show(s);
      if (s && s.error) {
        failed(s.latest && s.latest.build);
        fresh();
      } else if (was) told(was);
      else if (update) reload();
    });
  }
  function reload() {
    if (news.matches(':popover-open'))
      return news.addEventListener('toggle', function (ev) { if (ev.newState === 'closed') reload(); });
    history.scrollRestoration = 'auto';   // listen.js may have set it to manual
    location.reload();
  }
  // The site's worker, asked for before an update and waited for, so that the
  // new one, if there is one, fetches the copy and answers every page after.
  // The browser itself looks only as a page loads online: an app kept open
  // across a deploy would otherwise take the copy with the old worker, and a
  // reader going offline at once would keep it.
  function newest() {
    return sw.getRegistration('/').then(function (reg) {
      return reg && reg.update().then(function () {
        var w = reg.installing || reg.waiting;
        return w && new Promise(function (resolve) {
          var done = function () { if (w.state === 'activated' || w.state === 'redundant') resolve(); };
          w.addEventListener('statechange', done);
          done();
        });
      });
    }).catch(function () {});
  }
  function on() {
    line.textContent = 'Starting…';
    sw.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then(function () {
      if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
      return get();
    }).catch(function (e) {
      line.textContent = 'This browser would not keep it: ' + (e && e.message || e);
    });
  }
  function off() {
    if (!window.confirm('Remove the offline copy from this browser? It can be downloaded again at any time.')) return;
    ask('remove').then(function () {
      return sw.getRegistration('/');
    }).then(function (reg) { return reg && reg.unregister(); }).then(function () { show(null); });
  }
  // Update now, tapped (or Try again), or made by itself (keepUp).  Said here
  // at once, not left to the worker: the button goes, so a second tap cannot
  // look as if it did nothing.  `going` while this page has one under way.
  var going = false;
  function update(itself) {
    var have = last && last.have;
    going = true;
    show(Object.assign({}, last || {}, { busy: { done: 0, total: 0 }, removed: false }));
    return newest().then(function () { return get(!!have, itself && have && have.made); })
      .then(function () { going = false; }, function () { going = false; });
  }

  // An update made by itself, where Settings has not turned that off: when a
  // check finds the copy out of date, with the site reached and this page in
  // view, unless the browser is saving data, or this browser tried the same
  // update by itself within the hour and it stopped (Update now still offers
  // it).  A download already under way, from the page before a link was
  // followed, or from Update now there, is this page's to finish: asking the
  // worker for it again waits for the one running.
  var TRIED = 'ub_offline_auto', HOUR = 3600 * 1000, tried = null;
  function failed(build) {
    if (!build) return;
    tried = { build: build, at: Date.now() };
    try { localStorage.setItem(TRIED, JSON.stringify(tried)); } catch (e) {}
  }
  function triedLately(build) {
    var t = tried;
    try { t = JSON.parse(localStorage.getItem(TRIED)) || t; } catch (e) {}
    return !!t && t.build === build && Date.now() - t.at < HOUR;
  }
  function keepUp(s) {
    if (going || !byItself() || !s || !s.have || document.hidden || !online()) return;
    if (s.busy) {
      going = true;
      return get(true, s.have.made).then(function () { going = false; }, function () { going = false; });
    }
    if (!s.latest || triedLately(s.latest.build)) return;
    if (navigator.connection && navigator.connection.saveData) return;
    update(true);
  }
  // Its end: What's new, opened over the menu, says that the copy has just
  // been updated and lists what changed since the copy before (`was`), and the
  // page reloads once it is closed, as after Update now; while listening, it
  // does not, which would stop the reading.  With nothing listed, no reader
  // would see a difference: nothing is said and nothing reloaded, and the
  // next page is the new one.  It waits for the page to be in view, and for
  // Settings to close.
  function told(was) {
    var dlg = document.querySelector('dialog[open]');
    if (dlg) return dlg.addEventListener('close', function () { told(was); }, { once: true });
    if (document.hidden) {
      var seen = function () {
        if (document.hidden) return;
        document.removeEventListener('visibilitychange', seen);
        told(was);
      };
      return document.addEventListener('visibilitychange', seen);
    }
    manifest().then(function (m) {
      if (!listed(m, was)) return;
      since = was;
      if (!box.matches(':popover-open')) box.showPopover();
      if (news.matches(':popover-open')) whatsNew(); else news.showPopover();
      if (!listening()) reload();
    }, function () {});
  }

  box.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button');
    if (!b) return;
    if (b.classList.contains('keep')) on();
    else if (b.classList.contains('drop')) off();
    else if (b.classList.contains('get')) update(false);
    else if (b.classList.contains('app') && window.ubInstall) {
      window.ubInstall.prompt();
      window.ubInstall.userChoice.then(function () { window.ubInstall = null; installed(); });
    }
  });
  // The worker's word, as a download goes on.
  sw.addEventListener('message', function (e) { if (e.data && e.data.ubOffline) show(e.data.ubOffline); });

  // Install as an app: where the browser offers it (Chrome, Edge), a button;
  // on an iPhone or iPad, how, and why it matters there.
  function installed() {
    var app = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
    var ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
              (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (app) inst.innerHTML = '';
    else if (window.ubInstall) inst.innerHTML = '<button type="button" class="app"><span>Install as an app</span></button> ' +
      '<small>it opens on its own, from the home screen or the dock</small>';
    else if (ios) inst.innerHTML = '<small>On an iPhone or iPad, add it to the Home Screen too (Share, then Add to ' +
      'Home Screen): Safari deletes what a site keeps after seven days without a visit, but not for an app ' +
      'on the Home Screen.</small>';
    else inst.innerHTML = '';
    inst.hidden = !inst.innerHTML;
  }
  document.addEventListener('ub:installable', installed);
  installed();

  sw.getRegistration('/').then(function (reg) {
    if (!reg) return show(null);
    kept = true;
    return ask('check').then(heard);
  });
  // Opening the menu asks the site afresh, and so does coming back online: a
  // 304 of a few hundred bytes.  Going offline only takes the buttons away.
  // Asked whenever the browser is online, the site reached or not, so that a
  // page from the copy learns that the site is back.
  function fresh() { if (kept && navigator.onLine !== false) ask('check', { force: true }).then(heard); }
  box.addEventListener('toggle', function (ev) { if (ev.newState === 'open') fresh(); });
  window.addEventListener('online', fresh);
  // Coming into view again, as an app brought back to the front, whose page
  // does not load again: asked as a page load asks, at most once an hour,
  // so that the copy is kept up to date by itself there too (keepUp).
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && kept && navigator.onLine !== false) ask('check').then(heard);
  });
  window.addEventListener('offline', function () { if (last) show(last); });
})();
