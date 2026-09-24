from __future__ import annotations

from typing import Any


def resolve_dependency(request: Any, name: str) -> Any:
    return request.app.state.dependencies[name]
