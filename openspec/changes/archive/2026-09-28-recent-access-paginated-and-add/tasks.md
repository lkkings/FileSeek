## 1. Domain & Infrastructure Layers Update

- [x] 1.1 Update `RecentAccessRepository` protocol in `backend/src/fileseek/features/recent/domain/repositories/__init__.py` to declare `delete(record_id: int) -> None` and verify code syntax with `ruff`.
- [x] 1.2 Implement `delete` in `RecentAccessRepositoryImpl` in `backend/src/fileseek/features/recent/infrastructure/repositories/recent.py`, deleting specified record from `RecentAccessModel`, then verify code syntax with `ruff`.

## 2. Application Layer Update

- [x] 2.1 Refactor `RecentAccessDTO` in `backend/src/fileseek/features/recent/application/dto/__init__.py` to hold record ID and an optional nested `FileDTO`.
- [x] 2.2 Refactor `ListRecentAccessUseCase` in `backend/src/fileseek/features/recent/application/use_cases/list_record_access.py` to inject `FileRepository`, retrieve file details, populate nested `FileDTO` and return paginated results, and verify with `ruff`.
- [x] 2.3 Implement `DeleteRecentAccessUseCase` in `backend/src/fileseek/features/recent/application/use_cases/delete_record_access.py` and register it in `backend/src/fileseek/features/recent/application/use_cases/__init__.py`.

## 3. HTTP Interfaces Layer Update

- [x] 3.1 Update HTTP schema responses and requests in `backend/src/fileseek/features/recent/interfaces/http/schemas/recent.py` to support `RecentAccessResponse` with a nested `FileResponse`.
- [x] 3.2 Update HTTP mapper `recent_access_to_schema` in `backend/src/fileseek/features/recent/interfaces/http/mappers.py` to cleanly map `RecentAccessDTO` with its nested `FileDTO` into `RecentAccessResponse`, and verify with `ruff`.
- [x] 3.3 Register `DeleteRecentAccessUseCase` and adjust use case initialization inside composition root `backend/src/fileseek/bootstrap/dependencies.py`.
- [x] 3.4 Implement route `DELETE /recent/{record_id}` and update `GET /recent` to cleanly serialize results in `backend/src/fileseek/features/recent/interfaces/http/routers/recent.py`.
- [x] 3.5 Write tests for paginated listing, creation, and deletion in `backend/tests/api/test_recent.py`, ensuring tests verify standard DTO to Response Schema conversions.
