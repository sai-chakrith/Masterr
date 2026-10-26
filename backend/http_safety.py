"""Bound request bodies and log request IDs without tokens, bodies or query strings."""
import json
import logging
import time
from uuid import uuid4
from starlette.responses import JSONResponse

log = logging.getLogger("mastrr.requests")


class RequestSafetyMiddleware:
    def __init__(self, app, max_body=1_048_576):
        self.app, self.max_body = app, max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, request_id, status = time.monotonic(), str(uuid4()), 500
        async def safe_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers += [(b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff")]
                if scope["path"].startswith("/v1/"):
                    headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"] + [(b"cache-control", b"no-store")]
                message = {**message, "headers": headers}
            await send(message)
        try:
            chunks, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > self.max_body:
                    return await JSONResponse(status_code=413, content={"error": {"code": "body_too_large", "message": "Request is too large."}})(scope, receive, safe_send)
                chunks.append(message)
                if not message.get("more_body", False):
                    break
            index = 0
            async def replay():
                nonlocal index
                if index < len(chunks):
                    item = chunks[index]; index += 1
                    return item
                return await receive()
            await self.app(scope, replay, safe_send)
        finally:
            route = scope.get("route")
            log.info(json.dumps({"request_id": request_id, "method": scope["method"],
                                "route": getattr(route, "path", "unmatched"), "status": status,
                                "duration_ms": round((time.monotonic() - started) * 1000)}))
