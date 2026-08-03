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
