class VialbumError(Exception):
    """Base exception for expected application errors."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ConflictError(VialbumError):
    pass


class ConfigurationError(VialbumError):
    pass


class InvalidInputError(VialbumError):
    pass


class NotFoundError(VialbumError):
    pass


class UnauthorizedError(VialbumError):
    pass
