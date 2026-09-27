from fileseek.features.search.application.dto import (
    FileDTO
)
from fileseek.features.library.domain.entities import File

def file_to_dto(file: File) -> FileDTO:
    modified_str = file.modified.isoformat() if file.modified else None
    best_chunk = max(
        file.chunks,
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
        chunks=file.chunks,
        score=best_chunk.score,
        metadata=best_chunk.metadata
    )