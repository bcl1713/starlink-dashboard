/** Independent HTTP recorder; UI awaits never block its sampling loop. */
export async function sampleWhileRendering({
  read,
  validate = () => {},
  render,
  isComplete,
  samples = [],
  receipt = {},
  intervalMs = 300,
  limitMs = 350_000,
}) {
  Object.assign(receipt, {
    startedAt: Date.now(),
    reads: [],
    sampleGapsMs: [],
    completed: false,
  });
  const state = { samples, ended: false, error: undefined };
  let stopped = false,
    wake;
  const worker = (async () => {
    try {
      while (!stopped && Date.now() - receipt.startedAt < limitMs) {
        const attempt = { startedAt: Date.now() };
        receipt.reads.push(attempt);
        const sample = await read();
        samples.push(sample); // Keep actual evidence even if validation fails.
        attempt.finishedAt = Date.now();
        attempt.publicationRevision = sample.run?.revision;
        const previous = receipt.reads.at(-2)?.finishedAt;
        if (previous !== undefined)
          receipt.sampleGapsMs.push(attempt.finishedAt - previous);
        validate(sample);
        if (isComplete(sample)) {
          receipt.completed = true;
          return;
        }
        if (!stopped)
          await new Promise((resolve) => {
            const timer = setTimeout(resolve, intervalMs);
            wake = () => {
              clearTimeout(timer);
              resolve();
            };
          });
      }
      if (!stopped)
        throw new Error('HTTP replay sampling exceeded its deadline');
    } catch (error) {
      state.error = error;
      receipt.samplerError = String(error);
    } finally {
      state.ended = true;
      receipt.endedAt = Date.now();
    }
  })();
  try {
    await render(state);
    await worker;
    if (state.error) throw state.error;
    return state;
  } catch (error) {
    receipt.error = String(error);
    throw error;
  } finally {
    receipt.stopRequestedAt = Date.now();
    stopped = true;
    wake?.();
    await worker;
    receipt.stopped = true;
    receipt.maxSampleGapMs = Math.max(0, ...receipt.sampleGapsMs);
  }
}
