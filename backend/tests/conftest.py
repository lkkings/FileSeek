import pytest


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Treat an empty collection as success so filtered CI runs do not fail."""
    if session.exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
