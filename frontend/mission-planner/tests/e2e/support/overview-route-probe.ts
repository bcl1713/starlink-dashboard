import type { Page } from '@playwright/test';
import { observeOverviewCamera } from './overview-camera';

export async function installOverviewRouteProbe(page: Page): Promise<void> {
  await observeOverviewCamera(page);
}

/** Read the route actually delivered to the mounted Three reconciler. */
export async function renderedRoutePoints(page: Page) {
  return page.evaluate(() => {
    type Fiber = {
      child?: Fiber;
      sibling?: Fiber;
      memoizedProps?: {
        points?: number[][];
        forward?: { maxParticles?: number };
      };
    };
    const roots =
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{ current?: Fiber }>;
        }
      ).__overviewEvidenceRoots ?? [];
    const pending = roots.flatMap((root) =>
      root.current ? [root.current] : []
    );
    while (pending.length) {
      const fiber = pending.pop()!;
      if (
        fiber.memoizedProps?.forward?.maxParticles === 1 &&
        fiber.memoizedProps.points
      )
        return fiber.memoizedProps.points;
      if (fiber.child) pending.push(fiber.child);
      if (fiber.sibling) pending.push(fiber.sibling);
    }
    return [];
  });
}
