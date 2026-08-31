import type { RecordedOverviewRequest } from './overview-router';

export interface LifecycleLedger {
  readonly installedAt: number;
  readonly stoppedAt: number;
  readonly mutations: readonly MutationEntry[];
  readonly identityTransitions: readonly IdentityTransition[];
  readonly samples: readonly LifecycleSample[];
  readonly consoleErrors: readonly string[];
  readonly pageErrors: readonly string[];
}

export interface MutationEntry {
  readonly at: number;
  readonly activeRequestIds: readonly string[];
  readonly type: string;
  readonly target: string;
  readonly added: readonly string[];
  readonly removed: readonly string[];
  readonly criticalRemoval: boolean;
}

export interface IdentityTransition {
  readonly at: number;
  readonly phase: string;
  readonly key: string;
  readonly before: string | null;
  readonly after: string | null;
  readonly activeRequestIds: readonly string[];
}

export interface LifecycleSample {
  readonly at: number;
  readonly phase: string;
  readonly request: RecordedOverviewRequest | null;
  readonly activeRequestIds: readonly string[];
  readonly identities: Readonly<Record<string, string | null>>;
  readonly regions: readonly RegionSample[];
  readonly layers: readonly LayerSample[];
  readonly charts: readonly ChartSample[];
  readonly focusId: string | null;
  readonly focusLabel: string;
  readonly scrollX: number;
  readonly scrollY: number;
  readonly poiFilter: string;
  readonly disclosures: readonly string[];
}

export interface RegionSample {
  readonly key: string;
  readonly identity: string | null;
  readonly width: number;
  readonly height: number;
  readonly signature: string;
}

export interface LayerSample {
  readonly label: string;
  readonly checked: boolean;
  readonly controlId: string | null;
  readonly ownerId: string | null;
  readonly renderedCount: number;
  readonly signature: string;
}

export interface ChartSample {
  readonly label: string;
  readonly canvasId: string | null;
  readonly seriesOwnerId: string | null;
  readonly seriesCount: number;
  readonly signature: string;
}

export type LedgerWindow = Window & {
  __overviewLifecycle?: {
    request(record: RecordedOverviewRequest): void;
    stop(): LifecycleLedger;
  };
  __overviewObjectId?: (object: object | null | undefined) => string | null;
};
