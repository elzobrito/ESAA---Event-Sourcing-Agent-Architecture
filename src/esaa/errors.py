from __future__ import annotations


class ESAAError(Exception):
    """Domain error with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CorruptedStoreError(ESAAError):
    pass

