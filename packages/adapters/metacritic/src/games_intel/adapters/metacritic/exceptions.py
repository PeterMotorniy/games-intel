from __future__ import annotations

from games_intel.contracts.adapters import AdapterError, AdapterErrorCode


class MetacriticAdapterError(Exception):
    """Typed adapter failure mapped to AdapterError for workers and HTTP."""

    def __init__(self, code: AdapterErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dto(self) -> AdapterError:
        return AdapterError(code=self.code, message=self.message)

    @classmethod
    def from_dto(cls, error: AdapterError) -> MetacriticAdapterError:
        return cls(error.code, error.message)
