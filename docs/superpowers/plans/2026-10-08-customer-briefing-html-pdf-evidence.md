# Customer Briefing HTML-to-PDF Evidence Task

Required Task 4 companion to the
[checkpoint plan](2026-10-08-customer-briefing-html-pdf-checkpoint.md) and its
[runtime task](2026-10-08-customer-briefing-html-pdf-runtime.md). All Global
Constraints and execution gates apply. No implementation has begun.

## Task 4: Validate, publish, and review the two checkpoint pages

**Files:** Create `B/app/mission/exporter/customer_evidence.py`,
`B/tests/unit/test_customer_evidence.py`,
`tools/acceptance/customer-briefing/{html_pdf_checkpoint.py,html_pdf_generate.py,html_pdf_inspect.py,compose.html-pdf.yml}`,
and `tools/tests/test_customer_briefing_html_pdf_checkpoint.py`. Reuse Task 3's
real-process test module; create
`tools/acceptance/customer-briefing/HTML-PDF-README.md`. Do not copy the dirty
old `composition_checkpoint.py` or LibreOffice pipeline.

**Interfaces:**

```text
build_customer_evidence(snapshot: ExportSnapshot, trial: TrialLeg, view: CustomerLegView, report: dict) -> bytes
```

Validates matching fingerprint/leg/rows and serializes deterministic
schema-version-1 JSON. Fields:
`schemaVersion,snapshotFingerprint,legId,canonical,customerRows,pages,render`.
`canonical` records all exact clocks, source records, decisions/references,
restrictions and confidence; `customerRows` records interval/source mappings;
`pages` maps page 1 to exact bounds/row IDs; `render` contains Task 3's report.
Validation requires one verified PDF page, all required rows, successful
cleanup, and total deadline consumption ≤60000 ms. Unknown transport remains
unknown. Artifact references use relative published filenames, never temporary
paths; include their hashes so publication cannot leave dangling evidence
pointers.

`inspect_pdf(pdf_path: Path, html_png_path: Path) -> dict` uses Poppler to check
one page, 960×540 pt dimensions within 0.01 pt, required extracted customer
text, PDF word bounds, and color/grayscale PNG renders at 240 dpi (3200×1800).
Report PDF/HTML dimensions, text/geometry observations, and images for visual
comparison. Do not assert byte-identical antialiasing across PDF rasterization
and browser screenshots; compare their layout and inspect actual rendered pages.

`publish_checkpoint(staging: Path, destination: Path, evidence: bytes) -> None`
validates the four files then atomically renames a completed directory on the
same filesystem. Per example, retain `mission-customer-briefing-trial.html`,
`.png`, `.pdf`, and `mission-customer-briefing-evidence.json`. No partial
deliverable directory or orphan evidence on failure. This is local checkpoint
publication; ZIP/manifest/header integration is deferred.

```text
run_checkpoint(candidate_sha: str, evidence_root: Path, runtime_tests: bool=False) -> dict
```

Requires a clean committed candidate, records scoped ownership, builds the
dedicated exact-SHA image, runs checks, inspects/publishes the pair, and tears
down/audits in `finally`. CLI:

```bash
python3 tools/acceptance/customer-briefing/html_pdf_checkpoint.py --candidate-sha <full-sha> --evidence-root <path> [--runtime-tests]
```

Report `checksPassed` separately from `visualAcceptance`, initially `pending`.

- [ ] Write `test_evidence_rejects_mismatched_snapshot_and_page_rows` and
      `test_evidence_preserves_exact_unknown_and_source_records` in
      `test_customer_evidence.py`; run them expecting named missing-contract
      assertions, then implement the serializer/validation. Assert exact unsplit
      sources and ET/Zulu/T-plus values survive; PDF never substitutes rounded
      display strings for canonical evidence.
- [ ] Write `test_checkpoint_publishes_only_validated_pair`,
      `test_evidence_failure_after_pdf_leaves_no_deliverable`,
      `test_cleanup_failure_rejects_publication`, and
      `test_checkpoint_signal_cleans_owned_resources` in the tools test file.
      Use temporary owned directories and fake subprocess/Compose handles;
      assert:

  ```python
  assert not destination.exists()  # evidence validation failed after PDF creation
  assert ownership["cleanup"]["children_reaped"]
  assert ownership["cleanup"]["compose_removed"]
  assert report["visualAcceptance"] == "pending"
  ```

  Run the tools test selection before implementing orchestration/publication;
  ensure failures arise from those contracts, not absent Docker/Python packages.

- [ ] Implement fixture generation using Task 1's canonical helpers and Task 2
      payload. Label synthetic DTO snapshot injection clearly; it does not prove
      real API capture or legacy ZIP equivalence. Record fixture/input hashes.
- [ ] Implement the Compose runner with project
      `briefing-html-pdf-<candidate-sha-first-12>-<run-id>`, private named
      volumes, exact image revision verification, no shared services/volumes,
      and no host published ports. Rooted evidence goes under ignored
      `.superpowers/sdd/2026-10-08-customer-briefing-html-pdf/evidence/<sha>/`.
      Separate retained evidence from disposable temp/browser paths. Docker
      image entry runs fixture generator and Node renderer sequentially; each
      example has a fresh request owner/browser, not a persistent cross-request
      browser.
- [ ] Run scoped backend/Node/tools tests and documentation checks; commit
      `feat: validate paired HTML-PDF checkpoint evidence` before image runs.
      The runner requires this clean committed SHA for all real-process proof.
- [ ] Run Task 3's named real-runtime fault cases via `--runtime-tests`,
      including real page overflow/font substitution, actual map failure,
      map/print hangs, parent cancellation, and listener/browser cleanup. Save
      per-case reports.
- [ ] Render three cold fully assessed requests without caches; all require
      intended map success, one page, all four posture colors, five-minute red
      width, both SOF periods, and successful cleanup within 60000 ms. Record
      per-stage timing/reserves, browser launch count 1, shared-browser flag
      true, versions, hardware/image identity, and timing margin. Compare
      repeated customer text, SVG geometry, decoded PNG pixels, page
      assignments, and normalized PDF structure excluding only identified
      creation metadata/document IDs.
- [ ] Render the incomplete-X page as a separate fresh request. Require a
      neutral overall band, one incomplete-planning note, X lane `?`, visible
      known outages, and confirmed remaining capability; never a false red
      definitive outage. Retain exact canonical uncertainty in evidence.
- [ ] Run a distinct missing-map/fallback example and an overlong title/table
      example. Fallback may reclaim map space and succeed; overflow must fail
      with no partial pair. Neither fallback nor failure qualifies primary
      appearance.
- [ ] Use `inspect_pdf` on both successful outputs. Preserve actual PDF-derived
      color/grayscale images, HTML preview, and full-resolution crop comparisons
      for header, red callout, table, patch, and map. Require no extra blank PDF
      page, matching leg/table content, loaded intended fonts, complete map
      crop, and visible useful markers. Desktop native-PPTX editing is not a
      checkpoint check.
- [ ] If real-runtime failures require fixes, commit them and repeat affected
      checks plus final two-page proof on the new clean committed SHA.
- [ ] From repository root, run

  ```bash
  timeout --kill-after=10s 15m python3 tools/acceptance/customer-briefing/html_pdf_checkpoint.py --candidate-sha <full-sha> --evidence-root <path>
  ```

  Build separately under `timeout --kill-after=10s 45m`; no timeout grants
  renderer stages a fresh budget. Persist failed attempts and cleanup reports.

- [ ] Tear down the owned Compose project with its exact file/project name,
      disposable volumes and network. Verify owned
      processes/listeners/containers/ networks/volumes gone, using approved host
      checks when PID namespace hides them. Remove task-specific disposable
      image tags after qualification; keep shared image layers, credentials, the
      open-PR worktree, and evidence.
- [ ] Push commits to #312. Return links/paths for both HTML/PNG/PDF/evidence
      sets, actual page counts, semantics/fit/timing results, fallback/fault
      results, and cleanup audit. Mark scan timing and visual acceptance pending
      until the customer actually performs/reports them. Stop here.

## Customer review gate

Show the fully assessed primary page at full resolution and the actual PDF. Ask
the customer to identify when capability is reduced, what is lost, what remains,
and when SOF/AR applies without explanation; record elapsed scan time and
observations. Request explicit acceptance of hierarchy, four posture colors,
typography, table readability, APO branding, whitespace, and integrated map.
Show the incomplete-X page separately for uncertainty semantics.

Automated passing checks authorize neither visual acceptance nor dense/long/
multi-leg generalization. Keep #312 draft and stop. Once the primary page is
explicitly accepted, prepare a separate follow-up plan for readable continuation
planning and real default-off PDF/evidence ZIP integration with legacy/failure/
UI/production acceptance; do not implement that follow-up during this
checkpoint.
