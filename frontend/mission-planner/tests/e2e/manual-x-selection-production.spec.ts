import { writeFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import { seedOverviewWindowMission } from './support/overview-window-mission';

// Inspect real rendered Line2 resources through the Three reconciler, without
// adding product instrumentation or intercepting any API response.
async function installLinkProbe(page: Page) {
  await page.addInitScript(() => {
    type Node = {
      isLine2?: boolean;
      geometry?: { attributes: { instanceEnd?: { array: ArrayLike<number> } } };
      traverse: (visit: (node: Node) => void) => void;
    };
    type Store = {
      getState: () => { scene: Node; internal: { active: boolean } };
    };
    const stores: Store[] = [];
    const target = window as unknown as Record<string, unknown>;
    target.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {
      supportsFiber: true,
      inject: () => 1,
      onCommitFiberRoot: (
        _id: number,
        root: { current?: { stateNode?: { containerInfo?: Store } } }
      ) => {
        const store = root.current?.stateNode?.containerInfo;
        if (store?.getState && !stores.includes(store)) stores.push(store);
      },
      onCommitFiberUnmount: () => {},
    };
    target.__xLinkEnds = () => {
      const ends: number[][] = [];
      for (const store of stores) {
        const state = store.getState();
        if (!state.internal.active) continue;
        state.scene.traverse((node) => {
          const array = node.geometry?.attributes.instanceEnd?.array;
          if (node.isLine2 && array) ends.push(Array.from(array).slice(-3));
        });
      }
      return ends;
    };
  });
}

async function renderedLinkLongitudes(page: Page) {
  return page.evaluate(() => {
    const read = (window as unknown as { __xLinkEnds: () => number[][] })
      .__xLinkEnds;
    return read()
      .filter(([x, y, z]) => Math.abs(Math.hypot(x, y, z) - 13.234) < 0.01)
      .map(([x, , z]) => Math.round((Math.atan2(-z, x) * 180) / Math.PI));
  });
}

test('Configuration selects planned satellites in an open Overview and yields to mission ownership', async ({
  context,
  request,
}, info) => {
  const sha = process.env.ACCEPTANCE_CANDIDATE_SHA;
  expect(sha).toMatch(/^[a-f0-9]{40}$/);
  const observations: unknown[] = [];
  for (const [name, longitude] of [
    ['X-281-A', -100],
    ['X-281-B', -80],
    ['X-281-Mission', -90],
  ] as const) {
    const created = await request.post('/api/satellites', {
      data: { satellite_id: name, transport: 'X', longitude },
    });
    expect(created.status(), await created.text()).toBe(201);
  }
  expect(
    (
      await request.put('/api/active-x-link/selection', {
        data: { satellite_id: null },
      })
    ).ok()
  ).toBe(true);
  const overview = await context.newPage();
  const editing = await context.newPage();
  await installLinkProbe(overview);
  let navigations = 0;
  overview.on('framenavigated', (frame) => {
    if (frame === overview.mainFrame()) navigations++;
  });
  await overview.goto('/overview');
  const card = overview.getByRole('region', {
    name: 'Planned satellite',
    exact: true,
  });
  await expect(card).toContainText('NO SATELLITE SELECTED');
  await editing.goto('/configuration');
  await editing.getByRole('tab', { name: 'Network Traffic' }).click();
  const picker = editing.getByRole('combobox', {
    name: 'Planned X-band satellite',
  });
  await expect(picker).toBeEnabled();
  const initialNavigations = navigations;
  for (const [name, longitude] of [
    ['X-281-A', -100],
    ['X-281-B', -80],
  ] as const) {
    const saved = editing.waitForResponse(
      (response) =>
        response.url().endsWith('/api/active-x-link/selection') &&
        response.request().method() === 'PUT'
    );
    await picker.selectOption(name);
    const response = await saved;
    expect(response.status()).toBe(200);
    expect(response.headers().server).toMatch(/nginx/);
    observations.push(await response.json());
    await expect(card).toContainText(name, { timeout: 8000 });
    await expect
      .poll(() => renderedLinkLongitudes(overview), { timeout: 15000 })
      .toEqual([longitude, longitude, longitude]);
    await expect(overview.getByLabel('Globe legend')).toContainText(
      'Planned satellite link'
    );
    expect(navigations).toBe(initialNavigations);
  }
  await overview.screenshot({
    path: info.outputPath('manual-satellite-overview.png'),
  });
  await editing.screenshot({
    path: info.outputPath('manual-satellite-configuration.png'),
  });
  await editing.reload();
  await editing.getByRole('tab', { name: 'Network Traffic' }).click();
  await expect(picker).toHaveValue('X-281-B');

  const seed = await seedOverviewWindowMission(request);
  const legPath = `/api/v2/missions/${seed.missionId}/legs/${seed.firstLegId}`;
  const missionResponse = await request.get(
    `/api/v2/missions/${seed.missionId}`
  );
  expect(missionResponse.ok(), await missionResponse.text()).toBe(true);
  const mission = await missionResponse.json();
  const leg = mission.legs.find(
    (candidate: { id: string }) => candidate.id === seed.firstLegId
  );
  expect(leg).toBeDefined();
  const updated = await request.put(legPath, {
    data: {
      ...leg,
      transports: {
        ...leg.transports,
        initial_x_satellite_id: 'X-281-Mission',
      },
    },
  });
  expect(updated.ok(), await updated.text()).toBe(true);
  const activated = await request.post(`${legPath}/activate`);
  expect(activated.ok(), await activated.text()).toBe(true);
  await expect(card).toContainText('X-281-Mission', { timeout: 8000 });
  await expect(picker).toBeDisabled();
  await expect
    .poll(() => renderedLinkLongitudes(overview))
    .toEqual([-90, -90, -90]);
  const blocked = await request.put('/api/active-x-link/selection', {
    data: { satellite_id: 'X-281-A' },
  });
  expect(blocked.status()).toBe(409);
  observations.push(await (await request.get('/api/active-x-link')).json());
  const deactivated = await request.post(
    `/api/v2/missions/${seed.missionId}/legs/deactivate`
  );
  expect(deactivated.ok()).toBe(true);
  await expect(card).toContainText('X-281-B', { timeout: 8000 });
  await expect(picker).toBeEnabled();
  await expect
    .poll(() => renderedLinkLongitudes(overview))
    .toEqual([-80, -80, -80]);

  expect((await request.delete('/api/satellites/X-281-B')).ok()).toBe(true);
  await expect(card).toContainText('NO SATELLITE SELECTED', { timeout: 8000 });
  await expect(
    editing.getByText(/saved satellite is no longer/i)
  ).toBeVisible();
  await expect.poll(() => renderedLinkLongitudes(overview)).toEqual([]);
  await editing.getByRole('button', { name: 'Clear saved selection' }).click();
  await expect(editing.getByText(/saved satellite is no longer/i)).toHaveCount(
    0
  );
  await picker.selectOption('X-281-A');
  await expect(card).toContainText('X-281-A');
  await picker.selectOption('');
  await expect(card).toContainText('NO SATELLITE SELECTED');
  await expect.poll(() => renderedLinkLongitudes(overview)).toEqual([]);
  // Leave a confirmed saved selection for the runner's backend restart check.
  await picker.selectOption('X-281-A');
  await expect(card).toContainText('X-281-A');
  expect(navigations).toBe(initialNavigations);
  await writeFile(
    info.outputPath('manual-x-selection-evidence.json'),
    JSON.stringify(
      {
        sha,
        baseURL: info.project.use.baseURL,
        observations,
        navigations,
        interceptedAPIs: false,
      },
      null,
      2
    )
  );
  await overview.close();
  await editing.close();
});
