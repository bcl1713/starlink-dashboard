"""Bounded byte transfer and private, caller-owned package storage."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from tempfile import SpooledTemporaryFile
from typing import IO

from .archive_errors import ArchiveCapacityError

_SPOOL_BUDGET = ContextVar("mission_package_spool_budget", default=None)


class BudgetedSpool:
    def __init__(self, stream, budget):
        self.stream, self.budget, self.high_water = stream, budget, 0

    def write(self, data):
        end = max(self.high_water, self.stream.tell() + len(data))
        added = end - self.high_water
        if end > 100 * 1024 * 1024 or self.budget[0] + added > 200 * 1024 * 1024:
            raise ArchiveCapacityError("planning-spool", 200 * 1024 * 1024)
        result = self.stream.write(data)
        self.budget[0] += added
        self.high_water = end
        return result

    def close(self):
        if not self.stream.closed:
            self.stream.close()
            self.budget[0] -= self.high_water

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@contextmanager
def budgeted_spools():
    token = _SPOOL_BUDGET.set([0])
    try:
        yield
    finally:
        _SPOOL_BUDGET.reset(token)


def iter_zip_blocks(stream: IO[bytes], block_size: int = 65536) -> Iterator[bytes]:
    while block := stream.read(block_size):
        yield block


def new_package_stream() -> IO[bytes]:
    # Ownership transfers to the returned stream's caller.
    stream = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")  # noqa: SIM115
    budget = _SPOOL_BUDGET.get()
    return BudgetedSpool(stream, budget) if budget is not None else stream
