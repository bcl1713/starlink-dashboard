import {
  OVERVIEW_SCENARIOS,
  type OverviewScenario,
} from '../fixtures/overview';

export type OverviewScenarioId =
  | (typeof OVERVIEW_SCENARIOS)[number]['id']
  | 'overview-empty';

const template = OVERVIEW_SCENARIOS.find(
  (scenario) => scenario.id === 'overview-no-route'
);
if (!template) throw new Error('Missing no-route overview fixture');

export const EMPTY_OVERVIEW_SCENARIO: OverviewScenario = {
  ...template,
  id: 'overview-empty',
  name: 'empty',
  telemetry: {
    currentObservedAt: null,
    currentPosition: null,
    positionHistory: [],
    metrics: {
      latency: {
        currentMs: null,
        fiveMinute: { minMs: null, averageMs: null, maxMs: null },
        history: [],
      },
      packetLoss: {
        currentPercent: null,
        averagePercent: null,
        maxPercent: null,
        history: [],
      },
      throughput: {
        current: { downloadMbps: null, uploadMbps: null },
      },
      obstruction: { currentPercent: null },
    },
  },
  route: {
    ...template.route,
    active: false,
    revisionAt: null,
    westernSegment: [],
    easternSegment: [],
  },
  pois: { generatedAt: null, items: [] },
  groundEntryPoint: {
    ...template.groundEntryPoint,
    display: 'Unavailable',
    observedAt: null,
    coordinate: null,
  },
  radar: {
    available: false,
    frameAt: null,
    state: 'unavailable',
    error: 'No radar frame is available.',
  },
  satellites: { generatedAt: null, items: [] },
  activeLinks: [],
  missionEvents: { generatedAt: null, items: [] },
};

export function overviewScenarioById(id: OverviewScenarioId): OverviewScenario {
  if (id === 'overview-empty') return EMPTY_OVERVIEW_SCENARIO;
  const scenario = OVERVIEW_SCENARIOS.find((item) => item.id === id);
  if (!scenario) throw new Error(`Unknown overview scenario: ${id}`);
  return scenario;
}
