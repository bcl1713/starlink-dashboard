import { vi } from 'vitest';
import type { Mission } from '../types/mission';

vi.hoisted(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({
      matches: true,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  });
  Object.defineProperty(window, 'ResizeObserver', {
    configurable: true,
    value: class ResizeObserver {
      observe() {}
      disconnect() {}
    },
  });
});

const mission: Mission = {
  id: 'alpha',
  name: 'Alpha Mission',
  description: 'Route ownership fixture',
  created_at: '2026-08-31T00:00:00Z',
  updated_at: '2026-08-31T00:00:00Z',
  metadata: {},
  legs: [
    {
      id: 'bravo',
      name: 'Bravo Leg',
      route_id: 'route-a',
      transports: {
        initial_x_satellite_id: 'X-1',
        initial_ka_satellite_ids: ['AOR'],
        x_transitions: [],
        ka_outages: [],
        aar_windows: [],
        manual_aar_tracks: [],
        ku_overrides: [],
      },
    },
  ],
};

vi.mock('../services/monitoring', async () => {
  const fixtures = await import('../services/monitoring-test-fixtures');
  return {
    getStatus: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.statusPayload))
    ),
    getMonitoringHistory: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.historyPayload))
    ),
    getGroundEntryPoint: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.availableGep))
    ),
    getPOIETAs: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.poiPayload))
    ),
    getSatelliteETAs: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.poiPayload))
    ),
    getMissionEventETAs: vi.fn(() =>
      Promise.resolve(
        fixtures.clone({ pois: [], total: 0, timestamp: fixtures.aware })
      )
    ),
    getRouteCoordinates: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.routePayload))
    ),
    getActiveXLink: vi.fn(() =>
      Promise.resolve(fixtures.clone(fixtures.activeXLinkPayload))
    ),
    getRainViewerRadarTile: vi.fn(() =>
      Promise.resolve({ blob: new Blob(['radar']), contentType: 'image/png' })
    ),
  };
});

vi.mock('../services/missions', async () => {
  const actual = await vi.importActual<typeof import('../services/missions')>(
    '../services/missions'
  );
  return {
    MISSIONS_PAGE_SIZE: actual.MISSIONS_PAGE_SIZE,
    missionsApi: {
      list: vi.fn(() => Promise.resolve([mission])),
      listPage: vi.fn(() => Promise.resolve({ missions: [mission], total: 1 })),
      get: vi.fn(() => Promise.resolve(mission)),
      create: vi.fn(),
      update: vi.fn(() => Promise.resolve(mission)),
      delete: vi.fn(),
      addLeg: vi.fn(),
      updateLeg: vi.fn(),
      deleteLeg: vi.fn(),
      activateLeg: vi.fn(),
      deactivateAllLegs: vi.fn(),
      updateLegRoute: vi.fn(),
    },
  };
});

vi.mock('../services/routes', () => ({
  routesApi: {
    list: vi.fn(() =>
      Promise.resolve([{ id: 'route-a', name: 'Route A', is_active: true }])
    ),
    get: vi.fn(() =>
      Promise.resolve({
        id: 'route-a',
        name: 'Route A',
        points: [{ latitude: 39, longitude: -104 }],
        waypoints: [{ name: 'DEN', latitude: 39, longitude: -104 }],
      })
    ),
    upload: vi.fn(),
    delete: vi.fn(),
    activate: vi.fn(),
    deactivate: vi.fn(),
    download: vi.fn(),
    getCoordinates: vi.fn(() => Promise.resolve([[39, -104]])),
    getWaypoints: vi.fn(() =>
      Promise.resolve([{ name: 'DEN', latitude: 39, longitude: -104 }])
    ),
    getWaypointNames: vi.fn(() => Promise.resolve(['DEN'])),
  },
}));

vi.mock('../services/pois', () => ({
  poisService: {
    getAllPOIs: vi.fn(() => Promise.resolve([])),
    getPOIsByRoute: vi.fn(() => Promise.resolve([])),
    getPOIsByMission: vi.fn(() => Promise.resolve([])),
    getPOIsWithETA: vi.fn(() => Promise.resolve([])),
    getPOI: vi.fn(),
    createPOI: vi.fn(),
    updatePOI: vi.fn(),
    deletePOI: vi.fn(),
  },
}));

vi.mock('../services/satellites', () => ({
  satelliteService: {
    getAll: vi.fn(() =>
      Promise.resolve([
        {
          satellite_id: 'X-1',
          transport: 'x',
          longitude: -100,
          slot: null,
          color: 'green',
        },
      ])
    ),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../services/timeline', () => ({
  timelineService: {
    getTimeline: vi.fn(() =>
      Promise.resolve({
        mission_leg_id: 'bravo',
        created_at: '2026-08-31T00:00:00Z',
        segments: [],
      })
    ),
    previewTimeline: vi.fn(() => Promise.resolve(null)),
  },
}));

vi.mock('../services/gps', () => ({
  gpsService: {
    getGPSConfig: vi.fn(() =>
      Promise.resolve({ enabled: true, ready: true, satellites: 8 })
    ),
    setGPSConfig: vi.fn(),
    parseError: vi.fn((error) => ({
      type: 'unknown',
      message: error instanceof Error ? error.message : 'unknown',
    })),
  },
}));
