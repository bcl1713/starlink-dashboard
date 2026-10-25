import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createClientId } from '@/lib/clientId';
import {
  transportAvailabilityApi,
  type AvailabilityView,
  type AvailabilityCommand,
  type AvailabilityAction,
  type PlannedAvailabilityUpdate,
} from '@/services/transportAvailability';
type Intent =
  | { kind: 'planned'; value: PlannedAvailabilityUpdate }
  | { kind: 'action'; value: AvailabilityAction };
export function useTransportAvailability(missionId: string) {
  const client = useQueryClient();
  const key = ['transport-availability', missionId];
  const query = useQuery({
    queryKey: key,
    queryFn: async ({ signal }) => {
      const received = await transportAvailabilityApi.read(missionId, signal);
      const saved = client.getQueryData<AvailabilityView>(key);
      return saved && saved.revision > received.revision ? saved : received;
    },
    enabled: !!missionId,
    retry: false,
    refetchInterval: 10_000,
  });
  // An uncertain network outcome may already have committed. Keep its receipt
  // and original revision for an explicit retry of the same intent.
  const receipt = useRef<{
    identity: string;
    command: AvailabilityCommand;
  } | null>(null);
  const busy = useRef(false);
  const receive = async (view: AvailabilityView) => {
    await client.cancelQueries({ queryKey: key });
    const saved = client.getQueryData<AvailabilityView>(key);
    if (!saved || view.revision >= saved.revision)
      client.setQueryData(key, view);
  };
  const invalidate = async () => {
    await Promise.all([
      ...[
        'missions',
        'timeline',
        'pois',
        'status',
        'active-x-link',
        'overview-upcoming-pois',
        'operator-events',
        'operator-protection',
        'operator-brief',
      ].map((name) => client.invalidateQueries({ queryKey: [name] })),
      client.invalidateQueries({ queryKey: ['planning', missionId] }),
      client.invalidateQueries({ queryKey: key }),
    ]);
  };
  const mutation = useMutation({
    retry: false,
    mutationFn: async (intent: Intent) => {
      if (busy.current)
        throw new Error('An availability command is already saving.');
      const confirmed = client.getQueryData<AvailabilityView>(key);
      if (!confirmed || query.isError)
        throw new Error('Refresh availability before saving.');
      if (intent.kind === 'action' && !confirmed.operator_actions_allowed)
        throw new Error(
          confirmed.operator_actions_unavailable_reason ??
            'Mission actions are unavailable.'
        );
      busy.current = true;
      const expectedRun = confirmed.simulation_run_id;
      const identity = JSON.stringify([
        missionId,
        intent,
        intent.kind === 'action' ? expectedRun : null,
      ]);
      if (receipt.current?.identity !== identity)
        receipt.current = {
          identity,
          command: {
            expected_revision: confirmed.revision,
            command_id: createClientId(),
          },
        };
      const command = receipt.current.command;
      try {
        const response =
          intent.kind === 'planned'
            ? await transportAvailabilityApi.update(missionId, {
                ...command,
                ...intent.value,
              })
            : await transportAvailabilityApi.action(missionId, {
                ...command,
                ...intent.value,
                expected_simulation_run_id: expectedRun,
              });
        if (intent.kind === 'action') {
          const current = await transportAvailabilityApi.read(missionId);
          await receive(current);
          if (
            current.simulation_run_id !== expectedRun ||
            response.simulation_run_id !== expectedRun ||
            client.getQueryData<AvailabilityView>(key)?.simulation_run_id !==
              expectedRun
          ) {
            receipt.current = null;
            throw new Error(
              'Mission run changed; refresh availability before recording an action.'
            );
          }
          await receive(
            response.revision > current.revision ? response : current
          );
        } else await receive(response);
        receipt.current = null;
        await invalidate();
        if (
          intent.kind === 'action' &&
          client.getQueryData<AvailabilityView>(key)?.simulation_run_id !==
            expectedRun
        )
          throw new Error(
            'Mission run changed; refresh availability before recording an action.'
          );
        return response;
      } catch (error) {
        if (
          (error as { response?: { status?: number } }).response?.status === 409
        )
          receipt.current = null;
        try {
          await receive(await transportAvailabilityApi.read(missionId));
        } catch {
          /* Keep last confirmed state. */
        }
        await invalidate();
        throw error;
      } finally {
        busy.current = false;
      }
    },
  });
  return {
    ...query,
    isSaving: mutation.isPending,
    savePlanned: (value: PlannedAvailabilityUpdate) =>
      mutation.mutateAsync({ kind: 'planned', value }),
    act: (value: AvailabilityAction) =>
      mutation.mutateAsync({ kind: 'action', value }),
  };
}
