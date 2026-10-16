import assert from 'node:assert/strict';
import { test } from 'node:test';
import { sampleWhileRendering } from './pop-replay-sampler.mjs';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test('slow UI keeps collecting adjacent HTTP publications independently', async () => {
  const samples = [],
    receipt = {};
  let nextRevision = 0;
  const captured = Promise.withResolvers();
  const deadline = setTimeout(
    () =>
      captured.reject(new Error('UI delay starved independent HTTP samples')),
    1000
  );
  try {
    await sampleWhileRendering({
      samples,
      receipt,
      intervalMs: 2,
      limitMs: 1000,
      read: async () => {
        const revision = ++nextRevision;
        return { run: { revision } };
      },
      validate: (sample) => {
        if (sample.run.revision === 5) captured.resolve();
      },
      isComplete: (sample) => sample.run.revision >= 5,
      render: async () => {
        await captured.promise; // UI remains pending until independent HTTP work completes.
        assert.ok(
          samples.length >= 5,
          'UI delay starved the independent HTTP sampler'
        );
      },
    });
  } finally {
    clearTimeout(deadline);
  }
  assert.deepEqual(
    samples.map((sample) => sample.run.revision),
    [1, 2, 3, 4, 5]
  );
  assert.equal(receipt.completed, true);
  assert.equal(receipt.stopped, true);
  assert.ok(receipt.endedAt >= receipt.startedAt);
  assert.equal(receipt.reads.length, 5);
  assert.equal(receipt.sampleGapsMs.length, 4);
});

test('UI failure stops and awaits the sampler before propagating failure', async () => {
  const receipt = {},
    samples = [];
  await assert.rejects(
    sampleWhileRendering({
      samples,
      receipt,
      intervalMs: 1000,
      limitMs: 2000,
      read: async () => ({ run: { revision: samples.length + 1 } }),
      isComplete: () => false,
      render: async () => {
        await delay(10);
        throw new Error('capture failed');
      },
    }),
    /capture failed/
  );
  const count = samples.length;
  await delay(10);
  assert.equal(samples.length, count);
  assert.equal(receipt.stopped, true);
  assert.match(receipt.error, /capture failed/);
});

test('HTTP validation failure retains the acquired sample and propagates', async () => {
  const samples = [],
    receipt = {};
  await assert.rejects(
    sampleWhileRendering({
      samples,
      receipt,
      intervalMs: 1,
      limitMs: 1000,
      read: async () => ({ run: { revision: 1 } }),
      validate: () => {
        throw new Error('physical frame changed');
      },
      isComplete: () => true,
      render: async () => {
        await delay(10);
      },
    }),
    /physical frame changed/
  );
  assert.equal(samples.length, 1);
  assert.equal(receipt.stopped, true);
  assert.match(receipt.error, /physical frame changed/);
});
