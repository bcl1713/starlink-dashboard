import { useTransportAvailability } from '@/hooks/api/useTransportAvailability';
import { legAvailability } from '@/services/transportAvailability';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { PlanningView } from '../../types/planning';
import {
  usePlanningMissionController,
  usePlanningEditEpoch,
} from '../../hooks/usePlanningMissionController';
import { planningSourceReady } from '../../services/planning-prerequisites';
import { planningApi, planningErrorMessage } from '../../services/planning';
import { currentLeg } from '../../services/planning-mutations';
import { createClientId } from '../../lib/clientId';
import { Button } from '../ui/button';

export function ItineraryFinalReview({ view }: { view: PlanningView }) {
  const missionId = view.mission.id;
  const availability = useTransportAvailability(missionId);
  const xAvailable = (id: string) => {
    const row = legAvailability(availability.data, id);
    return row?.x_configuration_required ?? row?.planned.X !== false;
  };
  const controller = usePlanningMissionController(missionId);
  usePlanningEditEpoch(controller);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [planApproval, setPlanApproval] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const retry = useRef<{ signature: string; key: string } | null>(null);
  const cards = view.expected_legs.filter(
    (card) => !card.leg.retired && card.review_status !== 'reviewed'
  );
  const selected = cards.filter((card) => !excluded.includes(card.leg.id));
  const selectedIds = selected.map((card) => card.leg.id);
  const unsaved = controller.hasLocalEdits(selectedIds);
  const editEpoch = controller.localEditIdentity(selectedIds);
  const inputs = selected
    .map((card) => `${card.leg.id}:${card.input_identity}`)
    .join('|');
  const eligible =
    selected.length > 0 &&
    selected.every(
      (card) =>
        planningSourceReady(
          card.leg,
          card.leg.draft ?? {},
          card.leg.ar_section_status,
          xAvailable(card.leg.id)
        ) &&
        (!xAvailable(card.leg.id) || !!card.leg.draft?.initial_x_satellite_id)
    );
  const preview = useQuery({
    queryKey: [
      'itinerary-final-review',
      missionId,
      view.revision,
      inputs,
      editEpoch,
    ],
    enabled: eligible && !unsaved,
    queryFn: async ({ signal }) =>
      Object.fromEntries(
        await Promise.all(
          selected.map(
            async (card) =>
              [
                card.leg.id,
                await planningApi.previewDraft(
                  missionId,
                  card.leg.id,
                  {
                    expected_revision: view.revision,
                    input_identity: card.input_identity,
                    draft: card.leg.draft!,
                    ar_section_status: card.leg.ar_section_status,
                  },
                  signal
                ),
              ] as const
          )
        )
      ),
    retry: false,
  });
  const signature =
    inputs +
    `:${editEpoch}:` +
    JSON.stringify(
      selected.map(
        (card) => preview.data?.[card.leg.id]?.context.input_identity ?? null
      )
    );
  const missing = selected.some((card) => !preview.data?.[card.leg.id]);
  const blocked = selected.some((card) => {
    const evaluation = preview.data?.[card.leg.id];
    return evaluation?.errors?.length || evaluation?.map_diagnostics?.length;
  });
  const publish = async () => {
    if (
      unsaved ||
      !eligible ||
      missing ||
      blocked ||
      planApproval !== signature
    )
      return;
    setBusy(true);
    setError('');
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: createClientId() };
    const idempotencyKey = retry.current!.key;
    try {
      await controller.enqueueMutation(
        (current) => {
          controller.requireSavedSources(selected.map((card) => card.leg.id));
          const entries = selected.map((card) => {
            const latest = currentLeg(
              current,
              card.leg.id,
              card.input_identity
            );
            const draft = latest.leg.draft!;
            const rows = draft.ar_corrections?.length
              ? draft.ar_corrections
              : (latest.leg.ar_rows ?? []);
            return {
              leg_id: latest.leg.id,
              review: {
                expected_revision: current.revision,
                input_identity: latest.input_identity,
                evaluation_identity:
                  preview.data![card.leg.id].context.input_identity,
                satellite_plan_confirmed: true,
                no_ars_confirmed: draft.no_ars_confirmed ?? false,
                confirmed_ar_ids: rows
                  .filter((row) => row.match_status !== 'excluded')
                  .map((row) => row.id),
                excluded_ar_ids: rows
                  .filter((row) => row.match_status === 'excluded')
                  .map((row) => row.id),
              },
            };
          });
          return planningApi.publishReviewed(missionId, {
            expected_revision: current.revision,
            entries,
            idempotency_key: idempotencyKey,
          });
        },
        (result) => result
      );
      setMessage('Reviewed plans published together as inactive legs.');
    } catch (failure) {
      setError(planningErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  return (
    <fieldset
      disabled={busy}
      aria-label="Itinerary final review"
      className="space-y-3 rounded border p-4"
    >
      <legend className="font-semibold">Final itinerary review</legend>
      {!cards.length && (
        <p>
          All current itinerary legs are already reviewed. Existing approvals
          are retained.
        </p>
      )}
      {unsaved && (
        <p role="status">Save or resolve source edits before final review.</p>
      )}
      {!eligible && !!cards.length && (
        <p>
          Complete source review and apply the selected satellite plans before
          publication.
        </p>
      )}
      {cards.map((card) => {
        const evaluation = preview.data?.[card.leg.id];
        const rows = card.leg.draft?.ar_corrections?.length
          ? card.leg.draft.ar_corrections
          : (card.leg.ar_rows ?? []);
        return (
          <section key={card.leg.id} className="space-y-2 rounded border p-3">
            <label className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                aria-label={`Publish Leg ${card.leg.ordinal}`}
                checked={!excluded.includes(card.leg.id)}
                onChange={(event) =>
                  setExcluded((current) =>
                    event.target.checked
                      ? current.filter((id) => id !== card.leg.id)
                      : [...current, card.leg.id]
                  )
                }
              />
              Leg {card.leg.ordinal}: {card.leg.departure_airport} →{' '}
              {card.leg.arrival_airport}
            </label>
            <p>
              {rows.filter((row) => row.match_status !== 'excluded').length}{' '}
              reviewed AR windows ·{' '}
              {card.leg.draft?.no_ars_confirmed
                ? 'No ARs confirmed'
                : 'AR intervals confirmed'}{' '}
              · Initial X-band{' '}
              {xAvailable(card.leg.id)
                ? (card.leg.draft?.initial_x_satellite_id ?? 'not applied')
                : 'unavailable for this leg'}{' '}
              · Starshield{' '}
              {(legAvailability(availability.data, card.leg.id)?.planned.Ku ??
              card.leg.draft?.starshield_enabled ??
              true)
                ? 'available'
                : 'unavailable'}
            </p>
            {evaluation && (
              <p>
                Leg {card.leg.ordinal}: {evaluation.outage_seconds} seconds of
                X-band outage
              </p>
            )}
            {evaluation?.backup_gaps?.map((gap, index) => (
              <p key={index} className="break-words">
                Backup gap UTC: {gap.start_time} → {gap.end_time}
                {gap.reasons?.length ? ` · ${gap.reasons.join(', ')}` : ''}
              </p>
            ))}
            {[
              ...(evaluation?.errors ?? []),
              ...(evaluation?.map_diagnostics ?? []),
            ].map((issue, index) => (
              <p role="alert" key={index}>
                {issue.message}
              </p>
            ))}
          </section>
        );
      })}
      {preview.isFetching && (
        <p role="status">Checking canonical timelines and customer maps…</p>
      )}
      {preview.error && (
        <p role="alert">{planningErrorMessage(preview.error)}</p>
      )}
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          aria-label="I approve the selected satellite plans and Starshield settings"
          disabled={unsaved || preview.isFetching || missing}
          checked={planApproval === signature}
          onChange={(event) =>
            setPlanApproval(event.target.checked ? signature : '')
          }
        />
        I approve the selected satellite plans and Starshield settings
      </label>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <Button
        onClick={() => void publish()}
        disabled={
          busy ||
          unsaved ||
          !eligible ||
          missing ||
          blocked ||
          !!preview.error ||
          preview.isFetching ||
          planApproval !== signature
        }
      >
        Publish reviewed plans
      </Button>
    </fieldset>
  );
}
