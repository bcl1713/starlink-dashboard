"""Safe, actionable export failures without exposing internal exception text."""


class ArchiveCapacityError(RuntimeError):
    def __init__(self, layer, max_bytes):
        self.detail = {
            "code": "mission_archive_capacity",
            "layer": layer,
            "max_bytes": max_bytes,
            "message": f"Mission export exceeds the {layer} capacity ({max_bytes // (1024 * 1024)} MiB). Try Compact lossless or retry after older exports expire. Recorded source data is preserved.",
        }
        super().__init__(self.detail["message"])


class ArchiveDeadlineError(RuntimeError):
    def __init__(self):
        self.detail = {
            "code": "mission_archive_deadline",
            "message": "Mission archive capture reached its time limit. Please retry.",
        }
        super().__init__(self.detail["message"])
