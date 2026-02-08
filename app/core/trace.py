"""Trace id helpers for request/response correlation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

TRACE_ID_HEADER = "X-Trace-Id"

if TYPE_CHECKING:
    from fastapi import Request


def get_or_create_trace_id(request: Request) -> str:
    """Return client-provided trace id or create a new one."""
    existing = request.headers.get(TRACE_ID_HEADER)
    if existing:
        return existing
    return uuid4().hex


def get_trace_id(request: Request) -> str:
    """Fetch the trace id stored by middleware or create one."""
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        return trace_id
    return get_or_create_trace_id(request)
