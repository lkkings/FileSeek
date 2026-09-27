"""Request and response models for the API.

Every response is wrapped in a uniform envelope carrying status, data, and error, so
clients can handle success and failure uniformly without reading the status code. The
envelope also carries pagination metadata when a response can be paged through.
"""

from __future__ import annotations

from typing import Any


def success_response(data: Any) -> dict[str, Any]:
    """Build a success response."""
    resp: dict[str, Any] = {
        "status": "success",
        "data": data,
        "error": None,
    }
    return resp


def error_response(message: str) -> dict[str, Any]:
    """Build an error response."""
    return {
        "status": "error",
        "data": None,
        "error": message,
    }
