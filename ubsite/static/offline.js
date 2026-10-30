// Work offline, the page's side: Settings' Offline tab (base.html, the panel
// .offline), which does what the cloud's menu did until 2026-10-30 (Tigran:
// the translations' ticks, greyed until a copy had been got from the menu,
// were counter-intuitive, so the tab does the whole of it, and the menu is
// gone): online or offline, and which site this is; the copy, a tick that
// downloads it and lets it go, with what it is, or how far its download has
// gone, under it; the translations kept in it; and the offer to install the
// site as an app.  And what the cloud at the header's corner shows of the
// copy, data-have: none, kept, stale (an update is waiting: the flame's dot)
// or busy.  ub.js shows the cloud, says online or offline, opens the tab from
// it, and loads this when the tab opens, or at once on a page the worker
// controls.  The worker (static/sw.js) does the work, and answers {cmd} on a
// message port with its state:
//
//   have    the copy kept: {build, made, text, index, bytes, raw, tr, trs}, or null
//   latest  the site's, when it is another: {made, fetch, full, ...}, or null
//   busy    {done, total, adding, copy} in bytes while downloading
//   error   why the last download stopped
//
// Ticking the copy registers the worker, which fetches the copy; unticking it
// removes the copy and unregisters the worker, at once, as a translation is
// let go.  Nothing else does: the copy stays through going offline and online
// again, and the worker answers from it whenever the network does not.  Until
// 2026-10-14 all this was in Settings, a switch turned on or off, and a reader
// who turned it off to be "online" again lost the copy (Tigran); the tick is
// named for the copy now, not for a mode.
//
// A kept copy is updated by itself whenever a check finds it out of date with
// the site reached and this page in view: as a page loads, as the browser
// comes online, and as the page comes into view again (keepUp).  Only from a
// page the reader has open, never in the background.  At its end What's new
// opens, saying what changed since the copy before, and the page reloads once
// it is closed (told).  Update now stays only where the copy will not update
// itself: the browser saving data, or the same update having stopped within
// the hour, when it is Try again.  Until 2026-10-30 Settings' "Keep the
// offline copy up to date" could turn this off, leaving Update now to a reader
// who kept the copy as it was until they chose; most would forget it, and
// find the copy "broken" (Tigran, 2026-10-25).
//
// The translations beside the text are each a download of their own (Tigran,
// 2026-10-26): a tick downloads one at once, with the copy where none is kept
// yet (2026-10-30), or with an update of the copy if it is out of date, and an
// untick lets it go, online or not.  What the copy keeps is the worker's
// (sw.js meta.tr), not a setting, so ↺ never removes one; and it is kept up to
// date with the copy.  `ub:trkept` tells ub.js's folds when it changes.
(function () {
  var panel = document.querySelector('dialog.settings .panel.offline'), icon = document.querySelector('.top .offline');
  if (!panel || !icon || !('serviceWorker' in navigator) || !window.isSecureContext || window.ubOfflineUI) return;
  window.ubOfflineUI = true;
  var sw = navigator.serviceWorker, line = panel.querySelector('.offcopy .state'),
      copyBox = panel.querySelector('.offcopy input'), inst = panel.querySelector('.install'), kept = false;
  // The interface's words (ubsite/l10n.js): what the tab says is HTML in both
  // languages, which CSS chooses between (T()).
  var T = window.ubT;

  // A size, "44.8 MB", and a day, "October 18": the American order, as the
  // site writes every date in words (Tigran, 2026-10-18); in Russian «44,8 МБ»
  // and «18 октября».  Each in both languages, for T().
  function mb(n) { return T.tr('{x} MB', { x: T.dec(Math.max(0.1, n / 1e6).toFixed(1)) }); }
  function day(iso) { return T.date(iso, false); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  // The index turned off in Settings: what the tab says of the copy leaves it
  // out, as the page does (settings.py `index`).
  function noIndex() { return !!window.ubSettings && window.ubSettings.get().index === false; }
  // The browser saving data: the copy is not updated by itself (keepUp), and
  // Update now is offered instead.
  function saving() { return !!(navigator.connection && navigator.connection.saveData); }
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

  // The icon: what the copy is, and while online, what it would say of it, its
  // words in each language (T.tr()).  ub.js words the rest of its label, by
  // whether this page is online.
  function mark(have, say) {
    icon.dataset.have = have;
    icon.ubSay = say || null;
    document.dispatchEvent(new Event('ub:offline'));
  }

  // An update can be had only online; offline, the tab says so instead.
  // Online is the site reached, not the browser's word alone: ub.js says it
  // from the browser and from where this page came, and the worker's check
  // of the manifest says it again (heard).  A server that is not there is
  // offline, its buttons would do nothing (Tigran, 2026-10-16).  And a site
  // that answers is online, whatever the browser says: Chrome can say offline
  // with the network working, until it is restarted (2026-10-27).
  function online() { return icon.dataset.net === 'on'; }
  function reach(on) {
    icon.dataset.net = on ? 'on' : 'off';
    document.dispatchEvent(new Event('ub:offline'));
  }
  function heard(s) {
    if (s && 'reached' in s) reach(s.reached);
    show(s);
    keepUp(s);
  }
  var last = null;
  function show(s) {
    last = s;
    watch(s);
    trs(s);
    kept = !!s && !s.removed;
    // The copy's tick: ticked while a copy is kept or fetched, and not to be
    // changed while a download runs, nor offline: none can be fetched then,
    // and a copy kept is all the site there is.
    copyBox.checked = kept;
    copyBox.disabled = !!(s && s.busy) || !online();
    if (!kept) {
      mark('none');
      return sized();
    }
    // Why a download stopped: its words as the worker kept them, or the
    // browser's own.
    var have = s.have, up = s.latest, err = s.error ? s.words || T.same(s.error) : null;
    if (s.busy) {
      var of = s.busy.total && { a: mb(s.busy.done), b: mb(s.busy.total) };
      line.innerHTML = have ? (of ? T('Updating: {a} of {b}', of) : T('Updating…'))
                            : (of ? T('Downloading: {a} of {b}', of) : T('Downloading…'));
      mark('busy', have ? (of ? T.tr('Updating the offline copy: {a} of {b}', of) : T.tr('Updating the offline copy…'))
                        : (of ? T.tr('Downloading the offline copy: {a} of {b}', of) : T.tr('Downloading the offline copy…')));
    } else if (!have) {
      line.innerHTML = (err ? T('The download stopped: {e}.', { e: err }) : T('The download did not finish.')) +
                       (online() ? ' <button type="button" class="get"><span>' + T('Try again') + '</span></button>' : '');
      mark('none', T.tr('Online; the offline copy did not finish downloading'));
    } else if (up) {
      // Out of date.  Online it is updated by itself at once (keepUp), unless
      // the browser is saving data or this update stopped within the hour:
      // then Update now and What's new.  Offline, once online.
      var held = online() && (saving() || triedLately(up.build));
      line.innerHTML = T('Out of date: kept as the site was on {d}, which has changed since.', { d: day(have.made) }) + ' ' +
                       (held ? '<br><button type="button" class="get"><span>' + T('Update now ({s})', { s: mb(up.fetch) }) +
                               '</span></button> <button type="button" class="newsbtn"><span>' +
                               T('What’s new') + '</span></button>'
                             : online() ? '' : T('It updates by itself once online.')) +
                       (err ? '<br>' + T('The last update stopped: {e}.', { e: err }) : '');
      mark('stale', T.tr('An update to the offline copy is waiting ({s})', { s: mb(up.fetch) }));
    } else {
      var at = { d: day(have.made), t: day(have.text.date), i: day(have.index.date), s: mb(have.bytes) };
      line.innerHTML = (noIndex() ? T('Up to date: kept as the site was on {d}, with the text of {t}, {s} in this browser.', at)
                                  : T('Up to date: kept as the site was on {d}, with the text of {t} and the index of {i}, {s} in this browser.', at)) +
                       ' ' + T('Without a connection, the site reads from it by itself.');
      mark('kept');
    }
  }
  // The translations: each one's tick what the copy keeps or is fetching, and
  // its size, or how far its download has gone.  With no copy kept, its size
  // is the site's manifest's (sized), and a tick downloads the copy with it.
  // Greyed while any download runs, offline for those not kept, and until the
  // sizes are known; the last line says why, or that a tick would update the
  // copy too.
  var trBox = panel.querySelector('.offtr'), trSig = null, offer = null;
  function trs(s) {
    var have = s && !s.removed && s.have, busy = s && s.busy, on = online(), by = {};
    var mine = (have && have.tr) || [], err = s && s.error ? s.words || T.same(s.error) : null;
    ((have && have.trs) || offer || []).forEach(function (t) { by[t.key] = t; });
    var of = busy && busy.total && { a: mb(busy.done), b: mb(busy.total) };
    Array.prototype.forEach.call(trBox.querySelectorAll('.offtrs li'), function (li) {
      var box = li.querySelector('input'), k = box.value, t = by[k], kept = mine.indexOf(k) >= 0,
          adding = !!busy && (busy.adding || []).indexOf(k) >= 0;
      box.checked = kept || adding;
      box.disabled = !!busy || (!kept && !on) || !t;
      li.querySelector('.st').innerHTML = adding ? (of ? T('Downloading: {a} of {b}', of) : T('Downloading…'))
        : kept && t ? T('kept, {s}', { s: mb(t.bytes) }) : t ? T(mb(t.bytes)) : '';
    });
    var why = trBox.querySelector('.why');
    why.innerHTML = busy ? '' : !have ? (on && offer ? T('offline:trwith') : '')
                  : err ? T('The download stopped: {e}.', { e: err })
                  : !on ? T('offline:troffline') : s.latest ? T('offline:trstale') : '';
    why.hidden = !why.innerHTML;
    var sig = mine.join(' ');
    if (trSig !== null && sig !== trSig) document.dispatchEvent(new Event('ub:trkept'));
    trSig = sig;
  }
  // The copy's tick: ticked, the worker is registered and fetches the copy
  // (on); unticked, the copy is removed and the worker unregistered (off).  A
  // translation's tick: the copy's translations and this one, fetched now,
  // the site's worker asked for first, as an update asks, or with no copy
  // kept, the copy with it; an update of the copy with it ends as one made by
  // itself does (told).  An untick: let go at once.
  panel.addEventListener('change', function (ev) {
    var box = ev.target;
    if (box.type !== 'checkbox') return;
    if (box === copyBox) return box.checked ? on() : off();
    if (!box.closest('.offtrs')) return;
    var have = last && !last.removed && last.have;
    if (!box.checked) return ask('drop', { tr: box.value }).then(function (s) { show(s); fresh(); });
    if (!have) return on([box.value]);
    var was = last.latest ? have.made : null;
    going = true;
    show(Object.assign({}, last, { busy: { done: 0, total: 0, adding: [box.value], copy: !!was } }));
    newest().then(function () { return ask('get', { tr: (have.tr || []).concat(box.value) }); }).then(function (s) {
      going = false;
      show(s);
      if (s && s.error) fresh();
      else if (was) told(was);
    }, function () { going = false; });
  });

  // While a download goes on, the worker says how far it is.  A worker can be
  // stopped by the browser mid-way and say nothing more; if it is quiet for a
  // while, ask it, and show what it says: the copy before, and the button.
  var quiet = null;
  function watch(s) {
    clearTimeout(quiet);
    if (s && s.busy) quiet = setTimeout(function () { ask('state').then(show); }, 20000);
  }
  // Before there is a copy: what it would cost, in the tick's hint (base.html,
  // offline:copyhint), and each translation's size, from the site's manifest;
  // the tick itself is greyed until that has come.  A site that does not
  // answer, or answers 5xx, is offline here too, and one that answers is
  // online.
  function sized() {
    line.textContent = '';
    copyBox.disabled = true;
    var gone = function () { reach(false); return Promise.reject(); };
    fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (r.status >= 500) return gone();
      reach(true);
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }, gone).then(function (m) {
      if (kept) return;
      Array.prototype.forEach.call(panel.querySelectorAll('.offcopy .size'), function (el) {
        el.innerHTML = T('offline:about', { s: mb(m.bytes) });
      });
      offer = m.translations || [];
      copyBox.disabled = false;
      trs(last);
    }, function () {
      if (kept) return;
      line.innerHTML = !online() ? T('It can be downloaded only online.') : T('This site has no offline copy yet.');
      mark('none');
    });
  }

  // What's new: what changed on the site after this copy was made, from the
  // manifest an update would fetch (offline/news.py), newest first, by day.
  // Until 2026-10-23 it added a line of its own where the text or the index
  // was newer than the copy's, "The index as of October 23"; a new revision of
  // either has a line in the changelog now, which that only repeated (Tigran).
  // A modal dialog of its own, over Settings where it is opened from there:
  // a popover outside a modal dialog is inert while that is open, and
  // cannot be closed (until 2026-10-30 it was a popover inside the cloud's
  // menu's).  Escape, its ×, and a tap outside it close it.  At its foot, the
  // whole changelog, the page /changelog (2026-10-18).  After an update made
  // by itself, it says so, and lists what changed since the copy before,
  // whose date is `since` until it closes (told).
  var news = document.createElement('dialog'), since = null;
  news.id = 'offnews';
  news.className = 'offnews';
  news.setAttribute('aria-labelledby', 'offnews-title');
  document.body.appendChild(news);
  news.addEventListener('close', function () { since = null; });
  news.addEventListener('click', function (ev) {
    var r = news.getBoundingClientRect();
    if (ev.target.closest('.x') || (ev.target === news && (ev.clientX < r.left || ev.clientX > r.right ||
                                                           ev.clientY < r.top || ev.clientY > r.bottom)))
      news.close();
  });
  function openNews() {
    whatsNew();
    if (!news.open) news.showModal();
  }
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
      return '<h3>' + T(day(d)) + '</h3><ul><li>' + days[d].join('</li><li>') + '</li></ul>';
    }).join('') + (n.earlier && oldest && made < oldest.t ? '<p class="earlier">' + T('And earlier changes.') + '</p>' : '') : '';
  }
  function whatsNew() {
    var made = since || (last && last.have && last.have.made);
    news.innerHTML = '<div class="bar"><h2 id="offnews-title">' + T('What’s new') + '</h2>' +
      '<button type="button" class="x" ' + T.a('aria-label', 'Close') + ' ' +
      T.a('title', 'Close') + '><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/>' +
      '</svg></button></div><p class="since">' +
      (since ? T('The offline copy has just been updated. New since its last update, on {d}:', { d: day(since) })
             : made ? T('Since your copy, kept as the site was on {d}:', { d: day(made) }) : '') +
      '</p><div class="days">…</div>' +
      (since ? '<p class="then">' + (listening() ? T('The next page you open is the new one.')
                                                 : T('Closing this reloads the page, so that it is the new one too.')) + '</p>'
             : '') +
      '<p class="all"><a href="/changelog">' + T('The whole changelog') + '</a></p>';
    var out = news.querySelector('.days');
    if (!made) { out.textContent = ''; return; }
    manifest().then(function (m) {
      out.innerHTML = listed(m, made) || '<p>' + T('Nothing is listed for this update.') + '</p>';
    }, function () {
      out.innerHTML = T('The list could not be fetched just now.');
    });
  }

  // A download that stopped asks whether the site is still there: if not, its
  // buttons go with it, rather than come back to do nothing again.  An update
  // that ends whole reloads this page, so that it is the new one too, playing
  // or not (Tigran, 2026-10-18); while What's new is open, once it closes.
  // One made by itself (`was`, the date of the copy before) says so first
  // (told).  One that stops is not made by itself again for an hour (failed).
  // `trs` names the translations to fetch with the copy (a first copy got by a
  // translation's tick).
  function get(update, was, trs) {
    return ask('get', trs ? { tr: trs } : {}).then(function (s) {
      show(s);
      if (s && s.error) {
        failed(s.latest && s.latest.build);
        fresh();
      } else if (was) told(was);
      else if (update) reload();
    });
  }
  function reload() {
    if (news.open) return news.addEventListener('close', function () { reload(); }, { once: true });
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
  // The copy, ticked: the worker registered, and the copy fetched, with the
  // translations `trs` where a translation's tick asked for it.  Said at once,
  // as an update is, so that the tick does not look as if it did nothing.  A
  // first copy reloads nothing.
  function on(trs) {
    going = true;
    show({ have: null, latest: null, busy: { done: 0, total: 0, adding: trs || [], copy: true }, error: null, removed: false });
    sw.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then(function () {
      if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
      return get(false, null, trs);
    }).catch(function (e) {
      show(null);
      line.innerHTML = T('This browser would not keep it: {e}', { e: e && e.message || e });
    }).then(function () { going = false; });
  }
  // Unticked: the copy removed and the worker unregistered, at once.  The
  // menu's Remove asked first; a tick named for the copy is not mistaken for
  // going online, which was the bug of 2026-10-14.
  function off() {
    copyBox.disabled = true;
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

  // An update made by itself: when a check finds the copy out of date, with
  // the site reached and this page in view, unless the browser is saving
  // data, or this browser tried the same update by itself within the hour and
  // it stopped (Update now offers it then).  A download already under way,
  // from the page before a link was followed, or from a tick there, is this
  // page's to finish: asking the worker for it again waits for the one
  // running.
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
    if (going || !s || !s.have || document.hidden || !online()) return;
    if (s.busy) {
      going = true;
      return get(true, s.have.made).then(function () { going = false; }, function () { going = false; });
    }
    if (!s.latest || triedLately(s.latest.build) || saving()) return;
    update(true);
  }
  // Its end: What's new says that the copy has just been updated and lists
  // what changed since the copy before (`was`), and the page reloads once it
  // is closed, as after Update now; while listening, it does not, which would
  // stop the reading.  With nothing listed, no reader would see a difference:
  // nothing is said and nothing reloaded, and the next page is the new one.
  // It waits for the page to be in view, and for Settings to close.
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
      openNews();
      if (!listening()) reload();
    }, function () {});
  }

  panel.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button');
    if (!b) return;
    if (b.classList.contains('get')) update(false);
    else if (b.classList.contains('newsbtn')) openNews();
    else if (b.classList.contains('app') && window.ubInstall) {
      window.ubInstall.prompt();
      window.ubInstall.userChoice.then(function () { window.ubInstall = null; installed(); });
    }
  });
  // The worker's word, as a download goes on.
  sw.addEventListener('message', function (e) { if (e.data && e.data.ubOffline) show(e.data.ubOffline); });

  // Install as an app: where the browser offers it (Chrome, Edge), a button;
  // on an iPhone or iPad, how, and why it matters there.  Not in an app.
  function installed() {
    var app = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
    var ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
              (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (app) inst.innerHTML = '';
    else if (window.ubInstall) inst.innerHTML = '<button type="button" class="app"><span>' + T('Install as an app') + '</span></button> ' +
      '<small>' + T('it opens on its own, from the home screen or the dock') + '</small>';
    else if (ios) inst.innerHTML = '<small>' + T('offline:ios') + '</small>';
    else inst.innerHTML = '';
    inst.hidden = !inst.innerHTML;
  }
  document.addEventListener('ub:installable', installed);
  installed();

  // A page load asks at most once an hour, and at once where the page starts
  // offline, the browser saying so or the page from the copy: a 304 of a few
  // hundred bytes says whether the site is there.
  sw.getRegistration('/').then(function (reg) {
    if (!reg) return show(null);
    kept = true;
    return ask('check', { force: !online() }).then(heard);
  });
  // Opening the tab asks the site afresh, and so do the browser's online and
  // offline: whatever it says, so that a page from the copy learns that the
  // site is back, and the site's answer is the last word.  With no copy, the
  // manifest is asked for again, for the tick and the sizes.
  function fresh() {
    if (kept) ask('check', { force: true }).then(heard);
    else show(null);
  }
  document.addEventListener('ub:offtab', fresh);
  window.addEventListener('online', fresh);
  // Coming into view again, as an app brought back to the front, whose page
  // does not load again: asked as a page load asks, so that the copy is kept
  // up to date by itself there too (keepUp).
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && kept) ask('check', { force: !online() }).then(heard);
  });
  window.addEventListener('offline', function () { if (last) show(last); fresh(); });
})();
