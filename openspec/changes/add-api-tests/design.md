## Context

The current backend has zero integration tests under the `backend/tests/` folder for the main feature endpoints (search, library, and tasks). The test client set up in `backend/tests/conftest.py` has an initialization issue where `create_app` is called with `expected_token` instead of `auth_token`.

## Goals / Non-Goals

**Goals:**
- Correct the initialization issue in `backend/tests/conftest.py`.
- Implement API integration tests covering all endpoint routes of `search`, `library`, and `tasks` features under FastAPI TestClient.
- Validate request schema validation, normal execution flows, and common error responses (such as `ValidationError`, `NotFoundError`, or invalid query params/payloads) and authorization checks.
- Work within the existing dependency injection of `app.state.container` and SQLite in-memory database to ensure isolated test runs.

**Non-Goals:**
- Overhauling the container or repository implementation.
- Implementing vector search indexing features inside tests (we should mock out/intercept the vector embedding/search queries or verify correct fallback behavior).
- Modifying business logic to make tests pass.

## Decisions

### 1. Fix `conftest.py`
- Modify the `app` fixture in `backend/tests/conftest.py` to invoke `create_app` using the correct keyword argument: `auth_token="test-token"`.

### 2. Dependency Mocking / Verification for Search API
- When testing `/search` under `test_search.py`, mock the vector store's behavior or configure the sqlite repository to return predictable records.
- We will mock the `EmbeddingPort` and `VectorIndexPort` dynamically in the tests or use the dependencies that the container provides if they behave well under the default Settings.

### 3. File and Folder State Isolation
- In `test_library.py`, each test should create folders and import files inside an isolated SQLite memory database. We'll use the FastAPI app's dependency injection or repository overrides to manipulate folder/file records.
- For `GET /library/files/preview/{file_id}`, we will write a temporary file on disk (or mock its local file system read) to verify that bytes stream correctly.

## Risks / Trade-offs

- **[Risk]** Heavy dependency on Jina CLIP v2 embedding model might fail or take long.
  - **Mitigation** The `EmbeddingPort` can be mocked, or we can use fake/mock implementations since `SearchFilesUseCase` handles `NotImplementedError` gracefully and falls back to empty search results or keyword matching in the repository. We will specifically mock the vector store search method if we need to test semantic matches.
