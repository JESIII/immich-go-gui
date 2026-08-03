"""Immich-Go GUI — Web Console entrypoint.

Run locally:      uv run python web.py --port 8080
Run in Docker:    see Dockerfile / docker-compose.yml
"""

from __future__ import annotations

import argparse

import uvicorn

from webapp.app import create_app

app = create_app()

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Immich-Go GUI web console")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()
    uvicorn.run("web:app", host=args.host, port=args.port, reload=args.reload)
