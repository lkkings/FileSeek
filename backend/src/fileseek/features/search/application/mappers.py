from fileseek.features.library.domain.entities import File
from fileseek.features.search.application.contracts import SearchRequest
from fileseek.features.search.application.dto import FileDTO
from fileseek.features.search.application.queries import FileSortBy, SearchFilesQuery, SortOrder
from fileseek.shared.domain.file_types import FileCategory


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


def search_request_to_query(body: SearchRequest) -> SearchFilesQuery:
    categories = [
        FileCategory(category) for category in body.categories if category in list(FileCategory)
    ]
    return SearchFilesQuery(
        query=body.query,
        tag=body.tag,
        folder_id=body.folder_id,
        categories=categories,
        name_query=body.name_query,
        min_size_m=body.min_size_m,
        max_size_m=body.max_size_m,
        start_date=body.start_date,
        end_date=body.end_date,
        page_number=body.page_number,
        page_size=body.page_size,
        sort_by=FileSortBy(body.sort_by),
        sort_order=SortOrder(body.sort_order),
    )
