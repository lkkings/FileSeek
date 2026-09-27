## Why

The backend has multiple modules (`search`, `library`, `tasks`) providing critical APIs, but currently there are no API integration tests for them. Adding comprehensive API tests ensures stability, prevents regression, and documents API behaviors and boundary conditions.

## What Changes

- Create API integration tests under `backend/tests/api/`.
- Cover `POST /search` semantic search endpoint under `test_search.py`.
- Cover `library` API endpoints (`POST /library/files`, `GET /library/files/preview/{file_id}`, `GET /library/folders`, `POST /library/folders`, `PUT /library/folders/{folder_id}`, `DELETE /library/folders/{folder_id}`) under `test_library.py`.
- Cover `tasks` API endpoints (`GET /tasks`, `POST /tasks/{task_id}/retry`) under `test_tasks.py`.
- Fix existing setup issue in `backend/tests/conftest.py` where `create_app` is called with invalid keyword argument `expected_token` instead of `auth_token`.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
<!-- None -->

## Impact

- `backend/tests/conftest.py`: Corrects the `create_app` parameters for the test client setup.
- `backend/tests/api/test_search.py`: Comprehensive test suite for search endpoints.
- `backend/tests/api/test_library.py`: Comprehensive test suite for library (file & folder) endpoints.
- `backend/tests/api/test_tasks.py`: Comprehensive test suite for task management endpoints.
