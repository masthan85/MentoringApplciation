"""Request limits and response headers applied to every request."""

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The API returns JSON and event streams only, never pages, so it can forbid nearly everything.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
HSTS = "max-age=63072000; includeSubDomains"


class BodyTooLarge(Exception):
    pass


class SecurityMiddleware:
    """Reject oversized bodies (declared or streamed) and add security headers."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int, hsts: bool) -> None:
        self.app, self.max_body_bytes, self.hsts = app, max_body_bytes, hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                extra = {
                    b"content-security-policy": API_CSP.encode(),
                    b"x-frame-options": b"DENY",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                    b"cross-origin-resource-policy": b"same-site",
                }
                if self.hsts:
                    extra[b"strict-transport-security"] = HSTS.encode()
                headers += [(k, v) for k, v in extra.items() if k not in present]
                message = {**message, "headers": headers}
            await send(message)

        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_body_bytes:
            await self._reject(send_with_headers)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send_with_headers)
        except BodyTooLarge:
            if not started:
                await self._reject(send_with_headers)

    async def _reject(self, send: Any) -> None:
        body = json.dumps(
            {
                "type": "https://mentor.example/problems/payload_too_large",
                "title": "payload too large",
                "status": 413,
                "detail": f"The request is larger than the {self.max_body_bytes // 1000} KB limit.",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
