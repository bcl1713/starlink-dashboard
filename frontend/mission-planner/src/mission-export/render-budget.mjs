import { performance } from 'node:perf_hooks';
export class RenderDeadlineError extends Error {
  constructor() {
    super('Shared render deadline exceeded');
    this.code = 'deadline';
  }
}
export function createRenderBudget({
  budgetMs = 60000,
  clock = () => performance.now(),
  pdfReserveMs = 20000,
  cleanupReserveMs = 3000,
} = {}) {
  if (
    !(
      budgetMs > cleanupReserveMs &&
      pdfReserveMs >= cleanupReserveMs &&
      pdfReserveMs < budgetMs &&
      cleanupReserveMs > 0 &&
      budgetMs <= 60000
    )
  )
    throw new Error('Invalid reserves');
  const startedAt = clock(),
    deadlineAt = startedAt + budgetMs;
  const allowance = (reserve) => {
    const left = deadlineAt - clock() - reserve;
    if (left <= 0) throw new RenderDeadlineError();
    return left;
  };
  return Object.freeze({
    startedAt,
    deadlineAt,
    budgetMs,
    pdfReserveMs,
    cleanupReserveMs,
    remainingMs: () => allowance(0),
    workRemainingMs: () => allowance(cleanupReserveMs),
    mapRemainingMs: () => allowance(pdfReserveMs),
    elapsedMs: () => clock() - startedAt,
  });
}
export async function within(promise, ms) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new RenderDeadlineError()),
          Math.max(1, ms)
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
