## Context

The current `recent` module manages the user's history of recently accessed files. We are upgrading the module to fully support paginated retrieval (`page` and `page_size` parameters), nesting full `FileDTO` metadata inside `RecentAccessDTO`, and exposing a `DELETE /recent/{record_id}` endpoint to allow users to prune entries from their history.

## Goals / Non-Goals

**Goals:**
- Provide robust page-by-page retrieval (`GET /recent`) returning nested file information.
- Introduce an explicit HTTP POST endpoint (`POST /recent`) for adding recent access records dynamically.
- Introduce an explicit HTTP DELETE endpoint (`DELETE /recent/{record_id}`) for deleting recent access records.
- Maintain clean layered architectural boundaries (UseCase returns DTO; router/mapper converts DTO to Response Schema).

**Non-Goals:**
- Direct manipulation of files on the filesystem during deletion.
- Modification of database schemas.

## Decisions

### 1. File Metadata Aggregation in Application Layer
The `ListRecentAccessUseCase` will depend on both `RecentAccessRepository` and `FileRepository`.
- *Rationale*: Collecting file data inside the UseCase preserves clean architecture by ensuring the database model remains simple and performance is optimized through service coordination.

### 2. DTO and Schema Response Decoupled Mapping
- `RecentAccessDTO` will contain a nested `FileDTO`.
- `RecentAccessResponse` will contain a nested `FileResponse`.
- The mapper (`mappers.py`) under the HTTP layer will be responsible for translating `RecentAccessDTO` to `RecentAccessResponse`.

### 3. Deletion Port
- A `delete(record_id: int)` method will be added to the repositories and use cases.

## Risks / Trade-offs

- **Performance of File Fetches**: Iteratively querying `file_repo.get_by_id` inside a loop can be suboptimal for massive pages. Since default page size is 20 and the dataset is local, this approach is clean and simple. Future optimization could use batch fetching from the database if necessary.
- **Dangling Access Logs**: If a file is deleted from the `files` table, its access log remains in the database. In our design, `file_repo.get_by_id` returns `None` for deleted files, which is safely mapped to a `None` file inside the response without crashing the application.
