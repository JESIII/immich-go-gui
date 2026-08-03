#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENDOR_DIR="$ROOT_DIR/static/vendor"

mkdir -p "$VENDOR_DIR"

echo "Fetching htmx.min.js..."
curl -sSL "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" -o "$VENDOR_DIR/htmx.min.js"

echo "Fetching sse.js..."
curl -sSL "https://unpkg.com/htmx-ext-sse@2.2.2/sse.js" -o "$VENDOR_DIR/sse.js"

echo "Vendor scripts fetched into static/vendor/ successfully."
