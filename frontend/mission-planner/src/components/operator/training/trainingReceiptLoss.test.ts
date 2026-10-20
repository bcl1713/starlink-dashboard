import { afterEach, expect, it, vi } from 'vitest';
import type { InternalAxiosRequestConfig } from 'axios';
import apiClient from '@/services/api-client';
import { health, input } from '@/test/operator-fixtures';
import { armPrivateReceiptLoss } from './trainingReceiptLoss';
const identity = {
  origin: 'http://private',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const original = apiClient.defaults.adapter;
const stops: AbortController[] = [];
afterEach(() => {
  stops.forEach((controller) => controller.abort());
  stops.length = 0;
  apiClient.defaults.adapter = original;
  vi.useRealTimers();
});
function backend(privateRoot = true) {
  const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
    config,
    status: 200,
    statusText: 'OK',
    headers: {},
    data: config.url?.endsWith('/health')
      ? {
          ...health,
          source_mode: privateRoot ? 'simulation' : 'live',
          simulation_run_id: privateRoot ? namespace : null,
        }
      : config.url?.startsWith('/api/v2/missions/')
        ? {
            id: 'mission-a',
            metadata: {
              operator_training_fixture: {
                version: 1,
                namespace,
                prerequisite_record_ids: [],
              },
            },
          }
        : { nativeReceipt: 'untouched' },
  }));
  apiClient.defaults.adapter = adapter;
  return adapter;
}
async function arm() {
  const controller = new AbortController();
  stops.push(controller);
  const done = vi.fn();
  await armPrivateReceiptLoss(identity, controller.signal, done);
  return { controller, done };
}
const note = (mission_id = 'mission-a') =>
  apiClient.post(
    '/api/v2/operator/records',
    { ...input, mission_id },
    {
      headers: {
        'X-Operator-Store-Epoch': 'epoch-a',
        'Idempotency-Key': 'original-key',
      },
    }
  );
it('withholds exactly one matching private note response after its normal HTTP request, then leaves retry responses unchanged', async () => {
  const adapter = backend();
  const { done } = await arm();
  expect((await note('other-mission')).data).toEqual({
    nativeReceipt: 'untouched',
  });
  await expect(note()).rejects.toThrow(/withheld/);
  expect(done).toHaveBeenCalledTimes(1);
  expect((await note()).data).toEqual({ nativeReceipt: 'untouched' });
  expect(adapter).toHaveBeenCalledTimes(5);
});
it('refuses operational or mismatched stores before installing an exercise', async () => {
  backend(false);
  await expect(arm()).rejects.toThrow(/marked private/);
  expect((await note()).data).toEqual({ nativeReceipt: 'untouched' });
});
it('disarms on cancellation and after sixty seconds', async () => {
  vi.useFakeTimers();
  backend();
  const first = await arm();
  first.controller.abort();
  expect((await note()).data).toEqual({ nativeReceipt: 'untouched' });
  const second = await arm();
  await vi.advanceTimersByTimeAsync(60_000);
  expect(second.done).toHaveBeenCalledWith('expired');
  expect((await note()).data).toEqual({ nativeReceipt: 'untouched' });
});
