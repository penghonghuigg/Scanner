from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
