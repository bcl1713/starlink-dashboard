# Release Policy

**Purpose**: Define branch usage, semantic versioning, and release discipline
for Starlink Dashboard.
**Audience**: Contributors, release managers, mission operators.

## Branch Policy

- `main` is the stable mission branch. Keep it usable for active
  aircraft/mission operations.
- `dev` is the long-lived integration branch for enhancements and fixes that
  need aircraft or mission validation before they are promoted.
- Feature and fix branches should target `dev` by default unless the change is
  an urgent stable-branch hotfix.
- Do not merge experimental timeline/export work directly to `main`. Integrate
  and test it on `dev` first.

## Semantic Versioning

Starlink Dashboard releases follow semantic versioning (`MAJOR.MINOR.PATCH`):

- **Patch** (`x.y.Z`): bug fixes that preserve existing output formats, APIs,
  and operator workflows.
- **Minor** (`x.Y.z`): behavior-compatible feature additions or improvements
  that do not require consumers to change.
- **Major** (`X.y.z`): incompatible API, output, export-schema, or
  operator-workflow changes.

When in doubt, choose the larger version bump. Silent incompatibility is a
rather tiresome gift to future us.

## Lightweight Release Flow

1. Merge and test changes on `dev`.
2. Validate mission-critical behavior on aircraft or representative mission
   data.
3. Prepare release notes or changelog entries that call out operator-visible
   behavior, export/API changes, fixes, and manual validation performed.
4. Promote validated changes from `dev` to `main` with a reviewed PR.
5. Tag releases from `main` only after mission validation passes.
6. Keep `dev` open for the next integration cycle after the release tag is cut.

## Hotfixes

Urgent fixes for active mission use may branch from `main`, then merge back
into both `main` and `dev` after review. Record the patch version and the
reason for bypassing the normal `dev` validation path in the release notes.

## Related Documentation

- [Development Workflow](./workflow.md)
- [Contributing](../../CONTRIBUTING.md)
