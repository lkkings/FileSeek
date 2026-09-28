from fileseek.features.library.domain.entities import File
from fileseek.features.search.application.dto import FileDTO


def file_to_dto(file: File) -> FileDTO:
    modified_str = file.modified.isoformat() if file.modified else None
    chunks = file.chunks if file.chunks is not None else []
    normalized_chunks: list[object] = list(chunks)
    best_chunk = max(
        chunks,
        key=lambda chunk: chunk.score,
        default=None,
    )
    return FileDTO(
        file_id=file.id,
        file_name=file.name,
        category=file.category.value,
        file_type=file.file_type.value,
        path=file.path,
        size=file.size,
        modified=modified_str,
        tags=file.tags,
        chunks=normalized_chunks,
        score=best_chunk.score if best_chunk is not None else 0,
        metadata=(
            best_chunk.metadata
            if best_chunk is not None and best_chunk.metadata is not None
            else {}
        ),
    )
