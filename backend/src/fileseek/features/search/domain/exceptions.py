from fileseek.shared.domain.exceptions import ApplicationError


class AgentProviderError(ApplicationError):
    """Raised when the external retrieval agent cannot complete a request."""
