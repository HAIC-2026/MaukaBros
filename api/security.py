"""Security controls for the web service. See SECURITY.md.

- ChatLimiter: per-visitor rate limits, a cap on simultaneous questions and a daily question cap.
- SpendBudget: a daily and a per-question spending cap for the AI service, in US dollars,
  estimated from the token counts each API response reports.
- sign_answer / verify_answer: an HMAC on each answer, so a browser cannot invent earlier
  "assistant" turns to steer the model.
- ChatBodyLimit: refuses oversized chat requests while the body is being read, including requests
  sent in chunks without a Content-Length header.
- SecurityHeaders: Content Security Policy and other response headers on every page.

Settings (environment / .env, all optional):
  CHAT_PER_MINUTE      questions per visitor per minute    (default 10)
  CHAT_PER_HOUR        questions per visitor per hour      (default 60)
  CHAT_MAX_CONCURRENT  questions answered at the same time (default 4)
  CHAT_DAILY_LIMIT     questions per day, all visitors     (default 500)
  CHAT_DAILY_USD       AI spending per day, all visitors   (default 5.00)
  CHAT_QUESTION_USD    AI spending for one question        (default 0.50)
  CHAT_PRICE_INPUT / CHAT_PRICE_OUTPUT / CHAT_PRICE_CACHE_READ / CHAT_PRICE_CACHE_WRITE
                       US dollars per million tokens (defaults: Claude Opus 5.5 list prices,
                       4.00 / 20.00 / 0.20 / 5.00; update them if the model or prices change)
  CHAT_SIGNING_KEY     secret for answer signatures; if unset, one is generated once and kept in
                       data/chat_signing.key so every server process and restart shares it
  TRUST_PROXY          "1" only behind a reverse proxy that sets X-Forwarded-For and the scheme
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("district_insight.security")

ROOT = Path(__file__).resolve().parent.parent

# Request size limits (also enforced by the Pydantic model in main.py).
MAX_QUESTION_CHARS = 1000      # one user question
MAX_ANSWER_CHARS = 20000       # an earlier assistant answer sent back as context
MAX_HISTORY_MESSAGES = 12      # user + assistant turns sent back
MAX_BODY_BYTES = 64 * 1024     # whole /api/chat request body


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, default)))
    except ValueError:
        return default


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class LimitExceeded(Exception):
    def __init__(self, status: int, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.status, self.message, self.retry_after = status, message, retry_after


# --- Question limits ----------------------------------------------------------------------------
class ChatLimiter:
    """Thread-safe: FastAPI runs the (sync) chat endpoint in a thread pool."""

    def __init__(self):
        self.per_minute = _int_env("CHAT_PER_MINUTE", 10)
        self.per_hour = _int_env("CHAT_PER_HOUR", 60)
        self.daily = _int_env("CHAT_DAILY_LIMIT", 500)
        self._slots = threading.BoundedSemaphore(_int_env("CHAT_MAX_CONCURRENT", 4))
        self._lock = threading.Lock()
        self._hits: dict[str, deque] = {}
        self._day = ""
        self._day_count = 0

    def acquire(self, visitor: str) -> None:
        """Count one question for this visitor or raise LimitExceeded. Call release() after."""
        now = time.monotonic()
        with self._lock:
            today = _today()
            if today != self._day:
                self._day, self._day_count = today, 0
            if self._day_count >= self.daily:
                raise LimitExceeded(503, "The assistant has reached its daily limit. Please try again tomorrow; "
                                         "every figure is still available on the district pages.")
            hits = self._hits.setdefault(visitor, deque())
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if sum(1 for t in hits if now - t < 60) >= self.per_minute:
                raise LimitExceeded(429, "You have asked several questions in a short time. Please wait a minute and try again.", 60)
            if len(hits) >= self.per_hour:
                raise LimitExceeded(429, "You have reached the hourly question limit. Please try again later.",
                                    int(3600 - (now - hits[0])) + 1)
            if not self._slots.acquire(blocking=False):
                raise LimitExceeded(503, "The assistant is busy answering other questions. Please try again in a moment.", 10)
            hits.append(now)
            self._day_count += 1
            if len(self._hits) > 10000:  # drop idle visitors so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 3600]:
                    del self._hits[k]

    def release(self) -> None:
        self._slots.release()


def visitor_id(client_host: str | None, forwarded_for: str | None) -> str:
    """Who is asking, for the per-visitor limits.

    X-Forwarded-For is trusted only when TRUST_PROXY=1, because any browser can set it. IPv6
    addresses are grouped by /64 network, since one connection usually controls a whole /64 and
    could otherwise rotate addresses to dodge the limits."""
    host = client_host or "unknown"
    if os.getenv("TRUST_PROXY") == "1" and forwarded_for:
        host = forwarded_for.split(",")[0].strip()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if ip.version == 6:
        if ip.ipv4_mapped:  # ::ffff:198.51.100.7 is an IPv4 visitor
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


# --- Spending caps ------------------------------------------------------------------------------
class SpendBudget:
    """Estimated AI spending, from the token counts in each response's `usage`.

    A daily cap for all visitors and a cap for one question. The assistant checks it before every
    model call, so a question stops cleanly when either cap is reached."""

    def __init__(self):
        self.daily_usd = _float_env("CHAT_DAILY_USD", 5.00)
        self.question_usd = _float_env("CHAT_QUESTION_USD", 0.50)
        self.prices = {  # US dollars per million tokens
            "input": _float_env("CHAT_PRICE_INPUT", 4.00),
            "output": _float_env("CHAT_PRICE_OUTPUT", 20.00),
            "cache_read": _float_env("CHAT_PRICE_CACHE_READ", 0.20),
            "cache_write": _float_env("CHAT_PRICE_CACHE_WRITE", 5.00),
        }
        self._lock = threading.Lock()
        self._day = ""
        self._spent = 0.0

    def cost(self, usage) -> float:
        """Estimated cost of one API response from its usage block."""
        n = lambda field: getattr(usage, field, 0) or 0  # noqa: E731
        return (n("input_tokens") * self.prices["input"] + n("output_tokens") * self.prices["output"]
                + n("cache_read_input_tokens") * self.prices["cache_read"]
                + n("cache_creation_input_tokens") * self.prices["cache_write"]) / 1_000_000

    def _roll(self) -> None:
        if _today() != self._day:
            self._day, self._spent = _today(), 0.0

    def check_day(self) -> None:
        with self._lock:
            self._roll()
            if self._spent >= self.daily_usd:
                raise LimitExceeded(503, "The assistant has reached its daily spending limit. Please try again tomorrow; "
                                         "every figure is still available on the district pages.")

    def question(self) -> "QuestionSpend":
        return QuestionSpend(self)

    def add(self, amount: float) -> None:
        with self._lock:
            self._roll()
            self._spent += amount

    @property
    def spent_today(self) -> float:
        with self._lock:
            self._roll()
            return self._spent


class QuestionSpend:
    """Spending for one question. agent.answer() calls allow() before each model call and
    record() after it."""

    def __init__(self, budget: SpendBudget):
        self.budget, self.spent = budget, 0.0

    def allow(self) -> bool:
        with self.budget._lock:
            self.budget._roll()
            day_left = self.budget._spent < self.budget.daily_usd
        return day_left and self.spent < self.budget.question_usd

    def record(self, usage) -> None:
        c = self.budget.cost(usage)
        self.spent += c
        self.budget.add(c)


# --- Answer signatures --------------------------------------------------------------------------
def _signing_key() -> bytes:
    """CHAT_SIGNING_KEY, or a key generated once and kept in data/ (not in git), so every server
    process and every restart signs and checks with the same key."""
    if os.getenv("CHAT_SIGNING_KEY"):
        return os.environ["CHAT_SIGNING_KEY"].encode()
    path = ROOT / "data" / "chat_signing.key"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # only one process creates it
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    except OSError:
        log.warning("Could not store a signing key in %s; using a key for this process only.", path)
        return secrets.token_hex(32).encode()
    for _ in range(50):  # another process may still be writing it
        key = path.read_text().strip()
        if key:
            return key.encode()
        time.sleep(0.01)
    raise RuntimeError(f"{path} is empty; delete it and restart.")


_KEY = _signing_key()


def sign_answer(text: str) -> str:
    return hmac.new(_KEY, b"district-insight-answer-v1\x00" + text.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_answer(text: str, signature: str | None) -> bool:
    return bool(signature) and hmac.compare_digest(sign_answer(text), signature)


# --- Request body cap (ASGI middleware) ---------------------------------------------------------
class ChatBodyLimit:
    """Reads the /api/chat body itself, stopping at max_bytes, so a huge request (with or without
    a Content-Length header) is refused before it fills memory. Other paths pass straight through."""

    def __init__(self, app, path: str = "/api/chat", max_bytes: int = MAX_BODY_BYTES):
        self.app, self.path, self.max_bytes = app, path, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != self.path:
            return await self.app(scope, receive, send)
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            return await self._too_large(send)
        body, more = b"", True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > self.max_bytes:
                return await self._too_large(send)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _too_large(send):
        payload = json.dumps({"detail": "The request is too large."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(payload)).encode()),
                                (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": payload})


# --- Security headers (ASGI middleware) ---------------------------------------------------------
# Scripts only from this site and Esri's ArcGIS CDN (the map library); styles and fonts also from
# jsdelivr (IBM Plex Sans). Inline styles are allowed because the map library sets them; inline
# scripts are not. The page cannot be framed by another site.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://js.arcgis.com",
    "style-src 'self' 'unsafe-inline' https://js.arcgis.com https://cdn.jsdelivr.net",
    "font-src 'self' data: https://cdn.jsdelivr.net https://js.arcgis.com",
    "img-src 'self' data: blob: https://js.arcgis.com",
    "connect-src 'self' https://js.arcgis.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
# The interactive API docs (Swagger UI) load their own inline script; they get a looser policy.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        https = scope.get("scheme") == "https" or (
            os.getenv("TRUST_PROXY") == "1"
            and dict(scope.get("headers") or []).get(b"x-forwarded-proto") == b"https")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"x-frame-options": b"DENY",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                    b"cross-origin-opener-policy": b"same-origin",
                }
                if not path.startswith(DOCS_PATHS):
                    extra[b"content-security-policy"] = CSP.encode()
                if https:
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                names = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in extra.items() if k not in names]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
