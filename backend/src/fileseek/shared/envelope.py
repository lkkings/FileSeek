"""Request and response models for the API.

Every response is wrapped in a uniform envelope carrying status, data, and error, so
clients can handle success and failure uniformly without reading the status code. The
envelope also carries pagination metadata when a response can be paged through.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResponseEnvelope[T](BaseModel):
    """The shape every API response has."""

    status: str = Field(..., description="success or error")
    data: T | None = Field(None, description="The response payload, present on success")
    error: str | None = Field(None, description="The error message, present on failure")

    # Pagination metadata, present when the response is one page of many.
    page: int | None = Field(None, description="The current page number")
    page_size: int | None = Field(None, description="How many results are in this page")
    total: int | None = Field(None, description="The total number of results across all pages")
    has_more: bool | None = Field(None, description="Whether there are more pages to fetch")


def success_response(data: Any, **pagination_meta: Any) -> dict[str, Any]:
    """Build a success response."""
    resp: dict[str, Any] = {
        "status": "success",
        "data": data,
        "error": None,
    }
    # Pagination fields are optional and only appear when the caller provides them.
    for key in ["page", "page_size", "total", "has_more"]:
        if key in pagination_meta:
            resp[key] = pagination_meta[key]
    return resp


def error_response(message: str) -> dict[str, Any]:
    """Build an error response."""
    return {
        "status": "error",
        "data": None,
        "error": message,
    }
