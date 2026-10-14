import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
async function module() {
  assert.ok(
    existsSync(new URL('./render-budget.mjs', import.meta.url)),
    'shared budget contract absent'
  );
  return import('./render-budget.mjs');
}
test('map cutoff preserves PDF reserve', async () => {
  const { createRenderBudget, RenderDeadlineError } = await module();
  let now = 0;
  const budget = createRenderBudget({
    budgetMs: 60000,
    pdfReserveMs: 20000,
    clock: () => now,
  });
  now = 10000;
  assert.equal(budget.mapRemainingMs(), 30000);
  now = 39000;
  assert.equal(budget.mapRemainingMs(), 1000);
  now = 40000;
  assert.throws(() => budget.mapRemainingMs(), RenderDeadlineError);
  assert.equal(budget.workRemainingMs(), 17000);
  now = 60000;
  assert.throws(() => budget.remainingMs(), RenderDeadlineError);
});
test('teardown consumes budget', async () => {
  const { createRenderBudget } = await module();
  let now = 12;
  const budget = createRenderBudget({
    budgetMs: 60000,
    pdfReserveMs: 20000,
    clock: () => now,
  });
  now += 57000;
  assert.equal(budget.remainingMs(), 3000);
  assert.throws(() => budget.workRemainingMs());
  now += 2500;
  assert.equal(budget.elapsedMs(), 59500);
  assert.equal(budget.deadlineAt, 60012);
});
test('budget passed unchanged to every stage', async () => {
  const { createRenderBudget } = await module();
  let now = 0;
  const budget = createRenderBudget({ clock: () => now });
  for (const stage of ['startup', 'map', 'html', 'pdf', 'teardown']) {
    now += 2000;
    assert.equal(budget.startedAt, 0);
    assert.equal(budget.remainingMs(), 120000 - now);
  }
  assert.equal(budget.elapsedMs(), 10000);
});

test('slow renders have two minutes while preserving print and cleanup reserves', async () => {
  const { createRenderBudget, RenderDeadlineError } = await module();
  let now = 0;
  const budget = createRenderBudget({ clock: () => now });
  now = 65000;
  assert.equal(budget.workRemainingMs(), 52000);
  assert.equal(budget.mapRemainingMs(), 15000);
  now = 80000;
  assert.throws(() => budget.mapRemainingMs(), RenderDeadlineError);
  assert.equal(budget.workRemainingMs(), 37000);
  now = 117000;
  assert.throws(() => budget.workRemainingMs(), RenderDeadlineError);
  assert.equal(budget.remainingMs(), 3000);
  now = 120000;
  assert.throws(() => budget.remainingMs(), RenderDeadlineError);
  assert.throws(() => createRenderBudget({ budgetMs: 120001 }));
});
