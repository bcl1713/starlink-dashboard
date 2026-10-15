import type { ImportOperation } from '../../types/itinerary-import';
const labels: Record<string, string> = {
  reading_documents: 'Reading itinerary and routes…',
  matching_routes: 'Matching routes…',
  building_plans: 'Building satellite plans…',
  preparing_mission: 'Preparing mission…',
  review_changes: 'Revision ready to review',
  complete: 'Mission ready',
};
export function ImportProgress({ operation }: { operation: ImportOperation }) {
  return (
    <p role="status" aria-live="polite">
      {operation.state === 'queued'
        ? 'Waiting to start…'
        : (labels[operation.stage] ?? 'Preparing mission…')}
    </p>
  );
}
