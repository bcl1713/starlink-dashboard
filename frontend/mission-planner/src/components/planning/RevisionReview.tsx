import { useState } from 'react';
import type {
  ApplyRevision,
  CorrectionResolution,
  PlanningView,
  RevisionLegMapping,
  RevisionPreview,
} from '../../types/planning';
import { planningErrorMessage } from '../../services/planning';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

/** Captures preview CAS and individual mapping/correction choices until explicit apply. */
export function RevisionReview({
  view,
  previewRevision,
  applyRevision,
}: {
  view: PlanningView;
  previewRevision: (file: File, revision: number) => Promise<RevisionPreview>;
  applyRevision: (request: ApplyRevision) => Promise<PlanningView>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<RevisionPreview | null>(null);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [resolutions, setResolutions] = useState<
    Record<string, CorrectionResolution['action']>
  >({});
  const [confirmed, setConfirmed] = useState(false);
  const [lower, setLower] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const reset = () => {
    setPreview(null);
    setConfirmed(false);
    setResolutions({});
    setLower(false);
    setError('');
  };
  const stage = async () => {
    if (!file) return;
    setPending(true);
    setError('');
    setMessage('');
    try {
      const staged = await previewRevision(file, view.revision);
      setPreview(staged);
      setConfirmed(false);
      setResolutions({});
      setLower(false);
      setMappings(
        Object.fromEntries(
          (staged.leg_mappings ?? [])
            .filter((m) => m.action !== 'retire')
            .map((m) => [
              m.incoming_leg_id,
              m.action === 'add' ? 'add' : (m.expected_leg_id ?? ''),
            ])
        )
      );
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setPending(false);
    }
  };
  const incoming = preview?.parsed_values?.expected_legs ?? [];
  const selected = incoming
    .map((leg) => mappings[leg.id])
    .filter((id) => id && id !== 'add');
  const conflicts = (preview?.conflicts ?? []).filter(
    (issue) =>
      !issue.expected_leg_id ||
      incoming.some(
        (leg) =>
          mappings[leg.id] === issue.expected_leg_id &&
          issue.id.startsWith(`${issue.expected_leg_id}:${leg.id}:`)
      )
  );
  const complete =
    incoming.every((leg) => !!mappings[leg.id]) &&
    new Set(selected).size === selected.length;
  const apply = async () => {
    if (!preview) return;
    const leg_mappings: RevisionLegMapping[] = incoming.map((leg) => ({
      incoming_leg_id: leg.id,
      expected_leg_id: mappings[leg.id] === 'add' ? null : mappings[leg.id],
      action: mappings[leg.id] === 'add' ? 'add' : 'retain',
    }));
    for (const card of view.expected_legs)
      if (!selected.includes(card.leg.id))
        leg_mappings.push({
          incoming_leg_id: '',
          expected_leg_id: card.leg.id,
          action: 'retire',
        });
    setPending(true);
    setError('');
    try {
      await applyRevision({
        preview_id: preview.preview_id,
        expected_revision: preview.expected_revision,
        input_identity: preview.input_identity,
        leg_mappings,
        allow_lower_revision: lower,
        correction_resolutions: conflicts.map((issue) => ({
          conflict_id: issue.id,
          action: resolutions[issue.id],
        })),
      });
      reset();
      setMessage(
        preview.identical_content
          ? 'Identical source; no changes.'
          : 'Itinerary revision accepted. Review changed drafts before saving executable plans.'
      );
    } catch (e) {
      setError(planningErrorMessage(e));
    } finally {
      setPending(false);
    }
  };
  return (
    <fieldset
      disabled={pending}
      className="min-w-0 space-y-3 rounded-xl border p-4"
      aria-label="Itinerary revision"
    >
      <h2>Update itinerary</h2>
      <label>
        Revised itinerary PDF
        <Input
          type="file"
          accept=".pdf,application/pdf"
          aria-label="Revised itinerary PDF"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            reset();
          }}
        />
      </label>
      <Button onClick={stage} disabled={!file || pending}>
        Preview itinerary revision
      </Button>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {preview && (
        <div className="space-y-3">
          <p>
            Source: {preview.source?.filename} · Revision{' '}
            {preview.parsed_values?.itinerary_revision ?? 'unknown'}
          </p>
          {(!preview.accepted_metadata ||
            preview.previous_source_revision == null) && (
            <p>
              Prior mission metadata comparison is incomplete. Accepted values
              are retained when the source baseline is unavailable.
            </p>
          )}
          {(preview.field_errors ?? []).map((issue, index) => (
            <p role="alert" key={index}>
              {issue.message}
            </p>
          ))}
          {preview.identical_content ? (
            <p>Identical source; applying will make no changes.</p>
          ) : (
            <>
              {(preview.changes ?? [])
                .filter(
                  (change) =>
                    !change.incoming_leg_id ||
                    mappings[change.incoming_leg_id] === change.expected_leg_id
                )
                .map((change, index) => (
                  <p key={index}>
                    {change.field}: {change.before} → {change.after}
                  </p>
                ))}
              {incoming.map((leg) => (
                <label key={leg.id} className="block">
                  Map incoming leg {leg.ordinal}: {leg.departure_airport} →{' '}
                  {leg.arrival_airport}
                  <select
                    aria-label={`Map incoming leg ${leg.ordinal}`}
                    value={mappings[leg.id] ?? ''}
                    onChange={(e) => {
                      setMappings({ ...mappings, [leg.id]: e.target.value });
                      setConfirmed(false);
                    }}
                  >
                    <option value="">Choose mapping</option>
                    <option value="add">Add new expected leg</option>
                    {view.expected_legs.map((card) => (
                      <option key={card.leg.id} value={card.leg.id}>
                        Retain leg {card.leg.ordinal}:{' '}
                        {card.leg.departure_airport} →{' '}
                        {card.leg.arrival_airport}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              {view.expected_legs
                .filter((c) => !selected.includes(c.leg.id))
                .map((c) => (
                  <p key={c.leg.id}>
                    Retire leg {c.leg.ordinal}; retain its plan and source
                    history.
                  </p>
                ))}
              {conflicts.map((issue) => (
                <label className="block" key={issue.id}>
                  {issue.message}
                  <select
                    aria-label={issue.message}
                    value={resolutions[issue.id] ?? ''}
                    onChange={(e) =>
                      setResolutions({
                        ...resolutions,
                        [issue.id]: e.target
                          .value as CorrectionResolution['action'],
                      })
                    }
                  >
                    <option value="">Resolve this conflict</option>
                    <option value="retain">
                      Retain existing correction and review
                    </option>
                    {(issue.allowed_actions?.includes('use_source') ??
                      !['manual_work', 'source_baseline'].includes(
                        issue.field
                      )) && (
                      <option value="use_source">
                        Use incoming source values
                      </option>
                    )}
                    {(issue.allowed_actions?.includes('remove') ??
                      issue.field === 'ar_rows') && (
                      <option value="remove">Remove this correction</option>
                    )}
                  </select>
                </label>
              ))}
              <label className="block">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                I confirm the complete leg mapping
              </label>
            </>
          )}
          {preview.lower_revision && (
            <label className="block">
              <input
                type="checkbox"
                checked={lower}
                onChange={(e) => setLower(e.target.checked)}
              />
              Allow lower source revision
            </label>
          )}
          <Button variant="outline" onClick={reset}>
            Cancel revision
          </Button>
          <Button
            onClick={apply}
            disabled={
              pending ||
              (!preview.identical_content &&
                (!preview.confirmable ||
                  !confirmed ||
                  !complete ||
                  conflicts.some((issue) => !resolutions[issue.id]))) ||
              (preview.lower_revision && !lower)
            }
          >
            Apply itinerary revision
          </Button>
        </div>
      )}
    </fieldset>
  );
}
