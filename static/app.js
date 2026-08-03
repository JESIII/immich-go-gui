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
