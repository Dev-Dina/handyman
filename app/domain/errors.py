class VaultUnavailableError(RuntimeError):
    pass


class SecretNotFoundError(RuntimeError):
    pass


class ToolInputError(ValueError):
    """Raised by tool services when input cannot be processed."""


class OllamaUnavailableError(RuntimeError):
    """Raised when the Ollama HTTP endpoint cannot be reached or returns an error."""


class ModelServerUnavailableError(RuntimeError):
    """Raised when the model server HTTP endpoint cannot be reached or returns an error."""


class RagCorpusNotReadyError(RuntimeError):
    """Raised when the RAG chunk corpus file cannot be loaded."""
