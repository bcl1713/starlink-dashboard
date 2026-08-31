export type CdpNetworkEventName =
  | 'Network.requestWillBeSent'
  | 'Network.responseReceived'
  | 'Network.loadingFinished'
  | 'Network.loadingFailed';

export interface CdpNetworkEvent {
  readonly name: CdpNetworkEventName;
  readonly cdpRequestId: string;
  readonly timestamp: number;
  readonly url: string | null;
  readonly method: string | null;
  readonly status: number | null;
  readonly failureText: string | null;
}

export interface CdpNetworkRecord {
  readonly cdpRequestId: string;
  readonly event: CdpNetworkEventName;
  readonly url: string;
  readonly method: string;
  readonly type: string;
  readonly requestTimestamp: number;
  readonly responseTimestamp: number | null;
  readonly terminalTimestamp: number | null;
  readonly terminalOutcome: 'finished' | 'failed' | 'pending';
  readonly status: number | null;
  readonly failureText: string | null;
}

export interface RetentionOutcome {
  readonly status: 'complete' | 'overflow';
  readonly overflowed: readonly string[];
  readonly retained: Readonly<Record<string, number>>;
}

export interface BrowserObserverConfig {
  readonly chartSeriesCounts: readonly number[];
  readonly featureCounts: readonly number[];
  readonly panes: Readonly<Record<string, string>>;
  readonly ownershipSelector: string;
  readonly limits: {
    readonly identityTransitions: number;
    readonly lifecycleMutations: number;
    readonly lifecycleSamples: number;
    readonly mutationNodes: number;
  };
}

export interface LifecycleLedger {
  readonly installedAt: number;
  readonly stoppedAt: number;
  readonly mutations: readonly MutationEntry[];
  readonly identityTransitions: readonly IdentityTransition[];
  readonly samples: readonly LifecycleSample[];
  readonly consoleErrors: readonly string[];
  readonly pageErrors: readonly string[];
  readonly retention: RetentionOutcome;
}

export interface MutationEntry {
  readonly at: number;
  readonly activeRequestIds: readonly string[];
  readonly type: string;
  readonly target: string;
  readonly attributeName: string | null;
  readonly oldValue: string | null;
  readonly newValue: string | null;
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
  readonly request: CdpNetworkRecord | null;
  readonly activeRequestIds: readonly string[];
  readonly activeRequests: readonly CdpNetworkRecord[];
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
  readonly objectId: string | null;
  readonly expectedCount: number;
  readonly renderedCount: number;
  readonly signature: string;
}

export interface ChartSample {
  readonly label: string;
  readonly canvasId: string | null;
  readonly seriesOwnerId: string | null;
  readonly objectId: string | null;
  readonly seriesCount: number;
  readonly signature: string;
}

export type LedgerWindow = Window & {
  __overviewLifecycle?: {
    cdp(record: CdpNetworkRecord): void;
    stop(): LifecycleLedger;
  };
  __overviewObjectId?: (object: object | null | undefined) => string | null;
};
