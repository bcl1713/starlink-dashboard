import { expect, it, vi, afterEach } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createRunResponseGuard, useSimulationRun } from './useSimulationRun';
import { runningStatus } from '@/test/simulation-run-fixtures';
import { simulationRunApi } from '@/services/simulation-run';
afterEach(cleanup);
it('ignores obsolete reads, retired incarnations and decreasing revisions', () => {
  const guard = createRunResponseGuard();
  const old = guard.beginRequest();
  guard.confirmMutation({ ...runningStatus(), revision: 4 });
  expect(guard.accept(old, runningStatus())).toBeNull();
  expect(
    guard.accept(guard.beginRequest(), { ...runningStatus(), revision: 3 })
  ).toBeNull();
  expect(
    guard.accept(guard.beginRequest(), {
      ...runningStatus(),
      runtime_id: 'new-runtime',
      revision: 0,
    })
  ).not.toBeNull();
  expect(
    guard.accept(guard.beginRequest(), { ...runningStatus(), revision: 100 })
  ).toBeNull();
});
it('rejects an older same-runtime response after a new request', () => {
  const guard = createRunResponseGuard();
  const old = guard.beginRequest(),
    fresh = guard.beginRequest();
  expect(guard.accept(fresh, runningStatus())).not.toBeNull();
  expect(guard.accept(old, { ...runningStatus(), revision: 4 })).toBeNull();
});
it('two consumers share a cancellable background polling query', async () => {
  const read = vi
    .spyOn(simulationRunApi, 'get')
    .mockResolvedValue(runningStatus());
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Consumer() {
    const query = useSimulationRun();
    return <span>{query.data?.state}</span>;
  }
  const view = render(
    <QueryClientProvider client={client}>
      <Consumer />
      <Consumer />
    </QueryClientProvider>
  );
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  expect(read.mock.calls[0][0]).toBeInstanceOf(AbortSignal);
  const query = client.getQueryCache().find({ queryKey: ['simulation-run'] });
  expect(query?.options).toMatchObject({
    refetchInterval: 1000,
    refetchIntervalInBackground: true,
    retry: false,
    networkMode: 'always',
  });
  view.unmount();
  client.clear();
  read.mockRestore();
});
// @vitest-environment jsdom
