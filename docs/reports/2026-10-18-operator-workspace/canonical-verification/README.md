# Canonical verification

All three repository tiers passed with
`ACCEPTANCE_POLICY_BASE_SHA=1a3e77d3b4017ad1f7cb33d1b1ef20b9378e0244`. Each used
explicit wall-clock termination and an owned, reaped process group.

- Backend: 4,219 passed, 20 skipped, one Cartopy presentation warning in 690.80
  seconds. Runtime/test source `88f3e46f9f77b6a5e20be64c1f4ed9ab2d76d0d8`;
  backend source is unchanged in the subsequent footer correction.
- Frontend: 305 files / 2,057 tests pass and the production build passes at
  `9b07dbb48c6036c3c3c217dc46f88583eb682fdd`, including the fixed editor footer.
  The existing bundle-size advisory remains a build warning.
- Static: Python formatting/lint, filename conventions, frontend
  formatting/lint, Markdown formatting, internal documentation links and 12
  policy/link tests pass at the same `9b07dbb4` source. The external link
  checker reports repository-defined nonblocking availability warnings
  (including remote rate limits).

Final published documentation at `63cae2a1` also passes the complete static tier;
its exact log and independent cleanup record are in `static-publication`.

The ten-, thirty- and twenty-minute limits for static/backend/frontend were
unchanged. No test selectors, skip rules or verification commands were relaxed.
Early static failures are retained: Python import spacing, four frontend test
formatting errors and report Markdown/operations-reference length. These were
corrected; no runtime behavior changed for those formatting repairs. A static
run started before the last operations paragraph wrap and finished afterward;
that transitional pass was superseded by the retained clean `9b07dbb4` pass.

All completed groups were independently checked through the host process table:
no survivors. Private pytest directories were removed. No server, listener or
Docker project was started by these tiers. Automated results do not grant
uncoached human or physical-device acceptance.
