import type { Page } from '@playwright/test';

/** Sample props actually committed to the mounted Three scene at display frames. */
export async function sampleRunMotion(page: Page, durationMs = 600) {
  return page.evaluate(async (duration) => {
    type Fiber = {
      child?: Fiber;
      sibling?: Fiber;
      memoizedProps?: {
        coordinate?: { latitude: number; longitude: number };
        chevronSettings?: unknown;
        intensity?: number;
        position?: number[];
      };
    };
    const read = () => {
      const roots =
        (
          window as unknown as {
            __overviewEvidenceRoots?: Array<{ current?: Fiber }>;
          }
        ).__overviewEvidenceRoots ?? [];
      const pending = roots.flatMap((root) =>
        root.current ? [root.current] : []
      );
      let aircraft: { latitude: number; longitude: number } | undefined;
      let sun: number[] | undefined;
      while (pending.length) {
        const fiber = pending.pop()!;
        const props = fiber.memoizedProps;
        if (props?.coordinate && props.chevronSettings)
          aircraft = props.coordinate;
        if (props?.intensity === 5 && Array.isArray(props.position))
          sun = props.position;
        if (fiber.child) pending.push(fiber.child);
        if (fiber.sibling) pending.push(fiber.sibling);
      }
      return { aircraft, sun };
    };
    const samples: ReturnType<typeof read>[] = [];
    const started = performance.now();
    do {
      await new Promise(requestAnimationFrame);
      samples.push(read());
    } while (performance.now() - started < duration);
    return samples;
  }, durationMs);
}
