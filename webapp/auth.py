"""Minimal auth + session + CSRF for the web console.

Credentials via env: IGG_WEB_USER / IGG_WEB_PASSWORD.
If unset, auth is disabled (dev mode) and a warning is shown.
"""

from __future__ import annotations

import os
import secrets
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

AUTH_COOKIE = "igg_auth"
SESSION_COOKIE = "igg_sid"
CSRF_COOKIE = "igg_csrf"
SESSIONS: dict[str, dict[str, Any]] = {}

OPEN_PATHS = {"/login", "/healthz"}
STATIC_PREFIX = "/static/"


def auth_enabled() -> bool:
    user = os.environ.get("IGG_WEB_USER", "")
    pwd = os.environ.get("IGG_WEB_PASSWORD", "")
    return bool(user and pwd)


def check_login(username: str, password: str) -> bool:
    user = os.environ.get("IGG_WEB_USER", "")
    pwd = os.environ.get("IGG_WEB_PASSWORD", "")
    if not (user and pwd):
        return False
    return secrets.compare_digest(username, user) and secrets.compare_digest(
        password, pwd
    )


def get_session(request: Request) -> dict[str, Any]:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid or sid not in SESSIONS:
        sid = uuid.uuid4().hex
        SESSIONS[sid] = {}
    request.state.new_sid = sid
    return SESSIONS[sid]


def drop_session(sid: str) -> None:
    SESSIONS.pop(sid, None)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path
        if path in OPEN_PATHS or path.startswith(STATIC_PREFIX):
            return await call_next(request)
        if auth_enabled() and request.cookies.get(AUTH_COOKIE) != "1":
            if request.headers.get("HX-Request"):
                resp = RedirectResponse("/login", status_code=303)
                resp.headers["HX-Redirect"] = "/login"
                return resp
            return RedirectResponse("/login", status_code=303)
        if request.method == "POST":
            csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
            csrf_sent = request.headers.get("X-CSRF", "")
            if (
                csrf_cookie
                and csrf_sent
                and not secrets.compare_digest(csrf_sent, csrf_cookie)
            ):
                return PlainTextResponse("CSRF validation failed", status_code=403)
        return await call_next(request)
