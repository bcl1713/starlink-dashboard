import type { BrowserContext, Page } from '@playwright/test';
import type * as THREE from 'three';
import type {
  AdsbContact,
  AdsbSettings,
} from '../../../src/services/overview-adsb';
import { adsbContact, adsbSettings } from '../../../src/test/adsb-fixtures';
import { installOverviewWindowFixture } from './overview-window-fixture';
import { observeOverviewCamera, overviewCamera } from './overview-camera';

export interface AdsbFixtureController {
  setContacts: (contacts: AdsbContact[]) => void;
  setSettings: (settings: AdsbSettings) => void;
  failSettingsSave: (fail: boolean) => void;
  failTraffic: (fail: boolean) => void;
  holdNextTraffic: () => { release: () => void };
}
export function freshContact(changes: Partial<AdsbContact> = {}): AdsbContact {
  const now = Date.now();
  return adsbContact({
    latitude: 38,
    longitude: -90,
    position_observed_at_ms: now,
    acquired_at_ms: now,
    ...changes,
  });
}
export function globalWorkload(): AdsbContact[] {
  return Array.from({ length: 2000 }, (_, i) =>
    freshContact({
      hex: i.toString(16).toUpperCase().padStart(6, '0'),
      latitude: i < 50 ? 38 + (i % 5) * 0.07 : -80 + (i % 161),
      longitude: i < 50 ? -90 + Math.floor(i / 5) * 0.07 : -179 + (i % 359),
      callsign:
        i < 50 ? `INCLUDED-${i.toString().padStart(2, '0')}` : `RCH-${i}`,
      position_observed_at_ms: Date.now() - (i % 3 === 0 ? 40000 : 0),
    })
  );
}
export async function installAdsbFixture(
  context: BrowserContext
): Promise<AdsbFixtureController> {
  await installOverviewWindowFixture(context);
  let settings = adsbSettings({ enabled: false, revision: 0 }),
    contacts: AdsbContact[] = [],
    saveError = false,
    trafficError = false;
  let hold: Promise<void> | null = null;
  await context.route('**/api/overview-adsb/**', async (route) => {
    if (route.request().url().endsWith('/settings')) {
      if (route.request().method() === 'PUT') {
        if (saveError)
          return route.fulfill({
            status: 503,
            json: { detail: 'Controlled save failure' },
          });
        settings = {
          ...settings,
          ...route.request().postDataJSON(),
          revision: settings.revision + 1,
        };
      }
      return route.fulfill({ json: settings });
    }
    const snapshot = structuredClone({
      settings_revision: settings.revision,
      generated_at_ms: Date.now(),
      sources: [],
      contacts: settings.enabled
        ? contacts.filter(
            (c) =>
              !settings.exclude_hexes.includes(c.hex) &&
              (settings.include_hexes.includes(c.hex) ||
                (settings.mode === 'military_and_included' &&
                  c.military === true &&
                  (settings.callsign_substrings.length === 0 ||
                    settings.callsign_substrings.some((s) =>
                      (c.callsign ?? '').toUpperCase().includes(s)
                    ))))
          )
        : [],
    });
    const pending = hold;
    hold = null;
    if (pending) await pending;
    await route
      .fulfill(
        trafficError
          ? { status: 503, json: { detail: 'Controlled traffic failure' } }
          : { json: snapshot }
      )
      .catch(() => {});
  });
  return {
    setContacts: (value) => {
      contacts = structuredClone(value);
    },
    setSettings: (value) => {
      settings = structuredClone(value);
    },
    failSettingsSave: (value) => {
      saveError = value;
    },
    failTraffic: (value) => {
      trafficError = value;
    },
    holdNextTraffic: () => {
      let release = () => {};
      hold = new Promise<void>((resolve) => {
        release = resolve;
      });
      return { release };
    },
  };
}
type SceneState = {
  gl: THREE.WebGLRenderer;
  camera: THREE.Camera;
  scene: THREE.Scene;
  controls?: {
    rotate: (azimuth: number, polar: number, transition: boolean) => void;
  };
};
declare global {
  interface Window {
    __overviewEvidenceRoots?: Array<{
      containerInfo?: { getState?: () => SceneState };
    }>;
  }
}
export async function observeAdsbScene(page: Page) {
  await observeOverviewCamera(page);
}
export async function adsbScene(page: Page) {
  await overviewCamera(page);
  return page.evaluate(() => {
    const state = window.__overviewEvidenceRoots
      ?.find(
        (root) =>
          root.containerInfo?.getState &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )
      ?.containerInfo?.getState?.();
    if (!state) throw new Error('No active scene');
    const batches: {
      count: number;
      hexes: string[];
      points: { hex: string; x: number; y: number }[];
      matrices: number[];
    }[] = [];
    const rect = state.gl.domElement.getBoundingClientRect();
    state.scene.traverse((node) => {
      if (
        !(node as THREE.InstancedMesh).isInstancedMesh ||
        !node.userData.adsbBatch
      )
        return;
      const mesh = node as THREE.InstancedMesh,
        batch = node.userData.adsbBatch as {
          hexes: string[];
          positions: THREE.Vector3[];
        };
      batches.push({
        count: mesh.count,
        hexes: batch.hexes,
        matrices: Array.from(mesh.instanceMatrix.array),
        points: batch.positions.map((p, i) => {
          const v = p.clone().project(state.camera);
          return {
            hex: batch.hexes[i],
            x: rect.x + ((v.x + 1) * rect.width) / 2,
            y: rect.y + ((1 - v.y) * rect.height) / 2,
          };
        }),
      });
    });
    const context = state.gl.getContext(),
      debug = context.getExtension('WEBGL_debug_renderer_info');
    return {
      batches,
      calls: state.gl.info.render.calls,
      geometries: state.gl.info.memory.geometries,
      textures: state.gl.info.memory.textures,
      renderer: debug
        ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL)
        : context.getParameter(context.RENDERER),
      labels: document.querySelectorAll('[data-adsb-label]').length,
    };
  });
}
