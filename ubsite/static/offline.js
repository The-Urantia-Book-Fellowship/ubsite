// Work offline, the page's side: Settings' Offline tab (base.html, the panel
// .offline), which does what the cloud's menu did until 2026-10-30 (Tigran:
// the translations' ticks, greyed until a copy had been got from the menu,
// were counter-intuitive, so the tab does the whole of it, and the menu is
// gone): online or offline, and which site this is; the copy, "Base", with
// what it is, or how far its download has gone, under it; the translations
// kept in it; and the offer to install the site as an app.  And what the
// cloud at the header's corner shows of the copy, data-have: none, kept,
// stale (an update is waiting: the flame's dot) or busy.  ub.js shows the
// cloud, says online or offline, opens the tab from it, and loads this on
// every page: at once on one the worker controls, once it has loaded on one
// it does not.  The worker (static/sw.js) does the work, and answers {cmd} on
// a message port with its state:
//
//   have    the copy kept: {build, made, text, index, bytes, raw, tr, trs}, or null
//   latest  the site's, when it is another: {made, fetch, full, ...}, or null
//   busy    {done, total, adding, copy} in bytes while downloading
//   error   why the last download stopped
//
// Every browser keeps the copy, and reads the site from it (Tigran,
// 2026-11-10): a page with no worker registers it, once the site's manifest
// has answered, and the worker fetches the copy, with nothing tapped (sized,
// on); a first download that stopped, the reader gone or the worker ended by
// the browser, goes on by itself from the next page, with what it had
// (keepUp).  In every browser, saving data or short of room alike (Tigran,
// 2026-11-10: "49 MB is not too much.  If it grows into hundreds of MB we'll
// revisit this"); only not again within the hour of a download that failed,
// when the tab says so, with Try again.  There is no letting it go but the
// browser's own site data.  From 2026-10-30 until then it was a tick, which registered
// the worker and fetched the copy, and unticked removed both, asking first;
// until 2026-10-14 a switch in Settings, which a reader turned off to be
// "online" again, and lost the copy (Tigran).
//
// A kept copy is updated by itself whenever a check finds it out of date with
// the site reached and this page in view: as a page loads, as the browser
// comes online, and as the page comes into view again (keepUp).  Only from a
// page the reader has open, never in the background.  Without a word, and
// with no reload: the next page opened is the new one (Tigran, 2026-11-10;
// until then What's new opened at its end, and the page reloaded once it was
// closed).  What's new is the reader's to open, from the ? at the header's
// corner (ub.js, 'ub:news'), and lists what the last update brought.  Update
// now stands where the copy will not update itself: the reader having turned
// that off, the browser saving data, or the same update having stopped within
// the hour.
//
// Automatic updates, the switch under Base (Tigran, 2026-11-10: with the
// copy every browser's, a reader must be able to keep the one they have, his
// case a server no longer to be trusted): off, the copy is fetched again only
// by Update now, beside What's new, which lists what the update would bring;
// and the worker goes on answering from it first though the site has another
// build (sw.js `pinned`), which is the half that matters, an out-of-date copy
// being otherwise passed over for the server.  What it is, is the worker's
// (state.auto, {cmd: 'auto'}), not a setting: ↺ never turns it on again, and
// the worker knows it before a page's scripts run.  It does not govern the
// first copy.  Until 2026-10-30 a setting, "Keep the offline copy up to
// date", did the first half of this, leaving Update now to a reader who kept
// the copy as it was until they chose; most would forget it, and find the
// copy "broken" (Tigran, 2026-10-25), so it is on unless turned off.
//
// The translations beside the text are each a download of their own (Tigran,
// 2026-10-26): a tick downloads one at once, with the copy where none is kept
// yet (2026-10-30), or with an update of the copy if it is out of date, and an
// untick lets it go, online or not, asking first (2026-11-10).  What the copy keeps is the worker's
// (sw.js meta.tr), not a setting, so ↺ never removes one; and it is kept up to
// date with the copy.  `ub:trkept` tells ub.js's folds when it changes.
(function () {
  var panel = document.querySelector('dialog.settings .panel.offline'), icon = document.querySelector('.top .offline');
  if (!panel || !icon || !('serviceWorker' in navigator) || !window.isSecureContext || window.ubOfflineUI) return;
  window.ubOfflineUI = {};
  var sw = navigator.serviceWorker, line = panel.querySelector('.offcopy .state'),
      inst = panel.querySelector('.install'), autoBox = panel.querySelector('.offcopy input.auto'), kept = false;
  // The interface's words (ubsite/l10n.js): what the tab says is HTML in both
  // languages, which CSS chooses between (T()).
  var T = window.ubT;

  // A size, "44.8 MB", and a day, "October 18": the American order, as the
  // site writes every date in words (Tigran, 2026-10-18); in Russian «44,8 МБ»
  // and «18 октября».  Each in both languages, for T().
  function mb(n) { return T.tr('{x} MB', { x: T.dec(Math.max(0.1, n / 1e6).toFixed(1)) }); }
  // A recording's sizes: a paper's in whole megabytes, a part's or a voice's in
  // gigabytes to two places, as a phone's own settings count them (decimal).
  function mbw(n) { return T.tr('{x} MB', { x: Math.round(n / 1e6) }); }
  function gb(n) { return T.tr('{x} GB', { x: T.dec((n / 1e9).toFixed(2)) }); }
  function size(n) { return n >= 1e9 ? gb(n) : n >= 1e7 ? mbw(n) : mb(n); }
  function hours(sec) { return T.tr('{h} h', { h: Math.round(sec / 3600) }); }
  function day(iso) { return T.date(iso, false); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  // The browser saving data: the copy is not updated by itself (keepUp), and
  // Update now is offered instead.
  function saving() { return !!(navigator.connection && navigator.connection.saveData); }
  // Storage the browser will not clear under pressure.  Chrome and Safari
  // decide by themselves; Firefox asks the reader, so there it is asked only
  // with something the reader did (`act`): a translation ticked, a recording
  // kept, a button tapped.
  function persist(act) {
    if (!navigator.storage || !navigator.storage.persist || (!act && /Firefox\//.test(navigator.userAgent))) return;
    navigator.storage.persist().catch(function () {});
  }
  function ask(cmd, more) {
    return sw.ready.then(function (reg) {
      return new Promise(function (resolve) {
        var ch = new MessageChannel();
        // A command the worker refused, {error} alone (a translation let go
        // while a download runs, a recording whose list could not be had), is
        // no state: what is so now is asked for and shown instead, so that
        // the change is seen not made.  Until 2026-11-09 it was drawn as a
        // download that had stopped, in English, every translation's tick
        // cleared.
        ch.port1.onmessage = function (e) {
          if (cmd !== 'state' && e.data && 'error' in e.data && !('have' in e.data)) ask('state').then(resolve);
          else resolve(e.data);
        };
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
  var last = null, refused = null;
  function show(s) {
    last = s;
    watch(s);
    trs(s);
    recShow(s);
    // Automatic updates: as the worker has it, on unless it says off (a
    // worker from before the switch says nothing); greyed until there is a
    // copy to hold, and while one downloads.
    if (autoBox) {
      autoBox.checked = !s || s.auto !== false;
      autoBox.disabled = !s || !s.have || !!s.busy;
    }
    // `kept`: a worker is registered, with a copy or on its way to one.
    kept = !!s;
    if (!kept) {
      mark('none');
      return sized();
    }
    // The hint's size is for a copy not yet kept (sized); kept, the line
    // under it says what it takes.
    if (s.have) Array.prototype.forEach.call(panel.querySelectorAll('.offcopy .size'), function (el) { el.textContent = ''; });
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
      // No copy yet, and none on its way: it stopped, and goes on by itself
      // from the next page (keepUp), or at once from the button.
      line.innerHTML = (err ? T('The download stopped: {e}.', { e: err }) : T('The download did not finish.')) +
                       (online() ? ' <button type="button" class="pill solid get">' + T('Try again') + '</button>' : '');
      mark('none', T.tr('Online; the offline copy did not finish downloading'));
    } else if (up) {
      // Out of date.  Online it is updated by itself at once (keepUp), unless
      // the reader has turned that off, the browser is saving data or this
      // update stopped within the hour: then Update now and What's new.
      // Offline, once online: by itself, or by the reader.
      var off = s.auto === false, held = online() && (off || saving() || triedLately(up.build));
      line.innerHTML = T('Out of date: kept as the site was on {d}, which has changed since.', { d: day(have.made) }) + ' ' +
                       (held ? '<br><button type="button" class="pill solid get">' + T('Update now ({s})', { s: mb(up.fetch) }) +
                               '</button> <button type="button" class="pill newsbtn">' +
                               T('What’s new') + '</button>'
                             : online() ? '' : off ? T('It can be updated once online.')
                             : T('It updates by itself once online.')) +
                       (err ? '<br>' + T('The last update stopped: {e}.', { e: err }) : '');
      mark('stale', T.tr('An update to the offline copy is waiting ({s})', { s: mb(up.fetch) }));
    } else {
      // The index's date whatever Settings' `index`: the copy keeps the index
      // either way, and counts it in its size (Tigran, 2026-11-09; until then
      // the line left it out while the index was off, so a phone with it off
      // and a desktop with it on described the same copy differently).
      var at = { d: day(have.made), t: day(have.text.date), i: day(have.index.date), s: mb(have.bytes) };
      line.innerHTML = T('Up to date: kept as the site was on {d}, with the text of {t} and the index of {i}, {s} in this browser.', at) +
                       ' ' + T('The site reads from it, and asks the server only for what it does not hold.');
      // A recording downloading shows on the cloud as the copy's download does.
      var rb = s.audio && s.audio.busy;
      mark(rb ? 'busy' : 'kept', rb ? T.tr('Downloading {v}: Paper {n}, {a} of {b}',
        { v: recName(rb.v), n: rb.n, a: mbw(rb.done), b: mbw(rb.total) }) : null);
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
    var have = s && s.have, busy = s && s.busy, on = online(), by = {};
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
    trFold();
  }
  // Those the reader shows beside the text (Settings' Translations tab) stand
  // first; the rest fold away under a line that counts them, so that the tab
  // stays short as the Foundation's languages come (Tigran, 2026-11-04).  A
  // reader may still keep one it does not show.
  var trMain = trBox.querySelector('ul.offtrs'), trMore = trBox.querySelector('.offmore'),
      trOrder = Array.prototype.slice.call(trBox.querySelectorAll('.offtrs li'));
  function trFold() {
    var shown = window.ubSettings ? String(window.ubSettings.get().translations || '').split(' ') : [];
    var others = trOrder.filter(function (li) { return shown.indexOf(li.querySelector('input').value) < 0; });
    trOrder.forEach(function (li) {
      var into = others.indexOf(li) >= 0 ? trMore.querySelector('ul') : trMain;
      if (li.parentNode !== into) into.appendChild(li);
    });
    trMore.hidden = !others.length;
    trMore.querySelector('summary .w').innerHTML = others.length === trOrder.length
      ? T('All translations · {n}', { n: others.length }) : T('Other translations · {n}', { n: others.length });
  }
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail && ev.detail.key === 'translations') trFold();
  });
  // A translation's tick: the copy's translations and this one, fetched now,
  // the site's worker asked for first, as an update asks, or with no copy
  // kept, the copy with it; an update of the copy with it ends as one made by
  // itself does, without a word.  An untick lets it go, once the reader has
  // said yes to it: it asks first, naming the translation and what it takes,
  // and offline that it can be had again only once online, as a recording's
  // let-go asks (Tigran, 2026-11-10; from 2026-10-26 it let go at once, and a
  // stray tap deleted 12 MB).  Cancelled, the tick comes back.
  // Automatic updates, ticked or unticked: the worker told, which keeps it
  // (sw.js setAuto), and what it then says shown; turned on with an update
  // waiting, that is fetched at once, as a page's load would fetch it.
  panel.addEventListener('change', function (ev) {
    var box = ev.target;
    if (box === autoBox) return ask('auto', { on: box.checked }).then(function (s) { show(s); keepUp(s); });
    if (box.type !== 'checkbox' || !box.closest('.offtrs')) return;
    var have = last && last.have;
    // A translation's download fetches the site's copy as it is now, so with
    // the copy out of date it updates that too: said on the tab's last line
    // (offline:trstale), and with the updating turned off asked first, the
    // reader having chosen to keep the copy as it is.
    if (box.checked && have && last.latest && last.auto === false && !window.confirm(T.text('offline:trupdate'))) {
      box.checked = false;
      return;
    }
    if (!box.checked) {
      var w = box.closest('li').querySelector('.w'), t = ((have && have.trs) || []).filter(function (x) { return x.key === box.value; })[0],
          p = { t: T.same(w ? w.textContent.replace(/\s+/g, ' ').trim() : box.value), s: mb(t ? t.bytes : 0) };
      if (!window.confirm(online() ? T.text('offline:trdrop', p) : T.text('offline:trdropoff', p))) {
        box.checked = true;
        return;
      }
      return ask('drop', { tr: box.value }).then(function (s) { show(s); fresh(); });
    }
    persist(true);
    if (!have) return on([box.value]);
    going = true;
    show(Object.assign({}, last, { busy: { done: 0, total: 0, adding: [box.value], copy: !!last.latest } }));
    newestWorker().then(function () { return ask('get', { tr: (have.tr || []).concat(box.value) }); }).then(function (s) {
      going = false;
      show(s);
      if (s && s.error) fresh();
    }, function () { going = false; });
  });

  // While a download goes on, the worker says how far it is.  A worker can be
  // stopped by the browser mid-way and say nothing more; if it is quiet for a
  // while, ask it, and show what it says: the copy before, and the button.
  // A download it has lost so (the browser ends a worker's message after five
  // minutes, and a first copy on a slow line takes longer) is no longer this
  // page's under way, and goes on by itself with what it had (keepUp).
  var quiet = null;
  function watch(s) {
    clearTimeout(quiet);
    if (s && (s.busy || (s.audio && s.audio.queue.length)))
      quiet = setTimeout(function () {
        pumping = false;
        ask('state').then(function (now) {
          var lost = !!s.busy && now && !now.busy;
          if (lost) going = false;
          show(now);
          if (lost) keepUp(now);
        });
      }, 20000);
  }
  // Before there is a worker: what the copy costs, in its hint (base.html,
  // offline:copyhint), and each translation's size, from the site's manifest;
  // and, the manifest come, the worker registered and the copy fetched by
  // itself (on), unless a download failed within the hour, when the line
  // says so and offers it again.  A site that does
  // not answer, or answers 5xx, is offline here too, and one that answers is
  // online; one with no copy built (a 404: `make serve` before `make
  // offline`) registers nothing.
  function sized() {
    line.textContent = '';
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
      trs(last);
      if (going) return;
      if (!triedLately(FIRST)) return on();
      line.innerHTML = (refused || T('The download did not finish.')) + ' <button type="button" class="pill solid get">' +
                       T('Try again') + '</button>';
    }, function () {
      if (kept) return;
      line.innerHTML = !online() ? T('It can be downloaded only online.') : T('This site has no offline copy yet.');
      mark('none');
    });
  }

  // What's new: what changed on the site, by day, newest first, from the
  // `news` a manifest carries (offline/news.py).  Opened by the reader, from
  // the ? at the header's corner (ub.js, 'ub:news') or beside Update now,
  // never by itself (Tigran, 2026-11-10; from 2026-10-25 until then it opened
  // at the end of an update made by itself, and closing it reloaded the
  // page).  Which list, and since when:
  //   an update waiting   the site's, since the copy kept was made;
  //   a copy up to date   the copy's own, from the worker, the server not
  //                       asked: what its last update brought, since the copy
  //                       before it was made (sw.js meta.since); or, where it
  //                       has never been updated, or that update brought
  //                       nothing for a reader, the three newest days;
  //   no copy             the site's, the three newest days.
  // Until 2026-10-23 it added a line of its own where the text or the index
  // was newer than the copy's, "The index as of October 23"; a new revision of
  // either has a line in the changelog now, which that only repeated (Tigran).
  // A modal dialog of its own, over Settings where it is opened from there:
  // a popover outside a modal dialog is inert while that is open, and
  // cannot be closed (until 2026-10-30 it was a popover inside the cloud's
  // menu's).  Escape, its ×, and a tap outside it close it.  At its foot, the
  // whole changelog, the page /changelog (2026-10-18).
  var news = document.createElement('dialog');
  news.id = 'offnews';
  news.className = 'offnews';
  news.setAttribute('aria-labelledby', 'offnews-title');
  document.body.appendChild(news);
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
  window.ubOfflineUI.news = openNews;
  function manifest() {
    return fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }
  // What the list `n` has after `made`, by day, newest first: '' for nothing.
  function listed(n, made) {
    var days = {}, order = [];
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
  // Its three newest days: the list is newest first, so everything after the
  // first entry of a fourth day.
  function newest(n) {
    var seen = [], cut = '';
    n.items.some(function (x) {
      if (seen.indexOf(x.d) < 0) seen.push(x.d);
      if (seen.length > 3) cut = x.t;
      return seen.length > 3;
    });
    return listed(n, cut);
  }
  function whatsNew() {
    var have = last && last.have, stale = !!(have && last.latest), since = have && !stale && last.since;
    news.innerHTML = '<div class="bar"><h2 id="offnews-title">' + T('What’s new') + '</h2>' +
      '<button type="button" class="x" ' + T.a('aria-label', 'Close') + ' ' +
      T.a('title', 'Close') + '><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/>' +
      '</svg></button></div><p class="since"></p><div class="days">…</div>' +
      '<p class="all"><a href="/changelog">' + T('The whole changelog') + '</a></p>';
    var head = news.querySelector('.since'), out = news.querySelector('.days');
    var own = function () { return ask('news'); };
    var site = function () { return manifest().then(function (m) { return m.news || { items: [] }; }); };
    (stale ? site().then(null, own) : have ? own() : site()).then(function (n) {
      var html = stale ? listed(n, have.made) : since ? listed(n, since) : '';
      if (html) head.innerHTML = stale ? T('Since your copy, kept as the site was on {d}:', { d: day(have.made) })
                                       : T('New since {d}:', { d: day(since) });
      else if (stale) html = '<p>' + T('Nothing is listed for this update.') + '</p>';
      else if ((html = newest(n))) head.innerHTML = T('The latest changes:');
      out.innerHTML = html || '<p>' + T('Nothing is listed for this update.') + '</p>';
    }, function () {
      out.innerHTML = T('The list could not be fetched just now.');
    });
  }

  // A download that stopped asks whether the site is still there: if not, its
  // buttons go with it, rather than come back to do nothing again.  An update
  // that ends whole, asked for by a tap on Update now (`reloads`), reloads
  // this page, so that it is the new one too, playing or not (Tigran,
  // 2026-10-18); while What's new is open, once it closes.  One made by
  // itself reloads nothing and says nothing: the next page is the new one
  // (2026-11-10).  One that stops is not made by itself again for an hour
  // (failed).  `trs` names the translations to fetch with the copy (a first
  // copy got by a translation's tick).
  function get(reloads, trs) {
    return ask('get', trs ? { tr: trs } : {}).then(function (s) {
      show(s);
      if (s && s.error) {
        failed(s.have ? s.latest && s.latest.build : FIRST);
        fresh();
      } else if (reloads) reload();
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
  function newestWorker() {
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
  // The first copy: the worker registered, and the copy fetched, with the
  // translations `trs` where a translation's tick asked for it.  Said at once,
  // as an update is.  A first copy reloads nothing: the page stays the
  // server's, and the next is the copy's, which is the same.
  // `rec`, a recording's papers asked for before any copy was kept, {voice,
  // papers}, go on its queue once the copy is in (2026-11-04).
  function on(trs, rec) {
    going = true;
    show({ have: null, latest: null, busy: { done: 0, total: 0, adding: trs || [], copy: true }, error: null });
    sw.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then(function () {
      persist(!!(trs || rec));
      return get(false, trs);
    }).then(function () {
      if (rec && last && last.have) return ask('keep', rec).then(show);
    }).catch(function (e) {
      // Not registered: said (sized), and not tried again by itself for an
      // hour.
      refused = T('This browser would not keep it: {e}', { e: e && e.message || e });
      failed(FIRST);
      going = false;
      show(null);
    }).then(function () { going = false; });
  }
  // Update now, tapped (or Try again), or made by itself (keepUp).  Said here
  // at once, not left to the worker: the button goes, so a second tap cannot
  // look as if it did nothing.  `going` while this page has one under way.
  var going = false;
  function update(itself) {
    var have = last && last.have;
    going = true;
    show(Object.assign({}, last || {}, { busy: { done: 0, total: 0 } }));
    return newestWorker().then(function () { return get(!!have && !itself); })
      .then(function () { going = false; }, function () { going = false; });
  }

  // An update made by itself: when a check finds the copy out of date, with
  // the site reached and this page in view, unless the reader has turned the
  // updating off (state.auto false), the browser is saving data, or this
  // browser tried the same update by itself within the hour and it stopped
  // (Update now offers it in each case).  A download already under way,
  // from the page before a link was followed, or from a tick there, is this
  // page's to finish: asking the worker for it again waits for the one
  // running.
  // A first copy goes by the same rule, under FIRST where a build would be:
  // with a worker and no copy, at each of these moments it is fetched, what
  // it had carried over (sw.js download()), saving data or not.
  var TRIED = 'ub_offline_auto', HOUR = 3600 * 1000, tried = null, FIRST = 'first';
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
    if (going || !s || !online()) return;
    if (!s.have) {
      if (s.busy) {
        going = true;
        return get(false).then(function () { going = false; }, function () { going = false; });
      }
      if (!triedLately(FIRST)) update(true);
      return;
    }
    if (document.hidden) return;
    if (s.busy) {
      going = true;
      return get(false).then(function () { going = false; }, function () { going = false; });
    }
    if (!s.latest || s.auto === false || triedLately(s.latest.build) || saving()) return;
    update(true);
  }
  panel.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button');
    if (!b) return;
    if (b.classList.contains('get')) {
      persist(true);
      if (kept) update(false); else on();
    }
    else if (b.classList.contains('newsbtn')) openNews();
    else if (b.classList.contains('app') && window.ubInstall) {
      window.ubInstall.prompt();
      window.ubInstall.userChoice.then(function () { window.ubInstall = null; installed(); });
    }
  });
  // ---- The recordings kept (sw.js, The recordings kept; Tigran, 2026-11-04) --
  // A fold to each voice the database carries (base.html .offrec), which is its
  // whole-book row; opened, its parts, each folded to its papers, drawn from
  // the voice's list, /offline/audio/<key>.json, when it first opens.  One
  // control to a row, of four states: ↓ to keep, a ring while it downloads
  // (its progress --p; tap to stop), ✓ kept (tap to let go, a paper at once,
  // a part or a voice after asking), ↓ over the ring of a part kept.  What is
  // kept is the worker's word (state.audio): the papers whole, those in part,
  // the queue, the file under way.  The page pumps the download, one file a
  // message, while the queue is not empty and the page is online (pump), and
  // keeps the screen on meanwhile (hold).
  var recBox = panel.querySelector('.offrec'), recLists = {}, recIdx = {}, room = null, pumping = false;
  var ROMAN = ['', 'I', 'II', 'III', 'IV'];
  var ICONS = {
    none: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v7.5M4.5 7.5L8 11l3.5-3.5M3.5 13.5h9"/></svg>',
    busy: '<svg viewBox="0 0 16 16" aria-hidden="true"><path class="f" d="M5 5h6v6H5z"/></svg>',
    kept: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-6.5"/></svg>'
  };
  ICONS.some = ICONS.none;
  function recList(key) {
    if (recLists[key]) return recLists[key];
    var p = recLists[key] = fetch('/offline/audio/' + key + '.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (list) {
      list.byN = {};
      list.papers.forEach(function (x) { list.byN[x.n] = x; });
      recIdx[key] = list;
      return list;
    });
    p.catch(function () { delete recLists[key]; });
    return p;
  }
  function recVoice(key) { return recBox.querySelector('.recvoice[data-key="' + key + '"]'); }
  // A voice's name, in each language where ru.toml has it (app.py puts the
  // voices' names in l10n.js), from its row until its list has come.
  function recName(key) {
    var list = recIdx[key], el = recVoice(key), en = el && el.querySelector('.rname x-en');
    var s = list ? list.label : en ? en.textContent : key;
    return T.has(s) ? T.tr(s) : T.same(s);
  }
  function recBytes(a) {
    var n = 0;
    if (a && a.voices) Object.keys(a.voices).forEach(function (k) { n += a.voices[k].bytes || 0; });
    return n;
  }
  // The voice's list fetched and its parts drawn, once; its row's hours and
  // size with them, so the whole-book control is never offered unsized (on
  // the first evening it was, "0.1 MB": Tigran, 2026-11-04).  Drawn again
  // when Settings moves the Foreword (below).
  function ensure(key) {
    return recList(key).then(function (list) {
      var det = recVoice(key);
      if (det && !det.dataset.drawn) {
        det.dataset.drawn = '1';
        det.querySelector(':scope > summary .rmeta').innerHTML = T(hours(list.seconds)) + ' · ' + T(size(list.bytes));
        det.querySelector('.parts').innerHTML = recTree(list);
        recShow(last);
      }
      return list;
    });
  }
  // Every voice's, as the tab opens and whenever the page comes online again
  // after that: the lists are the copy's where one is kept, and ~30 KB each
  // from the site where none is.
  var recWanted = false;
  function ensureAll() {
    Array.prototype.forEach.call(recBox.querySelectorAll('.recvoice'), function (det) {
      ensure(det.dataset.key).catch(function () {});
    });
  }
  document.addEventListener('ub:offtab', function () { recWanted = true; ensureAll(); });
  window.addEventListener('online', function () {
    if (recWanted) ensureAll();
    if (last && last.audio && last.audio.error) pump(last, true);
  });
  // Loaded by the tab's own opening (ub.js), the event is past: the panel
  // shown says so.
  if (panel.classList.contains('on')) { recWanted = true; ensureAll(); }
  // The parts, each folded to its papers.  The list counts the Foreword in
  // Part I (app.py _audio_list), as the left rail lists it; with Settings'
  // Foreword in Part I off it is a row of its own before the parts, at their
  // level (ub.css .parts > .recrow), and Part I begins at Paper 1.
  function fwIn() { return document.documentElement.dataset.foreword !== 'off'; }
  function sum(xs, k) { return xs.reduce(function (t, x) { return t + x[k]; }, 0); }
  function recRow(x) {
    return '<div class="recrow" data-n="' + x.n + '"><span class="rpn">' + x.n + '</span>' +
      '<span class="rname" title="' + esc(x.title) + '">' + esc(x.title) + '</span>' +
      '<span class="rmeta"></span><button type="button" class="keep" data-st="none"></button></div>';
  }
  function recTree(list) {
    var out = [];
    if (!fwIn() && list.byN[0]) out.push(recRow(list.byN[0]));
    list.parts.forEach(function (pt) {
      var first = !fwIn() && pt.first === 0 ? 1 : pt.first,
          papers = list.papers.filter(function (x) { return first <= x.n && x.n <= pt.last; });
      if (!papers.length) return;
      out.push('<details class="recpart" data-part="' + pt.n + '" data-first="' + first + '" data-last="' + pt.last + '"><summary>' +
        '<span class="rfold"></span><span class="w"><span class="rname">' + T('Part {r}', { r: ROMAN[pt.n] || pt.n }) +
        '<span class="rpt"> · ' + esc(pt.title) + '</span></span><small class="rst"></small></span>' +
        '<span class="rmeta">' + T(hours(sum(papers, 'seconds'))) + ' · ' + T(size(sum(papers, 'bytes'))) + '</span>' +
        '<button type="button" class="keep" data-st="none"></button></summary>' +
        papers.map(recRow).join('') + '</details>');
    });
    return out.join('');
  }
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key !== 'foreword') return;
    Array.prototype.forEach.call(recBox.querySelectorAll('.recvoice[data-drawn]'), function (det) {
      delete det.dataset.drawn;
      ensure(det.dataset.key).catch(function () {});
    });
  });
  // What a row's papers are, against the state: all kept, any on the queue,
  // some kept, none; and the bytes held of them.
  function stateOf(ns, v, queued) {
    var kept = 0, some = 0, q = 0;
    ns.forEach(function (n) {
      if (v.kept.indexOf(n) >= 0) kept++;
      else { if (v.partial[n]) some++; if (queued[n]) q++; }
    });
    return q ? 'busy' : ns.length && kept === ns.length ? 'kept' : kept || some ? 'some' : 'none';
  }
  function heldOf(ns, v, busy, key, byN) {
    var b = 0;
    ns.forEach(function (n) {
      if (busy && busy.v === key && busy.n === n) b += busy.done;
      else if (v.kept.indexOf(n) >= 0) b += byN[n].bytes;
      else if (v.partial[n]) b += v.partial[n];
    });
    return b;
  }
  // A control's state, its ring's progress, and its words.
  function setKeep(btn, st, held, total, what) {
    btn.dataset.st = st;
    if (btn.dataset.icon !== st) { btn.dataset.icon = st; btn.innerHTML = ICONS[st]; }
    btn.style.setProperty('--p', total ? Math.max(0, Math.min(1, held / total)).toFixed(3) : '0');
    btn.dataset.room = room !== null && st === 'none' && total > room ? 'no' : '';
    var p = { s: size(total), a: mbw(held), b: mbw(total), n: what.n, r: what.r, v: what.v };
    var key = st === 'busy' ? T.k('Downloading: {a} of {b}; tap to stop')
            : st === 'kept' ? T.k('Kept, {s}; tap to let go')
            : st === 'some' ? T.k('Kept in part, {s}; tap to keep the rest')
            : what.n !== undefined ? T.k('Keep Paper {n} offline ({s})')
            : what.r !== undefined ? T.k('Keep Part {r} offline ({s})') : T.k('Keep the whole of {v} offline ({s})');
    if (st === 'some') p.s = size(held);
    T.attr(btn, 'title', key, p);
    T.attr(btn, 'aria-label', key, p);
  }
  function recShow(s) {
    var a = s && s.audio || null, have = s && s.have, on = online();
    var queue = (a && a.queue) || [], busy = a && a.busy, total = recBytes(a), nolist = false;
    Array.prototype.forEach.call(recBox.querySelectorAll('.recvoice'), function (det) {
      var key = det.dataset.key, v = (a && a.voices && a.voices[key]) || { kept: [], partial: {}, bytes: 0 },
          list = recIdx[key], queued = {};
      if (v.nolist) nolist = true;
      queue.forEach(function (q) { if (q.v === key) queued[q.n] = true; });
      var st = det.querySelector(':scope > summary .rst'), btn = det.querySelector(':scope > summary .keep');
      if (list) {
        var all = list.papers.map(function (x) { return x.n; }), vs = stateOf(all, v, queued);
        st.innerHTML = v.kept.length || Object.keys(v.partial).length
          ? T('offline:reckept', { n: v.kept.length, t: all.length, s: size(v.bytes) }) : '';
        setKeep(btn, vs, heldOf(all, v, busy, key, list.byN), list.bytes, { v: recName(key) });
        Array.prototype.forEach.call(det.querySelectorAll('.recpart'), function (pd) {
          var ns = all.filter(function (n) { return +pd.dataset.first <= n && n <= +pd.dataset.last; }),
              pb = ns.reduce(function (t, n) { return t + list.byN[n].bytes; }, 0), ps = stateOf(ns, v, queued),
              kept = ns.filter(function (n) { return v.kept.indexOf(n) >= 0; }).length;
          pd.querySelector(':scope > summary .rst').innerHTML = ps === 'none' ? ''
            : T('{a} of {b} papers', { a: kept, b: ns.length });
          setKeep(pd.querySelector(':scope > summary .keep'), ps, heldOf(ns, v, busy, key, list.byN), pb,
                  { r: ROMAN[+pd.dataset.part] || '' });
        });
        Array.prototype.forEach.call(det.querySelectorAll('.recrow'), function (row) {
          var n = +row.dataset.n, x = list.byN[n], rs = stateOf([n], v, queued), hb = heldOf([n], v, busy, key, list.byN);
          row.querySelector('.rmeta').innerHTML = rs === 'busy' || rs === 'some'
            ? T('{a} of {b}', { a: Math.round(hb / 1e6), b: mbw(x.bytes) }) : T(mbw(x.bytes));
          setKeep(row.querySelector('.keep'), rs, hb, x.bytes, { n: n });
        });
      } else {
        // Its list not come: its state alone, with no size to promise, and
        // the control greyed below.
        st.innerHTML = v.bytes ? T('kept, {s}', { s: size(v.bytes) }) : '';
        btn.dataset.st = Object.keys(queued).length ? 'busy' : v.kept.length || v.bytes ? 'some' : 'none';
        if (btn.dataset.icon !== btn.dataset.st) { btn.dataset.icon = btn.dataset.st; btn.innerHTML = ICONS[btn.dataset.st]; }
        btn.style.setProperty('--p', '0');
        ['title', 'data-ru-title', 'aria-label', 'data-ru-aria-label'].forEach(function (a) { btn.removeAttribute(a); });
      }
      // Greyed where nothing can be done: no worker's word yet, no list yet,
      // offline for what is not kept, a list the copy lacks (nolist).
      Array.prototype.forEach.call(det.querySelectorAll('.keep'), function (b) {
        b.disabled = !s || !list || v.nolist || (!on && (b.dataset.st === 'none' || b.dataset.st === 'some'));
      });
    });
    recBox.querySelector('.recstate').innerHTML = total && room !== null ? T('offline:rechead', { s: size(total), r: size(room) })
      : total ? T('kept, {s}', { s: size(total) }) : room !== null ? T('Room for about {s} in this browser.', { s: size(room) }) : '';
    recBox.querySelector('.going').hidden = !queue.length;
    hold(!!queue.length && !(a && a.error));
    var why = recBox.querySelector('.why');
    why.innerHTML = a && a.error ? T('The download stopped: {e}.', { e: a.words || T.same(a.error) }) +
                      (on ? ' <button type="button" class="recagain"><span>' + T('Try again') + '</span></button>' : '')
                  : !on ? T('offline:recoffline') : nolist ? T('offline:nolist') : !have ? T('offline:recwith') : '';
    why.hidden = !why.innerHTML;
    document.dispatchEvent(new CustomEvent('ub:audio', { detail: a }));
    pump(s);
  }
  // The next file asked for while the queue is not empty, nothing runs, and
  // the page is online; the reply, shown, asks for the next.  Not after a file
  // that failed, until Try again (`again`) or the browser is online again: a
  // full phone, a 404 or a damaged file was fetched again at once, for ever,
  // up to 27 MB a time, the screen held on (review of 2026-11-09).
  function pump(s, again) {
    var a = s && s.audio;
    if (!a || !a.queue.length || a.busy || s.busy || !online() || pumping || (a.error && !again)) return;
    pumping = true;
    ask('keep').then(function (r) { pumping = false; show(r); }, function () { pumping = false; });
  }
  // A recording asked for, stopped or let go: a voice and its papers.  With no
  // copy kept, the copy comes first, as a translation's tick brings it.  A
  // let-go always asks first, a paper's too: a tap deleted a paper unwarned on
  // the first evening (Tigran, 2026-11-04).
  function recAct(st, key, ns) {
    var have = last && last.have;
    if (st === 'busy') return ask('stop', { voice: key, papers: ns }).then(show);
    if (st === 'kept') {
      var list = recIdx[key], b = ns.reduce(function (t, n) { return t + (list && list.byN[n] ? list.byN[n].bytes : 0); }, 0);
      if (!window.confirm(T.text('offline:recdrop', { n: ns.length, v: recName(key), s: size(b) }))) return Promise.resolve();
      return ask('unkeep', { voice: key, papers: ns }).then(show);
    }
    persist(true);
    if (!have) return Promise.resolve(on(null, { voice: key, papers: ns }));
    return ask('keep', { voice: key, papers: ns }).then(function (r) { show(r); estimate(); });
  }
  window.ubOfflineUI.rec = function (st, key, n) { return ensure(key).then(function () { return recAct(st, key, [n]); }); };
  recBox.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button');
    if (!b) return;
    if (b.classList.contains('recagain')) { pumping = false; pump(last, true); return; }
    if (!b.classList.contains('keep')) return;
    ev.preventDefault();
    ev.stopPropagation();                        // not the fold's
    if (b.disabled) return;
    var det = b.closest('.recvoice'), key = det.dataset.key, row = b.closest('.recrow'), part = b.closest('.recpart');
    ensure(key).then(function (list) {
      var ns = row ? [+row.dataset.n]
             : list.papers.map(function (x) { return x.n; }).filter(function (n) {
                 return !part || (+part.dataset.first <= n && n <= +part.dataset.last); });
      return recAct(b.dataset.st, key, ns);
    });
  });
  // A voice opened draws its parts.
  recBox.addEventListener('toggle', function (ev) {
    var det = ev.target;
    if (det.classList && det.classList.contains('recvoice') && det.open) ensure(det.dataset.key).catch(function () {});
  }, true);
  // How much room this browser has, by its own estimate, advisory: Safari's
  // grows as it is asked.  A row larger than it is drawn faint, not disabled;
  // the worker's refused put is the word that counts.
  function estimate() {
    if (!navigator.storage || !navigator.storage.estimate) return;
    navigator.storage.estimate().then(function (e) {
      room = Math.max(0, (e.quota || 0) - (e.usage || 0));
      if (last) recShow(last);
    }, function () {});
  }
  estimate();
  // The screen stays on while the recordings download: a phone that locks it
  // stops the page, and with it the pump (as listen.js holds one for speech).
  var lock = null;
  function hold(on) {
    if (on && !lock && navigator.wakeLock && document.visibilityState === 'visible') {
      var p = lock = navigator.wakeLock.request('screen');
      p.then(function (l) { l.addEventListener('release', function () { if (lock === p) lock = null; }); },
             function () { if (lock === p) lock = null; });
    } else if (!on && lock) {
      var q = lock;
      lock = null;
      q.then(function (l) { l.release(); }, function () {});
    }
  }

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
  // worker, the manifest is asked for again, for the sizes and the copy.
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
  // What's new, asked for from the ? before this had loaded (ub.js).
  if (window.ubNewsDue) { window.ubNewsDue = false; openNews(); }
})();
