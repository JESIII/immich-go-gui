/* --------------------------------------------------------------------------
   Immich-Go GUI — Web Console Client Script
   -------------------------------------------------------------------------- */

function currentThemePreference() {
  return document.documentElement.getAttribute('data-theme-preference') || 'dark';
}

function applyTheme(pref) {
  var effective = pref;
  if (pref === 'system') {
    effective = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
  }
  document.documentElement.setAttribute('data-theme', effective);
  document.documentElement.setAttribute('data-theme-preference', pref);
}

function toggleTheme() {
  var order = ['dark', 'light', 'system'];
  var cur = currentThemePreference();
  var idx = order.indexOf(cur);
  var next = order[(idx + 1) % order.length];
  applyTheme(next);

  fetch('/theme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'theme=' + encodeURIComponent(next)
  });
}

// Follow OS color-scheme changes while in "system" mode.
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function () {
  if (currentThemePreference() === 'system') applyTheme('system');
});

// Programmatic theme selection from the Appearance card (System/Light/Dark).
function setTheme(value) {
  applyTheme(value);
  fetch('/theme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'theme=' + encodeURIComponent(value)
  });
}

// Dismiss the first-run checklist (removes the card and persists in session).
function dismissChecklist() {
  var card = document.getElementById('first-run-checklist');
  if (card) card.remove();
  fetch('/checklist/dismiss', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: ''
  });
}

/* --------------------------------------------------------------------------
   Ambient connection chip (W-14): after debounced edits to the server URL or
   API key, silently test the connection and update the inline chip. Delegated
   input listener survives HTMX content swaps of the config page.
   -------------------------------------------------------------------------- */
function getConnEls() {
  return {
    server: document.getElementById('cfg_server'),
    key: document.getElementById('cfg_api_key'),
    chip: document.getElementById('conn-chip')
  };
}

function runConnectionTest() {
  var els = getConnEls();
  if (!els.server || !els.chip) return;
  var body = 'server=' + encodeURIComponent(els.server.value) +
             '&api_key=' + encodeURIComponent(els.key ? els.key.value : '');
  els.chip.className = 'conn-chip conn-chip-checking';
  els.chip.textContent = 'checking…';
  fetch('/config/test-connection-async', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body
  }).then(function (r) { return r.json(); }).then(function (data) {
    if (data.ok) {
      els.chip.className = 'conn-chip conn-chip-ok';
      els.chip.textContent = 'Connected' + (data.server_version ? ' · v' + data.server_version : '');
      els.chip.title = data.message || 'Connected';
    } else {
      els.chip.className = 'conn-chip conn-chip-err';
      els.chip.textContent = 'Unreachable';
      els.chip.title = data.message || 'Connection failed';
    }
  }).catch(function () {
    var e = getConnEls();
    if (e.chip) {
      e.chip.className = 'conn-chip conn-chip-err';
      e.chip.textContent = 'Error';
    }
  });
}

var connTimer = null;
document.addEventListener('input', function (evt) {
  var t = evt.target;
  if (t && (t.id === 'cfg_server' || t.id === 'cfg_api_key')) {
    clearTimeout(connTimer);
    connTimer = setTimeout(runConnectionTest, 1200);
  }
});

function maybeInitConnChip() {
  var els = getConnEls();
  if (els.server && els.server.value && els.chip && !els.chip.dataset.inited) {
    els.chip.dataset.inited = '1';
    runConnectionTest();
  }
}
document.addEventListener('DOMContentLoaded', maybeInitConnChip);
document.addEventListener('htmx:afterSettle', maybeInitConnChip);

/* --------------------------------------------------------------------------
   W-18: HTML5 drag & drop for path/paths fields. Browsers only expose file
   *names*, not server-side paths, so this is a path-string convenience --
   real server paths are typed/pasted. Visual feedback via .dnd-over.
   -------------------------------------------------------------------------- */
document.addEventListener('dragover', function (e) {
  var wrap = e.target && e.target.closest ? e.target.closest('.dnd-wrap.is-droppable') : null;
  if (wrap) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; wrap.classList.add('dnd-over'); }
});
document.addEventListener('dragleave', function (e) {
  var wrap = e.target && e.target.closest ? e.target.closest('.dnd-wrap') : null;
  if (wrap) wrap.classList.remove('dnd-over');
});
document.addEventListener('drop', function (e) {
  var wrap = e.target && e.target.closest ? e.target.closest('.dnd-wrap.is-droppable') : null;
  if (!wrap) return;
  e.preventDefault();
  wrap.classList.remove('dnd-over');
  var input = wrap.querySelector('input.droppable-field');
  if (input && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    var names = Array.prototype.map.call(e.dataTransfer.files, function (f) { return f.name; });
    input.value = names.length === 1 ? names[0] : names.join(', ');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
});

/* --------------------------------------------------------------------------
   W-19: live command ribbon. Debounced form edits rebuild the plan server-side
   and render masked, color-coded argv tokens + the warnings shelf.
   -------------------------------------------------------------------------- */
var ribbonTimer = null;
function updateLiveRibbon() {
  var ribbon = document.getElementById('live-ribbon');
  var form = document.getElementById('tab-form');
  if (!ribbon || !form || !ribbon.dataset.tab) return;
  var body = new URLSearchParams(new FormData(form));
  fetch('/tabs/' + ribbon.dataset.tab + '/live-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString()
  }).then(function (r) { return r.text(); }).then(function (html) {
    ribbon.innerHTML = html;
  }).catch(function () {});
}
document.addEventListener('input', function (evt) {
  var t = evt.target;
  if (t && t.closest && t.closest('#tab-form')) {
    markDirty(true);
    clearTimeout(ribbonTimer);
    ribbonTimer = setTimeout(updateLiveRibbon, 350);
  }
});
document.addEventListener('htmx:afterSettle', updateLiveRibbon);

/* --------------------------------------------------------------------------
   W-22: unsaved-changes (dirty) tracking for the profile-switch prompt.
   -------------------------------------------------------------------------- */
window._iggDirty = false;
function markDirty(d) { window._iggDirty = d; }
document.addEventListener('input', function (evt) {
  if (evt.target && evt.target.closest && !evt.target.closest('#modal-container')) markDirty(true);
});
document.addEventListener('change', function (evt) {
  if (evt.target && evt.target.closest && !evt.target.closest('#modal-container')) markDirty(true);
});

/* --------------------------------------------------------------------------
   W-27: flag finder + presets (proposal P4).
   -------------------------------------------------------------------------- */
function updateAdvFilter() {
  var input = document.getElementById('adv-filter');
  var rows = document.querySelectorAll('#tab-form .adv-row');
  if (!input || !rows.length) return;
  var q = input.value.toLowerCase();
  var shown = 0;
  rows.forEach(function (row) {
    var hay = (row.getAttribute('data-key') || '') + ' ' + (row.textContent || '').toLowerCase();
    var match = !q || hay.indexOf(q) !== -1;
    row.style.display = match ? '' : 'none';
    if (match) shown++;
  });
  var count = document.getElementById('adv-count');
  if (count) count.textContent = shown + ' / ' + rows.length + ' shown';
}

// Apply a preset: flip the matching advanced rows on and set their values.
function applyPreset(flags) {
  Object.keys(flags || {}).forEach(function (key) {
    var row = document.querySelector('#tab-form .adv-row[data-key="' + key + '"]');
    if (!row) return;
    var en = row.querySelector('input[name="adv_' + key + '_en"]');
    var val = row.querySelector('[name="adv_' + key + '_val"]');
    if (en && !en.checked) {
      en.checked = true;
      var wrap = row.querySelector('.adv-input-wrap');
      if (wrap) wrap.classList.remove('disabled');
    }
    if (val) {
      var desired = String(flags[key]);
      if (val.tagName === 'SELECT') {
        if (val.querySelector('option[value="' + desired + '"]')) { val.value = desired; }
      } else {
        val.value = desired;
      }
      val.dispatchEvent(new Event('change', { bubbles: true }));
      val.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
  window._iggDirty = true;
}

document.addEventListener('input', function (evt) {
  if (evt.target && evt.target.id === 'adv-filter') updateAdvFilter();
});
document.addEventListener('htmx:afterSettle', updateAdvFilter);

/* --------------------------------------------------------------------------
   W-29: keyboard layer (proposal P9).
   -------------------------------------------------------------------------- */
function isTypingTarget(el) {
  var tag = el && el.tagName ? el.tagName.toLowerCase() : '';
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
}

function openTabJumper() {
  var jumper = document.getElementById('tab-jumper');
  var list = document.getElementById('tab-jumper-list');
  if (!jumper || !list) return;
  jumper.hidden = false;
  // Build from the sidebar nav items so it stays in sync with REGISTRY.
  list.innerHTML = '';
  document.querySelectorAll('.nav-item').forEach(function (el) {
    var href = el.getAttribute('hx-get') || '';
    if (href.indexOf('/tab/') !== 0) return;
    var label = (el.textContent || '').trim();
    var item = document.createElement('a');
    item.href = href;
    item.className = 'tab-jumper-item';
    item.textContent = label;
    item.setAttribute('hx-get', href);
    item.setAttribute('hx-target', '#content');
    item.setAttribute('hx-push-url', 'true');
    item.addEventListener('click', function (e) { e.preventDefault(); jumper.hidden = true; });
    list.appendChild(item);
  });
  var input = document.getElementById('tab-jumper-input');
  input.value = '';
  filterTabJumper();
  input.focus();
}

function filterTabJumper() {
  var list = document.getElementById('tab-jumper-list');
  var input = document.getElementById('tab-jumper-input');
  if (!list) return;
  var q = (input.value || '').toLowerCase();
  list.querySelectorAll('.tab-jumper-item').forEach(function (el) {
    el.style.display = !q || el.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
  });
}

document.addEventListener('keydown', function (evt) {
  var mod = evt.ctrlKey || evt.metaKey;
  if (mod && evt.key === 'Enter') {
    var btn = evt.shiftKey ? document.getElementById('btn-dry') : document.getElementById('btn-execute');
    if (btn && !btn.disabled) { evt.preventDefault(); btn.click(); }
    return;
  }
  if (mod && evt.key.toLowerCase() === 'k') {
    evt.preventDefault();
    openTabJumper();
    return;
  }
  if (mod && evt.key.toLowerCase() === 's') {
    evt.preventDefault();
    var form = document.querySelector('#content form[hx-post="/config/save"], #content form[hx-post="/config/save-server"]');
    if (form) form.requestSubmit();
    return;
  }
  if (evt.key === '?' && !isTypingTarget(evt.target)) {
    evt.preventDefault();
    var overlay = document.getElementById('shortcuts-overlay');
    if (overlay) overlay.hidden = !overlay.hidden;
    return;
  }
  if (evt.key === 'Escape') {
    var jumper = document.getElementById('tab-jumper');
    var shortcuts = document.getElementById('shortcuts-overlay');
    if (jumper && !jumper.hidden) jumper.hidden = true;
    if (shortcuts && !shortcuts.hidden) shortcuts.hidden = true;
    return;
  }
});

document.addEventListener('input', function (evt) {
  if (evt.target && evt.target.id === 'tab-jumper-input') filterTabJumper();
});



function clearTerminalLogs() {
  const container = document.getElementById('terminal-logs');
  if (container) {
    container.innerHTML = '';
  }
}

// Auto-scroll terminal logs on new SSE line messages
document.addEventListener('htmx:sseMessage', function(evt) {
  const toggle = document.getElementById('auto-scroll-toggle');
  const container = document.getElementById('terminal-logs');

  if (container && toggle && toggle.checked) {
    container.scrollTop = container.scrollHeight;
  }
});

// Update chip on SSE done event
document.addEventListener('htmx:sseBeforeMessage', function(evt) {
  if (evt.detail.type === 'done') {
    try {
      const data = JSON.parse(evt.detail.data);
      const chipContainer = document.getElementById('run-status-chip');
      if (chipContainer && data.chip) {
        chipContainer.innerHTML = data.chip;
      }
    } catch(e) {}
  }
});

// Sync active navigation item highlighting with current URL path
function updateActiveNav() {
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(function(el) {
    const targetPath = el.getAttribute('hx-get');
    if (targetPath && (targetPath === currentPath || (currentPath === '/' && targetPath === '/overview'))) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
}

document.addEventListener('htmx:afterSettle', updateActiveNav);
window.addEventListener('popstate', updateActiveNav);
document.addEventListener('DOMContentLoaded', updateActiveNav);

// Auto-dismiss toasts after 5s
document.addEventListener('htmx:afterSettle', function(evt) {
  const toasts = document.querySelectorAll('.toast:not([data-timer])');
  toasts.forEach(function(t) {
    t.setAttribute('data-timer', 'true');
    setTimeout(function() {
      if (t.parentNode) {
        t.style.opacity = '0';
        t.style.transition = 'opacity 0.3s ease';
        setTimeout(function() { if (t.parentNode) t.remove(); }, 300);
      }
    }, 5000);
  });
});
