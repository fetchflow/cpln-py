import requests


class CPLNException(Exception):
    """
    A base class from which all other exceptions inherit.

    If you want to catch all errors that the Docker SDK might raise,
    catch this base exception.
    """


class APIError(requests.exceptions.HTTPError, CPLNException):
    """
    An HTTP error from the API.
    """

    def __init__(self, message, response=None, explanation=None):
        # requests 1.2 supports response as a keyword argument, but
        # requests 1.1 doesn't
        super().__init__(message)
        self.response = response
        self.explanation = explanation

    def __str__(self):
        message = super().__str__()

        if self.is_client_error():
            message = (
                f"{self.response.status_code} Client Error for "
                f"{self.response.url}: {self.response.reason}"
            )

        elif self.is_server_error():
            message = (
                f"{self.response.status_code} Server Error for "
                f"{self.response.url}: {self.response.reason}"
            )

        if self.explanation:
            message = f'{message} ("{self.explanation}")'

        return message

    @property
    def status_code(self):
        if self.response is not None:
            return self.response.status_code

    def is_error(self):
        return self.is_client_error() or self.is_server_error()

    def is_client_error(self):
        if self.status_code is None:
            return False
        return 400 <= self.status_code < 500

    def is_server_error(self):
        if self.status_code is None:
            return False
        return 500 <= self.status_code < 600


class NotFound(APIError):
    pass


class ImageNotFound(NotFound):
    pass


class InvalidVersion(CPLNException):
    pass


class InvalidRepository(CPLNException):
    pass


class InvalidConfigFile(CPLNException):
    pass


class InvalidArgument(CPLNException):
    pass


class DeprecatedMethod(CPLNException):
    pass


class NullResource(CPLNException, ValueError):
    pass


class BuildError(CPLNException):
    def __init__(self, reason, build_log):
        super().__init__(reason)
        self.msg = reason
        self.build_log = build_log


class ImageLoadError(CPLNException):
    pass


class MissingContextParameter(CPLNException):
    def __init__(self, param):
        self.param = param

    def __str__(self):
        return f"missing parameter: {self.param}"


class ContextException(CPLNException):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class ContextNotFound(CPLNException):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"context '{self.name}' not found"


class WebSocketError(Exception):
    """Base class for all WebSocket-related errors."""

    pass


class WebSocketConnectionError(WebSocketError):
    """Raised when there are issues with the WebSocket connection."""

    pass


class WebSocketMessageError(WebSocketError):
    """Raised when there are issues with the WebSocket message content."""

    pass


class WebSocketExitCodeError(WebSocketMessageError):
    """Raised when the WebSocket message indicates a non-zero exit code."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class WebSocketOperationError(WebSocketMessageError):
    """Raised when the WebSocket message indicates an operation error."""

    pass


class TemplateNotFoundError(CPLNException):
    """Raised when a template file is not found."""

    pass


class TemplateVariableError(CPLNException):
    """Raised when there are issues with template variables."""

    pass


class TemplateParsingError(CPLNException):
    """Raised when there are issues parsing template content."""

    pass
