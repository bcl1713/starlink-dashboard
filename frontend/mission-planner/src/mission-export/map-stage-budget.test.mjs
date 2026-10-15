import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRenderBudget } from './render-budget.mjs';
import { renderMapInContext } from './map-stage.mjs';

for (const boundary of ['context', 'route', 'page', 'readiness', 'close']) {
  test(
    `map cutoff covers ${boundary} boundary`,
    { timeout: 1000 },
    async () => {
      const never = () => new Promise(() => {});
      let closed = false;
      const page = {
        on() {},
        goto: async () => {},
        waitForFunction: async () => {},
        evaluate: async (fn) =>
          fn.toString().includes('plan')
            ? [{ id: 'view' }]
            : fn.toString().includes('render')
              ? undefined
              : { status: 'ready', digest: 'unused', viewId: 'view' },
        screenshot: async () => Buffer.from('png'),
      };
      if (boundary === 'readiness')
        page.evaluate = async (fn) =>
          fn.toString().includes('state') ? never() : [{ id: 'view' }];
      const context = {
        route: async () => {},
        newPage: async () => page,
        close: async () => {
          closed = true;
          if (boundary === 'close') await never();
        },
      };
      if (boundary === 'route') context.route = never;
      if (boundary === 'page') context.newPage = never;
      const budget = createRenderBudget({
        budgetMs: 500,
        pdfReserveMs: 400,
        cleanupReserveMs: 30,
      });
      const owner = { origin: 'http://local', newContext: async () => context };
      if (boundary === 'context')
        owner.newContext = async () => {
          await new Promise((resolve) => setTimeout(resolve, 150));
          return context;
        };
      const result = await renderMapInContext({ owner, budget, input: {} });
      assert.equal(result.status, 'unavailable');
      assert.ok(
        budget.elapsedMs() < 135,
        `Map consumed reserve: ${budget.elapsedMs()}`
      );
      await new Promise((resolve) => setTimeout(resolve, 170));
      assert.ok(closed, 'Created or late context must be closed');
    }
  );
}
