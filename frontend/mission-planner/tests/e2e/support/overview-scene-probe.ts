import type { Page } from '@playwright/test';

/** Read real Three resources through the reconciler's DevTools boundary.
 * Installed before application startup; no product instrumentation or fake scene.
 */
export async function installOverviewSceneProbe(page: Page) {
  await page.addInitScript(() => {
    type Attribute = {
      array: ArrayLike<number>;
      count: number;
      itemSize: number;
    };
    type Node = {
      isPoints?: boolean;
      geometry?: {
        uuid: string;
        drawRange: { count: number };
        attributes: Record<string, Attribute>;
      };
      material?: { uniforms?: Record<string, unknown> };
      traverse: (visit: (node: Node) => void) => void;
    };
    type State = {
      scene: Node;
      internal: { active: boolean };
      gl: {
        domElement: HTMLCanvasElement;
        info: { render: { calls: number }; memory: { geometries: number } };
        getPixelRatio: () => number;
      };
    };
    type Root = {
      current?: { stateNode?: { containerInfo?: { getState?: () => State } } };
    };
    const roots = new Set<{ getState: () => State }>();
    const target = window as unknown as Record<string, unknown>;
    target.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {
      supportsFiber: true,
      inject: () => 1,
      onCommitFiberRoot: (_id: number, root: Root) => {
        const store = root.current?.stateNode?.containerInfo;
        if (store?.getState) roots.add(store as { getState: () => State });
      },
      onCommitFiberUnmount: () => {},
    };
    target.__overviewScene = (statsOnly = false) => {
      const store = [...roots].find((root) => {
        const state = root.getState();
        return state.internal.active && state.gl.domElement.isConnected;
      });
      if (!store) return null;
      const state = store.getState();
      const particles: {
        geometry: string;
        count: number;
        colors: number[][];
        positions: number[][];
        sizes: number[];
        brightness: number[];
      }[] = [];
      if (!statsOnly)
        state.scene.traverse((node) => {
          const geometry = node.geometry;
          if (
            !node.isPoints ||
            !geometry?.attributes.size ||
            !node.material?.uniforms?.uDepthBias
          )
            return;
          const count = geometry.drawRange.count;
          const read = (name: string) => {
            const attribute = geometry.attributes[name];
            return Array.from({ length: count }, (_, index) =>
              Array.from(
                { length: attribute.itemSize },
                (_, channel) =>
                  attribute.array[index * attribute.itemSize + channel]
              )
            );
          };
          particles.push({
            geometry: geometry.uuid,
            count,
            colors: read('color'),
            positions: read('position'),
            sizes: read('size').flat(),
            brightness: read('brightness').flat(),
          });
        });
      return {
        retiredGeometries: [...roots]
          .filter((root) => root !== store)
          .map((root) => root.getState().gl.info.memory.geometries),
        calls: state.gl.info.render.calls,
        geometries: state.gl.info.memory.geometries,
        pixelRatio: state.gl.getPixelRatio(),
        particles,
      };
    };
  });
}

export async function sceneSnapshot(page: Page) {
  return page.evaluate(() => {
    const probe = (
      window as unknown as {
        __overviewScene?: () => {
          retiredGeometries: number[];
          calls: number;
          geometries: number;
          pixelRatio: number;
          particles: {
            geometry: string;
            count: number;
            colors: number[][];
            positions: number[][];
            sizes: number[];
            brightness: number[];
          }[];
        } | null;
      }
    ).__overviewScene;
    return probe?.() ?? null;
  });
}
