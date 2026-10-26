from typing import Any


class WindScopeError(Exception):
    def __init__(
        self, code: str, message: str, status: int = 503, details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


class SourceError(WindScopeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("elexon_unavailable", message, details=details)


class DataValidationError(WindScopeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("invalid_source_data", message, details=details)
