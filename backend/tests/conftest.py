import os

# torch and faiss-cpu each bundle their own libomp.dylib; a process holding both
# aborts on the first faiss search unless this is set before either is imported.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pytest

# The API tests share one set of collaborators; see api_fixtures for why.
pytest_plugins = ["api_fixtures"]


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Treat an empty collection as success so filtered CI runs do not fail."""
    if session.exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
