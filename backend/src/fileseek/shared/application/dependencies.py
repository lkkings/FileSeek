from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


def resolve_dependency(request: Any, name: str) -> T:
    return request.app.state.dependencies[name]
