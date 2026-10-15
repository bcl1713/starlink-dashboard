import { expect, type Page } from '@playwright/test';
export async function observeOverviewCamera(page: Page) {
  await page.addInitScript(() => {
    const roots: Array<{ containerInfo?: { getState?: () => unknown } }> = [];
    Object.assign(window, {
      __overviewEvidenceRoots: roots,
      __REACT_DEVTOOLS_GLOBAL_HOOK__: {
        supportsFiber: true,
        inject: () => 1,
        onCommitFiberRoot: (_id: number, root: (typeof roots)[number]) => {
          if (!roots.includes(root)) roots.push(root);
        },
        onCommitFiberUnmount: () => {},
        onPostCommitFiberRoot: () => {},
        checkDCE: () => {},
      },
    });
  });
}
export async function overviewCamera(page: Page) {
  await page.waitForFunction(
    () =>
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{
            containerInfo?: { getState?: unknown };
          }>;
        }
      ).__overviewEvidenceRoots?.some(
        (root) =>
          typeof root.containerInfo?.getState === 'function' &&
          document.contains(root.containerInfo.getState().gl.domElement)
      ),
    null,
    { timeout: 15_000 }
  );
  return page.evaluate(() => {
    const roots = (
      window as unknown as {
        __overviewEvidenceRoots: Array<{
          containerInfo?: {
            getState?: () => {
              gl: { domElement: HTMLCanvasElement };
              camera: {
                position: { toArray: () => number[] };
                quaternion: { toArray: () => number[] };
                zoom: number;
              };
              controls?: { getTarget: () => { toArray: () => number[] } };
            };
          };
        }>;
      }
    ).__overviewEvidenceRoots;
    const store = roots.find(
      (root) =>
        typeof root.containerInfo?.getState === 'function' &&
        document.contains(root.containerInfo.getState().gl.domElement)
    )?.containerInfo;
    if (!store?.getState) throw new Error('Renderer store not observed');
    const state = store.getState();
    return {
      position: state.camera.position.toArray(),
      quaternion: state.camera.quaternion.toArray(),
      zoom: state.camera.zoom,
      target: state.controls?.getTarget().toArray() ?? [0, 0, 0],
    };
  });
}
export async function settledOverviewCamera(page: Page) {
  let previous = await overviewCamera(page),
    stable = 0;
  await expect
    .poll(
      async () => {
        const current = await overviewCamera(page);
        const delta = Math.max(
          ...current.position.map((value, index) =>
            Math.abs(value - previous.position[index])
          )
        );
        stable = delta < 0.00001 ? stable + 1 : 0;
        previous = current;
        return stable;
      },
      { timeout: 60_000, intervals: [100] }
    )
    .toBeGreaterThanOrEqual(3);
  return previous;
}
export function expectSameCamera(
  before: Awaited<ReturnType<typeof overviewCamera>>,
  after: typeof before
) {
  for (const key of ['position', 'quaternion', 'target'] as const)
    for (let i = 0; i < before[key].length; i++)
      expect(after[key][i]).toBeCloseTo(before[key][i], 3);
  expect(after.zoom).toBe(before.zoom);
}
