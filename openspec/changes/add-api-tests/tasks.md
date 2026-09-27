## 1. Setup and Fixes

- [x] 1.1 Fix `backend/tests/conftest.py` initialization by updating `expected_token` to `auth_token`. Verify health tests pass with `uv run pytest backend/tests/api/test_health.py`.

## 2. Implement Search Feature API Tests

- [x] 2.1 Implement `backend/tests/api/test_search.py` covering `/search` endpoint with normal, pagination, parameter types, bounds, missing token scenarios. Verify with `uv run pytest backend/tests/api/test_search.py`.

## 3. Implement Library Feature API Tests

- [x] 3.1 Implement `backend/tests/api/test_library.py` covering folders endpoints (`list_folders`, `create_folder`, `update_folder`, `delete_folder`) and files endpoints (`add_file`, `preview_file`). Ensure SQLite DB state validation and temporary files setup. Verify with `uv run pytest backend/tests/api/test_library.py`.

## 4. Implement Tasks Feature API Tests

- [x] 4.1 Implement `backend/tests/api/test_tasks.py` covering tasks endpoints (`list_tasks`, `retry_task`). Ensure pagination and retry flows. Verify with `uv run pytest backend/tests/api/test_tasks.py`.
