# Immich-Go GUI — Web Console

The **Web Console** is a production-ready, HTMX-powered web interface for Immich-Go GUI that sits directly on top of the Qt-free `core/` package. It provides complete feature parity with the desktop application without importing any Qt modules or GUI widgets.

---

## 🌟 Key Architecture & Features

- **Qt-Free Core Reuse**: Imports strictly from `core/` (`flag_registry`, `command_builder`, `binary_manager`, `process_tracker`, `config_manager`, `profile_manager`). Adding flags or schema updates to `core/flags.toml` automatically renders them in the web UI.
- **Managed Subprocess & Live SSE Log Terminal**: Runs `immich-go` in managed background processes and streams stdout/stderr live to an in-app monospaced terminal panel over Server-Sent Events (`hx-ext="sse"`). Includes stop triggers, exit-code chips, auto-scroll, and run history.
- **Multi-Profile Support**: Complete profile creation, switching, duplication, renaming, and deletion.
- **Diagnostics Export**: Export redacted diagnostics ZIP archives containing system summaries, masked configuration TOML, profile indices, and log tails.
- **Security & Authentication**: Mandatory user authentication via environment variables (`IGG_WEB_USER` and `IGG_WEB_PASSWORD`), session cookie management, and CSRF protection on POST operations.

---

## 🚀 Quick Start (Local)

### 1. Install Web Dependencies

```bash
export PATH=$HOME/.local/bin:$PATH
uv sync --extra web
```

### 2. Fetch Vendor Scripts

```bash
./scripts/fetch_vendor.sh
```

### 3. Launch Web Server

```bash
uv run python web.py --port 8080
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.

---

## 🔒 Authentication Configuration

Authentication is enabled by setting `IGG_WEB_USER` and `IGG_WEB_PASSWORD`:

```bash
export IGG_WEB_USER="admin"
export IGG_WEB_PASSWORD="SecurePassword123!"
uv run python web.py --port 8080
```

When unset, authentication is disabled (development mode).

---

## 🐳 Docker Deployment

### Run with Docker Compose

```bash
docker compose up -d
```

### Build Docker Image Manually

```bash
docker build -t immich-go-web .
docker run -d -p 8080:8080 -e IGG_WEB_USER=admin -e IGG_WEB_PASSWORD=secret -v $(pwd)/config_data:/config immich-go-web
```

---

## 🌐 Reverse Proxy Configuration

When running behind reverse proxies, Server-Sent Events (SSE) log streaming requires disabling proxy response buffering.

### Nginx

```nginx
server {
    listen 80;
    server_name immich-web.local;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Disable buffering for SSE live log stream
    location ~ ^/runs/.+/stream$ {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

### Caddy

```caddyfile
immich-web.local {
    reverse_proxy 127.0.0.1:8080 {
        flush_interval -1
    }
}
```

---

## 🧪 Testing

Run the web console test suite:

```bash
uv run pytest tests/test_web.py
```

---

## ✨ Feature Parity with the Desktop GUI

The web console now matches the desktop app across all 11 workflows plus the config surface.
Highlights added for parity:

- **Enum dropdowns** render as `<select>`s from `flags.toml` with the documented default preselected.
- **All 11 workflows** are reachable from the sidebar, including *Upload immich* and *Archive immich*.
- **Advanced bool flags** can emit `--flag=false` (true/false value control).
- **Inline per-field validation** — errors appear under the offending control *and* in the modal summary.
- **Target-server banner** on every server-required workflow, with the source server shown for immich→immich jobs.
- **Status pill** now also reflects the last connection test result (green `Connected · vX`/red `Connection issue`).
- **Config tab** gains: ambient connection chip with debounced auto-test, secret-status line, an *Application*
  card (GUI version, update check, release links), an *Appearance* card (theme selector), a **first-run checklist**,
  plus **Reload Config**, **Download Config** (redacted), and **View Log Tail** actions (web equivalents of the
  desktop's open-config/log-folder menu items).
- **Confirm modal** shows flag provenance ("Flag Sources") and a **Copy Command** button.
- **Live command ribbon**: while editing a workflow, a debounced server-side preview renders the evolving,
  masked, color-coded argv above the action buttons, along with a persistent warnings shelf.
- **Menu-bar equivalence**: About modal (version + CLI target + GitHub links), update toasts carry an
  "Open ↗" release link, and `<F>` menu items map to config save/reload/reset/export surfaces.
- **Efficiency layer**: advanced-flag *finder* with "n of N shown" counter, workflow **preset chips**
  (Fast Scan, Favorites Only, Gentle, Debug, …), **Rebuild** action on the run-history table that rehydrates
  a previous run's non-secret form state, and a **keyboard layer**.

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl`+`Enter` | Preview & execute the current workflow |
| `Ctrl`+`Shift`+`Enter` | Dry-run preview |
| `Ctrl`+`K` | Jump to a workflow tab (type to filter) |
| `?` | Toggle the shortcuts overlay |
| `Esc` | Close overlays |

### Intentional web adjustments (not 1:1 with desktop)

1. **Execution model** — the browser runs a managed subprocess and streams logs over SSE instead of opening
   an external terminal (in-app terminal, stop button, run history).
2. **Secret backend** — a container has no OS keyring. The web console probes for one, defaults to the
   0600 `secrets.toml` file (or `IMMICH_GO_GUI_API_KEY` / `IMMICH_GO_GUI_ADMIN_API_KEY` env vars), and shows
   a notice when the keyring is unavailable.
3. **Secrets never in HTML** — API keys are removed from workflow forms entirely (previews re-read them from
   the server session) and secret source fields render as masked `password` inputs.
4. **Native file pickers** — replaced with text inputs plus HTML5 drag-and-drop for path fields (browsers only
   expose file *names*, so server-side paths are typed/pasted).
5. **Menu bar** — there is no browser menu bar; every menu item maps to a web surface (see above).
6. **System theme** — implemented via `prefers-color-scheme` (stored choice: dark / light / system).

### Run history & persistence

Completed runs are recorded to `run_history.json` in the config directory (secrets excluded) so the Overview
**Rebuild** action survives server restarts. Secret-bearing fields are stripped before writing.
