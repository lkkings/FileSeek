from __future__ import annotations

import hashlib
from collections.abc import Iterator

from fastapi.responses import Response, StreamingResponse

from fileseek.features.library.application.ports import SourceFile
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.shared.utils.file_utils import detect_file_type_from_bytes

_CHUNK_SIZE = 64 * 1024
_FILE_TYPE_HEADER_SIZE = 4096


def stream_file(
    path: SourceFile,
    range_header: str | None = None,
) -> Response:
    """返回支持浏览器预览和视频 Range 的文件响应。"""

    try:
        size = _source_size(path)
        content_type = _detect_content_type(path)
    except SourceUnavailableError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise SourceUnavailableError("文件来源不可获取") from exc

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

    start_text, _, end_text = value.partition("-")

    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1

        else:
            # bytes=-500
            length = int(end_text)

            if length <= 0:
                return _range_not_satisfiable(size)

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


def _source_size(path: SourceFile) -> int:
    size_value = path.stat()["size"]
    if not isinstance(size_value, int):
        raise TypeError
    return size_value


def _detect_content_type(
    path: SourceFile,
) -> str:
    """读取少量文件头检测 MIME Type。"""

    with path.open("rb") as file:
        header = file.read(_FILE_TYPE_HEADER_SIZE)

    file_type = detect_file_type_from_bytes(header)
    if file_type is None:
        return "application/octet-stream"

    return file_type.media_type


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
) -> Iterator[bytes]:
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
