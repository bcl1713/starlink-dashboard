"""Concurrent settings writes must be reviewed before retrying."""


class SettingsConflict(Exception):
    """The supplied settings revision is no longer current."""
