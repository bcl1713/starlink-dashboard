import type {
  EncounterPlanSummary,
  RouteSigmetEntry,
  SelectedSigmetEntry,
} from '@/services/route-sigmets';
import { passageReasons } from './sigmet-encounter-text';
export function SigmetEncounterDetails({
  entry,
  plan,
}: {
  entry: RouteSigmetEntry | SelectedSigmetEntry;
  plan: EncounterPlanSummary | null;
}) {
  if (!('encounter' in entry))
    return <p>Encounter unavailable — no route intersection</p>;
  return (
    <section aria-label="Planned passage details">
      <p>
        Planned UTC · Constant planned speed within each route segment. Altitude
        is not evaluated.
      </p>
      <p>
        Timing source: {plan?.source ?? 'unavailable'} · Precision:{' '}
        {plan?.precision ?? 'unknown'} · Method: {plan?.method ?? 'unavailable'}
      </p>
      {plan && (
        <p>
          Plan revision: {plan.revision} · Source revision:{' '}
          {plan.source_revision ?? 'unavailable'}
        </p>
      )}
      <table>
        <caption>Planned passage intervals</caption>
        <tbody>
          {entry.encounter.spans.map((p, i) => (
            <tr key={i}>
              <td>
                Segment {entry.spans[i].segment_index + 1}:{' '}
                {p.entry_ms !== null && p.exit_ms !== null
                  ? `${new Date(p.entry_ms).toISOString()} – ${new Date(p.exit_ms).toISOString()} · ${p.status === 'overlap' ? 'Time overlap' : 'No time overlap'}`
                  : passageReasons[p.reason ?? 'unavailable-plan']}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
