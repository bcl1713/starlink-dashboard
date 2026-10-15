import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type {
  PlanningManifest,
  PlanningProposal,
  PlanningView,
} from '../../types/planning';
import {
  usePlanningMissionController,
  usePlanningEditEpoch,
} from '../../hooks/usePlanningMissionController';
import { planningSourceReady } from '../../services/planning-prerequisites';
import { planningApi, planningErrorMessage } from '../../services/planning';
import { currentLeg } from '../../services/planning-mutations';
import { createClientId } from '../../lib/clientId';
import { ProposalComparison } from './ProposalComparison';
import { Button } from '../ui/button';

export function ItineraryPlans({ view }: { view: PlanningView }) {
  const missionId = view.mission.id;
  const controller = usePlanningMissionController(missionId);
  usePlanningEditEpoch(controller);
  const [generated, setGenerated] = useState<Record<string, PlanningProposal>>(
    {}
  );
  const [progress, setProgress] = useState<Record<string, string>>({});
  const [deselected, setDeselected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const application = useRef<{ signature: string; key: string } | null>(null);
  const cards = view.expected_legs.filter((card) => !card.leg.retired);
  const manifest = view.mission.metadata?.itinerary_planning as
    | PlanningManifest
    | undefined;
  const refs = cards.flatMap((card) => {
    const ref = manifest?.proposal_refs
      ?.filter((ref) => ref.leg_id === card.leg.id)
      .at(-1);
    return ref ? [ref] : [];
  });
  const restored = useQuery({
    queryKey: [
      'itinerary-proposals',
      missionId,
      view.revision,
      refs.map((ref) => ref.id).join(','),
      cards.map((card) => card.computation_status).join(','),
    ],
    queryFn: async () => {
      const values = await Promise.all(
        refs.map(
          async (ref) =>
            [
              ref.leg_id,
              await planningApi.readProposal(missionId, ref.leg_id, ref.id),
            ] as const
        )
      );
      return Object.fromEntries(values);
    },
    retry: false,
  });
  const proposals: Record<string, PlanningProposal> = {
    ...generated,
    ...restored.data,
  };
  for (const card of cards) {
    const proposal = proposals[card.leg.id];
    if (!proposal) continue;
    const ref = refs.find(
      (ref) => ref.leg_id === card.leg.id && ref.id === proposal.id
    );
    if (ref?.state === 'applied')
      proposals[card.leg.id] = {
        ...proposal,
        state: 'applied',
        applied_input_identity: ref.applied_input_identity,
      };
    const current = proposals[card.leg.id];
    if (
      card.computation_status === 'stale' ||
      (current.applied_input_identity ?? current.input_identity) !==
        card.input_identity
    )
      proposals[card.leg.id] = { ...current, state: 'stale' };
  }
  const ready =
    !controller.hasLocalEdits(cards.map((card) => card.leg.id)) &&
    cards.length > 0 &&
    cards.every(
      (card) => planningSourceReady(card.leg) && !card.errors?.length
    );
  const targets = cards.filter(
    (card) =>
      !proposals[card.leg.id] ||
      ['stale', 'failed'].includes(proposals[card.leg.id].state)
  );
  const failures = cards.filter((card) =>
    progress[card.leg.id]?.startsWith('failed')
  );
  const selected = cards.filter(
    (card) =>
      proposals[card.leg.id]?.state === 'ready' &&
      !deselected.includes(card.leg.id)
  );
  const generate = async (ids: string[]) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      for (const legId of ids) {
        setProgress((current) => ({ ...current, [legId]: 'generating' }));
        try {
          const result = await controller.enqueueMutation(
            async (current) => {
              controller.requireSavedSources([legId]);
              const card = currentLeg(current, legId);
              if (!planningSourceReady(card.leg))
                throw new Error(
                  'Complete source review before generating plans'
                );
              const proposal = await planningApi.generateProposal(
                missionId,
                legId,
                {
                  expected_revision: current.revision,
                  input_identity: card.input_identity,
                }
              );
              return { proposal, view: await planningApi.read(missionId) };
            },
            (result) => result.view
          );
          const current = result.view.expected_legs.find(
            (card) => card.leg.id === legId
          );
          const proposal =
            current?.input_identity === result.proposal.input_identity
              ? result.proposal
              : { ...result.proposal, state: 'stale' as const };
          setGenerated((current) => ({ ...current, [legId]: proposal }));
          setProgress((current) => ({ ...current, [legId]: proposal.state }));
        } catch (failure) {
          setProgress((current) => ({
            ...current,
            [legId]: `failed — ${planningErrorMessage(failure)}`,
          }));
        }
      }
    } finally {
      setBusy(false);
    }
  };
  const apply = async () => {
    if (!selected.length) return;
    setBusy(true);
    setError('');
    const entries = selected.map((card) => ({
      leg_id: card.leg.id,
      proposal_id: proposals[card.leg.id].id,
      input_identity: proposals[card.leg.id].input_identity,
    }));
    const signature = JSON.stringify(entries);
    if (application.current?.signature !== signature)
      application.current = { signature, key: createClientId() };
    const idempotencyKey = application.current!.key;
    try {
      const saved = await controller.enqueueMutation(
        (current) => {
          controller.requireSavedSources(selected.map((card) => card.leg.id));
          return planningApi.applyProposals(missionId, {
            expected_revision: current.revision,
            entries,
            idempotency_key: idempotencyKey,
          });
        },
        (result) => result
      );
      setGenerated((current) => ({
        ...current,
        ...Object.fromEntries(
          selected.map((card) => [
            card.leg.id,
            {
              ...proposals[card.leg.id],
              state: 'applied',
              applied_input_identity: saved.expected_legs.find(
                (item) => item.leg.id === card.leg.id
              )?.input_identity,
            },
          ])
        ),
      }));
      setMessage(
        'Selected plans applied to saved drafts. Continue to final review.'
      );
    } catch (failure) {
      setError(planningErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section
      aria-label="Itinerary plans"
      className="space-y-4 rounded border p-4"
    >
      <h2 className="font-semibold">Generate and compare plans</h2>
      {!ready && (
        <p>
          Review all attached AR or no-AR inputs and satellite access before
          generating this itinerary.
        </p>
      )}
      <Button
        onClick={() => void generate(targets.map((card) => card.leg.id))}
        disabled={busy || !ready || !targets.length}
      >
        {cards.some((card) => proposals[card.leg.id])
          ? 'Re-optimize changed plans'
          : 'Generate plans'}
      </Button>
      {!!failures.length && (
        <Button
          variant="outline"
          onClick={() => void generate(failures.map((card) => card.leg.id))}
          disabled={busy || !ready}
        >
          Retry failed legs
        </Button>
      )}
      {cards.map((card) => (
        <div key={card.leg.id} className="space-y-2">
          <p role="status">
            Leg {card.leg.ordinal}:{' '}
            {progress[card.leg.id] ??
              proposals[card.leg.id]?.state ??
              'not generated'}
          </p>
          {proposals[card.leg.id] && (
            <>
              <ProposalComparison proposal={proposals[card.leg.id]} />
              {proposals[card.leg.id].state === 'ready' && (
                <label className="flex min-h-11 items-center gap-2">
                  <input
                    type="checkbox"
                    aria-label={`Select Leg ${card.leg.ordinal} proposal`}
                    checked={!deselected.includes(card.leg.id)}
                    onChange={(event) =>
                      setDeselected((current) =>
                        event.target.checked
                          ? current.filter((id) => id !== card.leg.id)
                          : [...current, card.leg.id]
                      )
                    }
                  />
                  Select Leg {card.leg.ordinal} proposal
                </label>
              )}
            </>
          )}
        </div>
      ))}
      {restored.error && (
        <p role="alert">
          Unable to restore saved proposals. Reload before applying.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <Button
        onClick={() => void apply()}
        disabled={busy || !ready || !selected.length}
      >
        Apply selected plans
      </Button>
    </section>
  );
}
