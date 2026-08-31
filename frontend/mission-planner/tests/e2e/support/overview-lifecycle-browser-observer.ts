import type {
  BrowserObserverConfig,
  CdpNetworkRecord,
  IdentityTransition,
  LedgerWindow,
  LifecycleSample,
  MutationEntry,
} from './overview-lifecycle-types';
export function installBrowserLifecycleObserver({
  chartSeriesCounts,
  featureCounts,
  panes,
  ownershipSelector,
  limits,
}: BrowserObserverConfig): void {
  const criticalSelector =
    '.overview-page,.leaflet-container,.operational-map__layer-row,.leaflet-pane,.leaflet-planned-route-west-pane path,.leaflet-weather-radar-pane img,canvas,.overview-summary-region,.overview-right-rail,.overview-poi-region,details';
  const criticalOwnerSelector =
    '.leaflet-planned-route-west-pane,.leaflet-weather-radar-pane';
  const mutations: MutationEntry[] = [];
  const identityTransitions: IdentityTransition[] = [];
  const samples: LifecycleSample[] = [];
  const overflowed = new Set<string>();
  const retain = <T>(values: T[], value: T, limit: number, label: string) =>
    values.length < limit ? values.push(value) : overflowed.add(label);
  const active = new Map<string, CdpNetworkRecord>();
  let previous: Readonly<Record<string, string | null>> | null = null;
  let mutationSampledSinceRequest = false;
  const timestamp = (): number =>
    Number(document.timeline.currentTime ?? performance.now());
  const installedAt = timestamp();
  const objectId = (window as LedgerWindow).__overviewObjectId;
  if (!objectId) throw new Error('Object identity registry was not installed');
  const describe = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) return '#text';
    return node instanceof Element ? node.tagName.toLowerCase() : node.nodeName;
  };
  const relevant = (node: Node) =>
    node instanceof Element &&
    (node.matches(criticalSelector) ||
      Boolean(node.querySelector(criticalSelector)));
  const canvasSignature = (canvas: HTMLCanvasElement) => {
    const ready = canvas.width > 0 && canvas.height > 0;
    return `${canvas.width}x${canvas.height}:${ready ? 1 : 0}:stable`;
  };
  const region = (key: string, selector: string) => {
    const element = document.querySelector(selector);
    const box = element?.getBoundingClientRect();
    return {
      key,
      identity: objectId(element),
      width: box?.width ?? 0,
      height: box?.height ?? 0,
      signature: /loading/i.test(element?.textContent ?? '')
        ? 'loading'
        : `content:${element?.childElementCount ?? 0}`,
    };
  };

  const collect = (phase: string, request: CdpNetworkRecord | null): void => {
    const root = document.querySelector('.overview-page');
    const map = document.querySelector('.leaflet-container');
    const layers = [
      ...document.querySelectorAll('.operational-map__layer-row'),
    ].map((row, index) => {
      const input = row.querySelector('input');
      const label = input?.getAttribute('aria-label') ?? '';
      const paneName = panes[label] ?? null;
      const owner = paneName
        ? document.querySelector(`.leaflet-${CSS.escape(paneName)}-pane`)
        : null;
      const rendered = owner ? [...owner.children] : [];
      const ownedNodes = owner
        ? [...owner.querySelectorAll(ownershipSelector)]
        : [];
      return {
        label,
        checked: input instanceof HTMLInputElement ? input.checked : false,
        controlId: objectId(input),
        ownerId: objectId(owner),
        objectId: objectId(owner),
        expectedCount: featureCounts[index] ?? -1,
        renderedCount: rendered.length,
        signature: ownedNodes
          .map((node) => `${objectId(node)}:${describe(node)}`)
          .join('|'),
      };
    });
    const charts = [...document.querySelectorAll('canvas')].map(
      (canvas, index) => {
        const section = canvas.closest('section,article');
        const owner = canvas.closest('.uplot') ?? canvas.parentElement;
        return {
          label:
            section?.querySelector('h2,h3')?.textContent?.trim() ?? 'chart',
          canvasId: objectId(canvas),
          seriesOwnerId: objectId(owner),
          objectId: objectId(
            canvas.closest('[data-testid="time-series-chart-host"]')
          ),
          seriesCount: chartSeriesCounts[index] ?? 0,
          signature: canvasSignature(canvas),
        };
      }
    );
    const identities: Record<string, string | null> = {
      overviewRoot: objectId(root),
      leafletContainer: objectId(map),
      leafletMap: (map as (Element & { _leaflet_id?: number }) | null)
        ?._leaflet_id
        ? `leaflet:${(map as Element & { _leaflet_id: number })._leaflet_id}`
        : null,
      leafletOwner: objectId(map?.parentElement),
    };
    layers.forEach((layer, index) => {
      identities[`layerControl:${index}:${layer.label}`] = layer.controlId;
      identities[`layerOwner:${index}:${layer.label}`] = layer.ownerId;
      identities[`layerObject:${index}:${layer.label}`] = layer.objectId;
    });
    charts.forEach((chart, index) => {
      identities[`chartCanvas:${index}:${chart.label}`] = chart.canvasId;
      identities[`chartSeries:${index}:${chart.label}`] = chart.seriesOwnerId;
      identities[`chartObject:${index}:${chart.label}`] = chart.objectId;
    });
    const now = timestamp();
    if (previous) {
      for (const [key, before] of Object.entries(previous)) {
        const after = identities[key] ?? null;
        if (before !== after) {
          retain(
            identityTransitions,
            {
              at: now,
              phase,
              key,
              before,
              after,
              activeRequestIds: [...active.keys()],
            },
            limits.identityTransitions,
            'identityTransitions'
          );
        }
      }
    }
    previous = identities;
    const focused = document.activeElement;
    retain(
      samples,
      {
        at: now,
        phase,
        request,
        activeRequestIds: [...active.keys()],
        activeRequests: [...active.values()],
        identities,
        regions: [
          region('root', '.overview-page'),
          region('map', '.overview-map-region'),
          region('summary', '.overview-summary-region'),
          region('rail', '.overview-right-rail'),
          region('poi', '.overview-poi-region'),
          region('history', '.overview-latency-region'),
        ],
        layers,
        charts,
        focusId: objectId(focused),
        focusLabel:
          focused instanceof HTMLElement
            ? (focused.getAttribute('aria-label') ??
              focused.textContent?.trim() ??
              '')
            : '',
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        poiFilter:
          document.querySelector<HTMLSelectElement>(
            '[aria-label="POI category"]'
          )?.value ?? '',
        disclosures: [...document.querySelectorAll('details')].map((details) =>
          details.open ? 'open' : 'closed'
        ),
      },
      limits.lifecycleSamples,
      'lifecycleSamples'
    );
  };
  const recordMutation = (record: MutationRecord) => {
    const target = record.target instanceof Element ? record.target : null;
    const removed = [...record.removedNodes];
    const criticalRemoval =
      removed.some(relevant) ||
      (Boolean(target?.closest(criticalOwnerSelector)) &&
        removed.some((node) => node instanceof Element));
    const observedAttribute =
      record.type === 'attributes' &&
      ['aria-busy', 'aria-hidden'].includes(record.attributeName ?? '');
    if (!criticalRemoval && !observedAttribute) return;
    retain(
      mutations,
      {
        at: timestamp(),
        activeRequestIds: [...active.keys()],
        type: record.type,
        target: describe(record.target),
        attributeName: record.attributeName,
        oldValue: record.oldValue,
        newValue:
          record.type === 'attributes' && target && record.attributeName
            ? target.getAttribute(record.attributeName)
            : null,
        added: [...record.addedNodes]
          .slice(0, limits.mutationNodes)
          .map(describe),
        removed: removed.slice(0, limits.mutationNodes).map(describe),
        criticalRemoval,
      },
      limits.lifecycleMutations,
      'lifecycleMutations'
    );
  };
  const shouldSampleMutations = (records: MutationRecord[]) => {
    const observedLayoutChange = records.some(
      (record) =>
        record.type === 'attributes' && record.attributeName === 'style'
    );
    const observedTextChange = records.some(
      (record) =>
        record.type === 'childList' &&
        [...record.addedNodes, ...record.removedNodes].some(
          (node) => node.nodeType === Node.TEXT_NODE
        )
    );
    for (const record of records) recordMutation(record);
    if (
      !records.length ||
      (mutationSampledSinceRequest &&
        !observedLayoutChange &&
        !observedTextChange)
    )
      return false;
    mutationSampledSinceRequest = true;
    return true;
  };
  const observer = new MutationObserver((records) => {
    if (shouldSampleMutations(records)) collect('mutation', null);
  });
  observer.observe(document.querySelector('.overview-page')!, {
    attributes: true,
    attributeOldValue: true,
    childList: true,
    characterData: true,
    characterDataOldValue: true,
    subtree: true,
  });
  collect('baseline', null);
  (window as LedgerWindow).__overviewLifecycle = {
    cdp(record) {
      active.set(record.cdpRequestId, record);
      if (record.event === 'Network.requestWillBeSent')
        mutationSampledSinceRequest = false;
      const phase =
        record.event === 'Network.responseReceived'
          ? null
          : {
              'Network.requestWillBeSent': 'cdp-request-start',
              'Network.loadingFinished': 'cdp-request-terminal',
              'Network.loadingFailed': 'cdp-request-terminal',
            }[record.event];
      if (phase) collect(phase, record);
      if (record.terminalOutcome !== 'pending')
        active.delete(record.cdpRequestId);
    },
    stop() {
      const pending = observer.takeRecords();
      if (shouldSampleMutations(pending)) collect('stop-mutation', null);
      collect('final-settle', null);
      observer.disconnect();
      return {
        installedAt,
        stoppedAt: timestamp(),
        mutations,
        identityTransitions,
        samples,
        consoleErrors: [],
        pageErrors: [],
        retention: {
          status: overflowed.size ? 'overflow' : 'complete',
          overflowed: [...overflowed].sort(),
          retained: {
            lifecycleMutations: mutations.length,
            lifecycleSamples: samples.length,
            identityTransitions: identityTransitions.length,
          },
        },
      };
    },
  };
}
