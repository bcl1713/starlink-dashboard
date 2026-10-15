import type { ExpectedLeg, PlanningDraft } from '../types/planning';

/** Source review is separate from approving the proposed satellite plan. */
export function planningSourceReady(
  leg: ExpectedLeg,
  draft: PlanningDraft = leg.draft ?? {},
  section = leg.ar_section_status
) {
  const permitted = draft.permitted_satellite_ids ?? [];
  const confirmed = draft.access_confirmation;
  if (
    !leg.route ||
    section === 'unrecognized' ||
    !permitted.length ||
    !confirmed?.confirmed ||
    confirmed.satellite_ids.length !== permitted.length ||
    confirmed.satellite_ids.some((id) => !permitted.includes(id)) ||
    draft.unresolved_aar_windows?.length ||
    draft.unresolved_x_transitions?.length
  )
    return false;
  const rows = draft.ar_corrections?.length
    ? draft.ar_corrections
    : (leg.ar_rows ?? []);
  const active = rows.filter((row) => row.match_status !== 'excluded');
  if (!active.length)
    return (
      !!draft.no_ars_confirmed &&
      rows.every(
        (row) => row.match_status !== 'excluded' || !!row.exclusion_note?.trim()
      )
    );
  return (
    active.every(
      (row) =>
        row.confirmed &&
        row.match_status === 'matched' &&
        !!row.confirmed_units &&
        row.source_altitude != null &&
        Number.isFinite(row.source_altitude) &&
        row.source_altitude > 0 &&
        row.start_anchor?.content_hash === leg.route!.content_hash &&
        row.end_anchor?.content_hash === leg.route!.content_hash &&
        Number.isFinite(Date.parse(row.entry_time)) &&
        Date.parse(row.entry_time) < Date.parse(row.exit_time)
    ) &&
    rows.every(
      (row) => row.match_status !== 'excluded' || !!row.exclusion_note?.trim()
    )
  );
}
