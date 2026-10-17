import type { ReadRecord } from '@/types/operator';
import { revisionUtc } from './revisionUtc';

export function RevisionDetails({ record, association }: ReadRecord) {
  const { time, provenance, author, payload } = record;
  return (
    <div className="space-y-1 text-sm">
      <p>
        Actual start: {revisionUtc(time.occurred_at)} · precision:{' '}
        {time.precision}
      </p>
      <p>
        Actual end: {revisionUtc(time.ended_at)} · end state: {time.end_state}
      </p>
      {payload.entry_type === 'call' && (
        <>
          <p>
            Party / participant: {payload.party ?? 'Unknown'} · Coordinator:{' '}
            {payload.coordinator ?? 'Unknown'}
          </p>
          <p>
            Call status: {payload.status} · Type:{' '}
            {payload.communications_kind ?? 'Unknown'} · Preparation lead:{' '}
            {payload.prep_lead_minutes == null
              ? 'Unknown'
              : `${payload.prep_lead_minutes} minutes`}
          </p>
          <p>Conference: {payload.conference_id ?? 'None'}</p>
        </>
      )}
      {payload.entry_type === 'conference' && (
        <>
          <p>
            Conference state: {payload.status ?? 'Unknown'} · Operator
            verification: {revisionUtc(payload.verified_at ?? null)}
          </p>
          <p>
            Intended transport: {payload.intended_transport ?? 'Unknown'} ·
            Operator-reported configuration:{' '}
            {payload.configured_transport ?? 'Unknown'} · Configuration
            reported: {revisionUtc(payload.configuration_reported_at ?? null)}
          </p>
        </>
      )}
      {payload.entry_type === 'participation' && (
        <>
          <p>
            Customer state: {payload.state ?? 'Unknown'} · Participant:{' '}
            {payload.participant ?? 'Unknown'}
          </p>
          <p>
            Call: {payload.call_id ?? 'Unassigned'} · Conference:{' '}
            {payload.conference_id ?? 'Unassigned'} · Restored from interval:{' '}
            {payload.resumes_participation_id ?? 'None'}
          </p>
        </>
      )}
      <p>Planned start: {revisionUtc(time.planned_start_at)}</p>
      <p>Planned end: {revisionUtc(time.planned_end_at)}</p>
      <p>
        Scope: {record.scope} · Mission: {record.mission_id} · Leg:{' '}
        {record.leg_id ?? 'None'}
      </p>
      <p>
        Previous leg: {payload.previous_leg_id ?? 'None'} · Next leg:{' '}
        {payload.next_leg_id ?? 'None'}
      </p>
      <p>
        Association: {association.status}
        {association.unresolved_fields.length > 0 &&
          ` · Unresolved: ${association.unresolved_fields.join(', ')}`}
        {association.error_code && ` · ${association.error_code}`}
      </p>
      <p>
        Author: {author.operator_label ?? 'Unlabeled operator'} ·{' '}
        {author.backend}
      </p>
      <p>
        Provenance: {provenance.kind} · {provenance.source_mode} ·{' '}
        {provenance.mutation_origin}
      </p>
      {(provenance.observed_at || provenance.predicted_at) && (
        <p>
          Observed: {revisionUtc(provenance.observed_at)} · Predicted:{' '}
          {revisionUtc(provenance.predicted_at)}
        </p>
      )}
      {provenance.source_ref && (
        <p>
          Source: {provenance.source_ref.producer_id} · Record:{' '}
          {provenance.source_ref.record_id ?? 'Unknown'} · Revision:{' '}
          {provenance.source_ref.revision ?? 'Unknown'} · Fingerprint:{' '}
          {provenance.source_ref.fingerprint ?? 'Unknown'}
        </p>
      )}
      <p>
        Entry type: {payload.entry_type} ·{' '}
        {record.deleted ? 'Removed' : 'Present'}
      </p>
    </div>
  );
}
