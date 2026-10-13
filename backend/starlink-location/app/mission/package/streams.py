"""Bounded byte transfer and private, caller-owned package storage."""

from collections.abc import Iterator
from tempfile import SpooledTemporaryFile
from typing import IO


def iter_zip_blocks(stream: IO[bytes], block_size: int = 65536) -> Iterator[bytes]:
    while block := stream.read(block_size):
        yield block


def new_package_stream() -> IO[bytes]:
    return SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
