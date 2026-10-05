import {
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import {
  simulationRunApi,
  type SimulationRunStatus,
} from '@/services/simulation-run';

export function createRunResponseGuard() {
  let generation = 0,
    acceptedSequence = 0;
  let confirmed: SimulationRunStatus | undefined;
  const retired = new Set<string>();
  function install(status: SimulationRunStatus) {
    if (confirmed && confirmed.runtime_id !== status.runtime_id)
      retired.add(confirmed.runtime_id);
    confirmed = status;
  }
  return {
    beginRequest: () => ++generation,
    accept(sequence: number, status: SimulationRunStatus) {
      if (
        sequence < generation ||
        sequence < acceptedSequence ||
        retired.has(status.runtime_id)
      )
        return null;
      if (
        confirmed?.runtime_id === status.runtime_id &&
        status.revision < confirmed.revision
      )
        return null;
      acceptedSequence = sequence;
      install(status);
      return status;
    },
    confirmMutation(status: SimulationRunStatus) {
      generation++;
      acceptedSequence = generation;
      install(status);
    },
  };
}
const guards = new WeakMap<
  QueryClient,
  ReturnType<typeof createRunResponseGuard>
>();
export function runResponseGuard(client: QueryClient) {
  let guard = guards.get(client);
  if (!guard) {
    guard = createRunResponseGuard();
    guards.set(client, guard);
  }
  return guard;
}
export function confirmSimulationRun(
  client: QueryClient,
  status: SimulationRunStatus
) {
  runResponseGuard(client).confirmMutation(status);
  client.setQueryData(['simulation-run'], status);
}
export function useSimulationRun() {
  const client = useQueryClient();
  return useQuery({
    queryKey: ['simulation-run'],
    queryFn: async ({ signal }) => {
      const guard = runResponseGuard(client),
        sequence = guard.beginRequest();
      const response = await simulationRunApi.get(signal);
      const accepted = guard.accept(sequence, response);
      if (accepted) return accepted;
      const current = client.getQueryData<SimulationRunStatus>([
        'simulation-run',
      ]);
      if (current) return current;
      throw new Error('Obsolete simulation response');
    },
    refetchInterval: 1000,
    networkMode: 'always',
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: 'always',
    refetchOnReconnect: 'always',
    retry: false,
    structuralSharing: false,
  });
}
export function useSimulationRunRoute(status: SimulationRunStatus | undefined) {
  const selected =
    status && ['running', 'completed'].includes(status.state)
      ? status.run
      : null;
  return useQuery({
    queryKey: ['simulation-run-route', status?.runtime_id, selected?.run_id],
    queryFn: ({ signal }) => simulationRunApi.route(selected!.run_id, signal),
    enabled: Boolean(selected),
    staleTime: Infinity,
    retry: false,
  });
}
