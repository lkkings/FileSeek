from __future__ import annotations

import hashlib

from fastapi.responses import Response, StreamingResponse

from fileseek.features.library.application.ports import SourceFile
from fileseek.shared.utils.file_utils import detect_file_type_from_bytes

_CHUNK_SIZE = 64 * 1024
_FILE_TYPE_HEADER_SIZE = 4096


def stream_file(
    path: SourceFile,
    range_header: str | None = None,
):
    """返回支持浏览器预览和视频 Range 的文件响应。"""

    size = path.stat()["size"]
    content_type = _detect_content_type(path)

    # 没有 Range，直接流式返回整个文件
    if not range_header:
        return StreamingResponse(
            _iter_file(
                path,
                0,
                size - 1,
            ),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(size),
                "Content-Disposition": "inline",
            },
        )

    # 只处理单 Range
    if not range_header.startswith("bytes="):
        return _range_not_satisfiable(size)

    value = range_header[6:].strip()

    if "," in value:
        return _range_not_satisfiable(size)

    start, _, end = value.partition("-")

    try:
        if start:
            start = int(start)
            end = int(end) if end else size - 1

        else:
            # bytes=-500
            length = int(end)

            if length <= 0:
                raise ValueError

            start = max(
                size - length,
                0,
            )
            end = size - 1

    except ValueError:
        return _range_not_satisfiable(size)

    if start < 0 or start >= size or start > end:
        return _range_not_satisfiable(size)

    end = min(
        end,
        size - 1,
    )

    length = end - start + 1

    return StreamingResponse(
        _iter_file(
            path,
            start,
            end,
        ),
        status_code=206,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": (
                f"bytes {start}-{end}/{size}"
            ),
            "Content-Length": str(length),
            "Content-Disposition": "inline",
        },
    )


def _detect_content_type(
    path: SourceFile,
) -> str:
    """读取少量文件头检测 MIME Type。"""

    try:
        with path.open("rb") as file:
            header = file.read(
                _FILE_TYPE_HEADER_SIZE
            )

        return detect_file_type_from_bytes(header).value

    except (OSError, ValueError):
        return "application/octet-stream"


def _range_not_satisfiable(
    size: int,
) -> Response:
    """返回 HTTP 416 Range Not Satisfiable。"""

    return Response(
        status_code=416,
        headers={
            "Content-Range": f"bytes */{size}",
        },
    )


def _iter_file(
    path: SourceFile,
    start: int,
    end: int,
):
    """分块读取文件。"""

    remaining = end - start + 1

    with path.open("rb") as file:
        file.seek(start)

        while remaining > 0:
            chunk = file.read(
                min(
                    _CHUNK_SIZE,
                    remaining,
                )
            )

            if not chunk:
                break

            remaining -= len(chunk)

            yield chunk


def thumbnail_response(
    data: bytes,
    *,
    source_size: int,
    source_modified: str,
) -> Response:
    """Return a cacheable WebP thumbnail without exposing source paths."""

    digest = hashlib.sha256(
        f"{source_size}:{source_modified}:".encode() + data,
    ).hexdigest()
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": "inline",
            "ETag": f'"{digest}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
