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
  const budget = createRenderBudget({ clock: () => now });
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
  const budget = createRenderBudget({ clock: () => now });
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
    assert.equal(budget.remainingMs(), 60000 - now);
  }
  assert.equal(budget.elapsedMs(), 10000);
});
