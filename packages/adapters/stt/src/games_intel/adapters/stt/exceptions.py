from __future__ import annotations

from games_intel.contracts.adapters import AdapterError, AdapterErrorCode


class SttAdapterError(Exception):
    """Typed STT failure mapped to AdapterError for TranscriptionAgent / worker."""

    def __init__(self, code: AdapterErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dto(self) -> AdapterError:
        return AdapterError(code=self.code, message=self.message)
