import type {
  RouteSigmetEntry,
  SelectedSigmetEntry,
} from '@/services/route-sigmets';
import { crossingPassages, formatCrossingTime } from './sigmet-encounter-text';
export function SigmetEncounterDetails({
  entry,
  nowMs,
}: {
  entry: RouteSigmetEntry | SelectedSigmetEntry;
  nowMs: number;
}) {
  if (!('encounter' in entry)) return <p>Crossing time unknown</p>;
  if (entry.encounter.status === 'passed') return <p>Crossing passed</p>;
  const known = crossingPassages(entry).filter(
    (p) => p.status !== 'unknown' && p.status !== 'passed'
  );
  return (
    <section aria-label="Crossing details">
      {known.map((p, index) => (
        <p key={index}>
          {p.entry_ms === null || p.exit_ms === null
            ? 'Crossing time unknown'
            : `${p.status === 'overlap' ? 'Crossing expected' : 'Passage outside advisory validity'} · ${formatCrossingTime(p.entry_ms, p.exit_ms, nowMs)}`}
        </p>
      ))}
      {entry.encounter.unknown_count > 0 && (
        <p>
          {known.length
            ? 'Some crossing times unavailable'
            : 'Crossing time unknown'}
        </p>
      )}
    </section>
  );
}
