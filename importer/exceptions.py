"""Common exception types for the Mealie importer."""

class UserAbort(RuntimeError):
    """Raised when the user cancels an interactive pipeline step."""

    pass
