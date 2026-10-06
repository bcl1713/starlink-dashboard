"""Disposable bulletin normalizer with CPU/RAM/output limits; no source I/O."""

import json
import os
import resource
import sys
import zlib

MAX_EXPANDED = 32 * 1024**2
MAX_INPUT = 8 * 1024**2
MAX_OUTPUT = 16 * 1024**2


def expand_gzip(body):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    expanded = decoder.decompress(body, MAX_EXPANDED + 1)
    if (
        len(expanded) > MAX_EXPANDED
        or decoder.unconsumed_tail
        or not decoder.eof
        or decoder.unused_data
    ):
        raise ValueError("Invalid or excessive gzip input")
    return expanded


def main():
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))
    from .normalization import normalize_metar, normalize_sigmet, normalize_taf

    functions = {
        "metar": normalize_metar,
        "taf": normalize_taf,
        "sigmet": normalize_sigmet,
    }
    layer, now = sys.argv[1:]
    body = sys.stdin.buffer.read(MAX_INPUT + 1)
    if layer not in functions or len(body) > MAX_INPUT:
        raise ValueError("Invalid normalization input")
    if layer != "sigmet":
        body = expand_gzip(body)
    result = functions[layer](body, int(now))
    encoded = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(encoded) > MAX_OUTPUT:
        raise ValueError("Normalized product exceeds budget")
    sys.stdout.buffer.write(encoded)


if __name__ == "__main__":
    main()
