# Task 9 report — strict RGB PNG screenshot acceptance

## Diagnosis

The retained platform-owned headed/Xvfb neutral screenshot was a structurally valid exact-viewport PNG: 1920×1080, bit depth 8, non-interlaced, color type 2 (opaque RGB). The product adapter rejected it before artifact return because `pngDimensions()` required color type 6 (RGBA). This was a bounded-parser defect, not a browser, viewport, or evidence-sealing failure.

## TDD evidence

### RED

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py::test_production_adapter_accepts_valid_opaque_rgb_viewport_screenshot -vv
```

Before the adapter change, the real ESM parser was exercised through a temporary exact copy of the shipped adapter with only its private parser exported for the test. A fully decoded, filter-valid 1920×1080 color-type-2 PNG failed as expected with:

```text
Error: screenshot is not a decoded PNG
... data[9] !== 6 ...
```

### GREEN

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_runner.py
# 63 passed in 6.85s

node --check tools/acceptance/journeys/v2-mission-retirement.mjs
python -m compileall -q tools/tests/test_v2_acceptance_browser_contract.py
git diff --check
# all exited 0
```

## Changes

- Accept only PNG color types 2 (RGB) and 6 (RGBA), retaining exact 1920×1080, 8-bit, non-interlaced IHDR requirements.
- Derive decoded scanline and filter-byte stride from 3 RGB or 4 RGBA channels.
- Retain the 12 MiB source cap, streamed inflate bound, IDAT/IEND structure checks, decoded-length check, and filter-byte validation.
- Added real-ESM parser regression coverage for valid RGB and RGBA images, unsupported grayscale/palette/grayscale-alpha color types, invalid decoded lengths for both accepted forms, oversized input, and non-exact dimensions.

No Docker/Compose, runtime/health/static/final/browser lanes, external cleanup, or push was performed.

## Review-blocker repair (round 1)

### Root cause and TDD evidence

The first RGB change trusted a chunk's type and payload after only checking its byte bounds. It neither authenticated chunk bytes with their mandatory PNG CRC nor imposed the PNG critical-chunk ordering rules. A real-ESM regression was added first for a one-bit-corrupted IHDR CRC and was observed RED:

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py::test_production_adapter_rejects_png_with_corrupt_ihdr_crc -vv
# 1 failed: parser returned {"width":1920,"height":1080}
```

The validator now calculates CRC-32 over each chunk type plus payload and rejects any mismatch before examining the chunk. It requires IHDR at byte offset 8, validates the known PLTE structure only for RGB before IDAT, rejects unknown critical chunks, and keeps IDAT consecutive through IEND. Ancillary chunks remain CRC-validated; their unexamined metadata does not alter the decoded raster policy.

### Regression coverage and verification

The real ESM parser regressions now cover corrupted IHDR, IDAT, IEND, and ancillary CRCs; a pre-IHDR unknown critical chunk; an unknown critical chunk between IDAT and IEND; and a safe, bounded RGB PLTE. Existing RGB/RGBA, exact-dimension, 12 MiB, decoded-length, unsupported-color-type, filter, and inflate bounds remain intact.

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_runner.py
# 68 passed in 8.87s
node --check tools/acceptance/journeys/v2-mission-retirement.mjs
python -m compileall -q tools/tests/test_v2_acceptance_browser_contract.py
git diff --check
# all exited 0
```

## Re-review compatibility repair (round 2)

### Root cause and TDD evidence

The structural repair limited PLTE to `channels === 3`, which accidentally made the optional suggested palette invalid for an otherwise valid color-type-6 (RGBA) PNG. PNG permits a pre-IDAT PLTE for both accepted truecolor types (2 and 6). A real-ESM regression was added first using an exact 1920×1080, 8-bit RGBA image with CRC-valid IHDR, PLTE, IDAT, and IEND chunks; it was observed RED against the production adapter:

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py::test_production_adapter_accepts_valid_rgba_plte_viewport_screenshot -vv
# 1 failed: screenshot is not a decoded PNG at `channels !== 3`
```

The PLTE gate now accepts only channel counts 3 or 4, which remains confined by the existing IHDR gate to color types 2 and 6. All other PLTE constraints remain unchanged: one chunk only, before IDAT, nonempty, at most 768 bytes, and a multiple of three; every chunk remains CRC-validated before interpretation.

### Regression coverage and verification

The real-ESM tests now accept a valid exact RGBA PNG with a bounded CRC-valid PLTE and reject empty, non-three-byte-aligned, and oversized PLTE payloads plus PLTE with an unsupported indexed color type. Existing strict CRC, IHDR-first, unknown-critical-chunk, IDAT consecutiveness, IEND-finality, filter-byte, exact dimensions, decoded-size, and 12 MiB source-cap coverage remains in place.

```sh
pytest -q tools/tests/test_v2_acceptance_browser_contract.py -k 'plte or rgba' -vv
# 5 passed, 20 deselected in 1.45s
pytest -q tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_runner.py
# 70 passed in 7.39s
node --check tools/acceptance/journeys/v2-mission-retirement.mjs
python -m compileall -q tools/tests/test_v2_acceptance_browser_contract.py
git diff --check
# all exited 0
```
