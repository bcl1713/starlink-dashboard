# Production briefing samples

These files were extracted unchanged from real mission export ZIPs through the
production API and Nginx, using supported synthetic mission, KML and provider
inputs. They are ready for customer review; acceptance remains pending.

| Actual PDF                                        | Pages | Verified coordination rows |
| ------------------------------------------------- | ----: | -------------------------: |
| [Dense continuation example](dense-two-page.pdf)  |     2 |                         14 |
| [Long continuation example](dense-three-page.pdf) |     3 |                         30 |
| [Five-leg mission](five-leg.pdf)                  |     5 |                         10 |

Every printed coordination cell, page assignment, font and page boundary was
verified. All ten pages match the individually inspected color and grayscale PDF
rasters recorded in the manifest. Three fresh five-leg requests produced
identical content, geometry, preview hashes and PDF pixels. Only identified PDF
generation clocks are excluded from deterministic structural comparisons.

[Omitted-download feedback](omitted-download.png) is an actual browser
screenshot. The complete legacy ZIP downloads, the message remains until
dismissal, and reopening clears it. Included and disabled journeys also passed.

The [manifest](manifest.json) records the exact renderer candidate, production
image identities, PDF hashes, row counts and review scope. The complete PDF,
browser, lifecycle and fault controls ran at `960ae0ba`; the final imports ran
at `aa64cc9f`. Application/runtime sources, four base-image digests, 84 Python
package versions, 153 system-package records, and installed renderer assets
matched. A redundant whole-matrix rerun was stopped at the user's request. These
are combined checks with explicit provenance, not a claimed new-head full-matrix
pass. Adjacent evidence JSONs are the actual published evidence; private HTML,
previews and runtime files remain outside the ZIP. The feature remains off by
default.

Customer acceptance is required for these new continuation/multi-leg examples
and production download behavior. PR #312 accepted only its original two
single-page examples. No new five-second scan duration has been measured.
