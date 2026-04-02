class BaseAppError(Exception):
    """Base exception for all application-specific errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ResourceExistsError(BaseAppError):
    """Raised when trying to create a resource that already exists."""

    pass


class ResourceNotFoundError(BaseAppError):
    """Raised when a requested resource cannot be found."""

    pass


class InvalidArgumentError(BaseAppError):
    """Raised when an argument is provided with an incorrect value."""

    pass
