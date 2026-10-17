"""Typed service errors: callers branch on fields, never exception text."""


class OperatorError(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        fields: dict[str, str] | None = None,
        current_version: int | None = None,
        record_ids: list[str] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.fields = fields
        self.current_version = current_version
        self.record_ids = record_ids
