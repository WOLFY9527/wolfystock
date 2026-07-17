from __future__ import annotations


class EnvironmentFailure(RuntimeError):
    """A bounded environment failure with a stable machine reason code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


class OfflineMaterialUnavailable(EnvironmentFailure):
    """The exact requested snapshot cannot be built without network access."""
