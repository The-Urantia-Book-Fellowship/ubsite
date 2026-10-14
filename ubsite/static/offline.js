// Read offline, the page's side: the switch in Settings, what it says about
// the copy, the line under the header when the copy is stale, and the offer
// to install the site as an app.  ub.js loads this when Settings opens, or at
// once on a page the worker controls.  The worker (static/sw.js) does the
// work, and answers {cmd} on a message port with its state:
//
//   have    the copy kept: {build, made, text, index, bytes, raw}, or null
//   latest  the site's, when it is another: {made, fetch, full, ...}, or null
//   busy    {done, total} in bytes while downloading
//   error   why the last download stopped
//
// The switch is the registration: on, the worker is registered and fetches
// the copy; off, it removes the copy and is unregistered.
(function () {
  var box = document.querySelector('fieldset.offline');
  if (!box || !('serviceWorker' in navigator) || !window.isSecureContext || window.ubOfflineUI) return;
  window.ubOfflineUI = true;
  var sw = navigator.serviceWorker, input = box.querySelector('input[name="offline"]'),
      line = box.querySelector('.state'), inst = box.querySelector('.install');
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
                'October', 'November', 'December'];
  box.hidden = false;

  function mb(n) { return Math.max(0.1, n / 1e6).toFixed(1) + ' MB'; }
  function day(iso) {
    var d = new Date(iso);
    return d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()];
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
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
  function later() { try { return localStorage.getItem('ub_offline_later'); } catch (e) { return null; } }

  // The line under the header: the copy is stale, or being updated.
  var note = null;
  function noted(html) {
    if (!html) { if (note) { note.remove(); note = null; } return; }
    if (!note) {
      note = document.createElement('div');
      note.className = 'offnote';
      note.setAttribute('role', 'status');
      var top = document.querySelector('header.top');
      top.parentNode.insertBefore(note, top.nextSibling);
    }
    note.innerHTML = '<p>' + html + '</p>';
  }

  var last = null;
  function show(s) {
    last = s;
    watch(s);
    if (!s || s.removed) {
      input.checked = false;
      notice(null);
      return sized();
    }
    input.checked = true;
    var have = s.have, up = s.latest, err = s.error ? esc(s.error) : '';
    if (s.busy) {
      line.textContent = (have ? 'Updating' : 'Downloading') + (s.busy.total
        ? ': ' + mb(s.busy.done) + ' of ' + mb(s.busy.total) : '…');
    } else if (!have) {
      line.innerHTML = (err ? 'The download stopped: ' + err + '.' : 'The download did not finish.') +
                       ' <button type="button" class="get">Try again</button>';
    } else if (up) {
      line.innerHTML = 'Kept as the site was on ' + day(have.made) + ', which has changed since. ' +
                       '<button type="button" class="get">Update now (' + mb(up.fetch) + ')</button>' +
                       (err ? '<br>The last update stopped: ' + err + '.' : '');
    } else {
      line.textContent = 'Up to date: the text of ' + day(have.text.date) + ' and the index of ' +
                         day(have.index.date) + ', ' + mb(have.raw) + ' in this browser.';
    }
    notice(s);
  }
  // The line under the header, while a copy is kept: stale, an update going
  // on, how it ended.  "Up to date" stands for a few seconds; an update that
  // stopped says why, with a button to try again.
  var updating = false, ended = null;
  function notice(s) {
    var have = s && s.have, up = s && s.latest;
    if (!have) return noted(null);
    if (s.busy) {
      updating = true;
      return noted('Updating the offline copy' + (s.busy.total
        ? ': ' + mb(s.busy.done) + ' of ' + mb(s.busy.total) : '…'));
    }
    var just = updating;
    updating = false;
    if (just) {
      clearTimeout(ended);
      ended = null;
      if (!up) {
        noted('The offline copy is up to date.');
        ended = setTimeout(function () { ended = null; notice(last); }, 5000);
        return;
      }
    }
    if (ended) return;
    if (up && navigator.onLine !== false && (just || later() !== up.build))
      noted((s.error ? 'The update stopped: ' + esc(s.error) + '. '
                     : 'Your offline copy is from ' + day(have.made) + ', and the site has changed since. ') +
            '<button type="button" class="get">' + (s.error ? 'Try again' : 'Update it (' + mb(up.fetch) + ')') +
            '</button> <button type="button" class="later">Later</button>');
    else noted(null);
  }
  // While a download goes on, the worker says how far it is.  A worker can be
  // stopped by the browser mid-way and say nothing more; if it is quiet for a
  // while, ask it, and show what it says: the copy before, and the button.
  var quiet = null;
  function watch(s) {
    clearTimeout(quiet);
    if (s && s.busy) quiet = setTimeout(function () { ask('state').then(show); }, 20000);
  }
  // Before it is on: what it would cost.
  function sized() {
    line.textContent = '';
    fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (m) {
      if (!input.checked) line.textContent = 'About ' + mb(m.bytes) + ' to download, kept in this browser.';
    }, function () {
      if (!input.checked) line.textContent = navigator.onLine === false ? 'It can be turned on only online.'
                                                                        : 'This site has no offline copy yet.';
    });
  }

  function get() {
    return ask('get').then(show);
  }
  function on() {
    line.textContent = 'Starting…';
    sw.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then(function () {
      if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
      return get();
    }).catch(function (e) {
      input.checked = false;
      line.textContent = 'This browser would not keep it: ' + (e && e.message || e);
    });
  }
  function off() {
    if (!window.confirm('Remove the offline copy from this browser?')) { input.checked = true; return; }
    ask('remove').then(function () {
      return sw.getRegistration('/');
    }).then(function (reg) { return reg && reg.unregister(); }).then(function () { show(null); });
  }
  input.addEventListener('change', function () { if (input.checked) on(); else off(); });
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.offnote button, fieldset.offline button');
    if (!b) return;
    if (b.classList.contains('get')) {
      // Said here at once, in both places, not left to the worker: the button
      // goes, so a second tap cannot look as if it did nothing.
      show(Object.assign({}, last || {}, { busy: { done: 0, total: 0 }, removed: false }));
      get();
    }
    else if (b.classList.contains('later')) {
      try { localStorage.setItem('ub_offline_later', last && last.latest ? last.latest.build : ''); } catch (e) {}
      noted(null);
    } else if (b.classList.contains('app') && window.ubInstall) {
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
    else if (window.ubInstall) inst.innerHTML = '<button type="button" class="app">Install as an app</button> ' +
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
    input.checked = true;
    return ask('check').then(show);
  });
  // Opening Settings asks the site afresh: a 304 of a few hundred bytes.
  document.querySelector('.gear').addEventListener('click', function () {
    if (input.checked) ask('check', { force: true }).then(show);
  });
})();
