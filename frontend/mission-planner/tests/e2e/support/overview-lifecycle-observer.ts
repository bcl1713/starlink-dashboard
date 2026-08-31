import type { Page } from '@playwright/test';

import type { RecordedOverviewRequest } from './overview-router';
import {
  LIFECYCLE_LAYER_PANES,
  LIFECYCLE_OWNERSHIP_SELECTOR,
} from './overview-lifecycle-contract';
import type {
  LedgerWindow,
  LifecycleSample,
  MutationEntry,
  IdentityTransition,
  RegionSample,
} from './overview-lifecycle-types';

export async function installLifecycleObserver(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));

  await page.evaluate(
    ({ panes, ownershipSelector }) => {
      const criticalSelector = [
        '.overview-page',
        '.leaflet-container',
        '.operational-map__layer-row',
        '.leaflet-pane',
        'canvas',
        '.overview-summary-region',
        '.overview-right-rail',
        '.overview-poi-region',
        'details',
      ].join(',');
      const mutations: MutationEntry[] = [];
      const identityTransitions: IdentityTransition[] = [];
      const samples: LifecycleSample[] = [];
      const active = new Map<string, RecordedOverviewRequest>();
      let previous: Readonly<Record<string, string | null>> | null = null;
      const timestamp = (): number =>
        Number(document.timeline.currentTime ?? performance.now());
      const installedAt = timestamp();
      const objectId = (window as LedgerWindow).__overviewObjectId;
      if (!objectId)
        throw new Error('Object identity registry was not installed');
      const describe = (node: Node) => {
        if (node.nodeType === Node.TEXT_NODE) return '#text';
        if (!(node instanceof Element)) return node.nodeName;
        const label =
          node.getAttribute('aria-label') ??
          node.getAttribute('data-testid') ??
          '';
        return `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ''}${
          node.classList.length ? `.${[...node.classList].join('.')}` : ''
        }${label ? `[${label}]` : ''}`;
      };
      const relevant = (node: Node) =>
        node instanceof Element &&
        (node.matches(criticalSelector) ||
          node.querySelector(criticalSelector));
      const mapObject = (element: Element | null) =>
        objectId(
          (element as (Element & { __overviewLeafletMap?: object }) | null)
            ?.__overviewLeafletMap
        );
      const layerObject = (element: Element | null) =>
        objectId(
          (element as (Element & { __overviewLeafletLayer?: object }) | null)
            ?.__overviewLeafletLayer
        );
      const chartObject = (element: Element | null) =>
        objectId(
          (element as (Element & { __overviewUPlot?: object }) | null)
            ?.__overviewUPlot
        );
      const region = (key: string, selector: string): RegionSample => {
        const element = document.querySelector(selector);
        const box = element?.getBoundingClientRect();
        const text = (element?.textContent ?? '')
          .replace(/Ready|Refreshing|Stale/g, 'Status')
          .replace(/Retry/g, '')
          .replace(/\s+/g, ' ')
          .trim();
        return {
          key,
          identity: objectId(element),
          width: box?.width ?? 0,
          height: box?.height ?? 0,
          signature: `${text.length}:${text}`,
        };
      };
      const collect = (
        phase: string,
        request: RecordedOverviewRequest | null
      ): void => {
        const root = document.querySelector('.overview-page');
        const map = document.querySelector('.leaflet-container');
        const layers = [
          ...document.querySelectorAll('.operational-map__layer-row'),
        ].map((row) => {
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
            objectId: layerObject(owner),
            renderedCount: rendered.length,
            signature: ownedNodes
              .map((node) => `${objectId(node)}:${describe(node)}`)
              .join('|'),
          };
        });
        const charts = [...document.querySelectorAll('canvas')].map(
          (canvas) => {
            const section = canvas.closest('section,article');
            const owner = canvas.closest('.uplot') ?? canvas.parentElement;
            return {
              label:
                section?.querySelector('h2,h3')?.textContent?.trim() ?? 'chart',
              canvasId: objectId(canvas),
              seriesOwnerId: objectId(owner),
              objectId: chartObject(
                canvas.closest('[data-testid="time-series-chart-host"]')
              ),
              seriesCount: owner?.querySelectorAll('.u-series').length ?? 0,
              signature: (section?.textContent ?? '')
                .replace(/\s+/g, ' ')
                .trim(),
            };
          }
        );
        const identities: Record<string, string | null> = {
          overviewRoot: objectId(root),
          leafletContainer: objectId(map),
          leafletMap: mapObject(map),
          leafletOwner: objectId(map?.parentElement),
        };
        layers.forEach((layer, index) => {
          identities[`layerControl:${index}:${layer.label}`] = layer.controlId;
          identities[`layerOwner:${index}:${layer.label}`] = layer.ownerId;
          identities[`layerObject:${index}:${layer.label}`] = layer.objectId;
        });
        charts.forEach((chart, index) => {
          identities[`chartCanvas:${index}:${chart.label}`] = chart.canvasId;
          identities[`chartSeries:${index}:${chart.label}`] =
            chart.seriesOwnerId;
          identities[`chartObject:${index}:${chart.label}`] = chart.objectId;
        });
        const now = timestamp();
        if (previous) {
          for (const [key, before] of Object.entries(previous)) {
            const after = identities[key] ?? null;
            if (before !== after) {
              identityTransitions.push({
                at: now,
                phase,
                key,
                before,
                after,
                activeRequestIds: [...active.keys()],
              });
            }
          }
        }
        previous = identities;
        const focused = document.activeElement;
        const sample = {
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
          disclosures: [...document.querySelectorAll('details')].map(
            (details) => (details.open ? 'open' : 'closed')
          ),
        } satisfies LifecycleSample;
        samples.push(sample);
      };

      const recordMutation = (record: MutationRecord) => {
        const target = record.target instanceof Element ? record.target : null;
        mutations.push({
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
          added: [...record.addedNodes].map(describe),
          removed: [...record.removedNodes].map(describe),
          criticalRemoval: [...record.removedNodes].some(relevant),
        });
      };

      const observer = new MutationObserver((records) => {
        for (const record of records) {
          recordMutation(record);
        }
        collect('mutation', null);
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
        request(record) {
          active.set(record.id, record);
          collect(
            record.event === 'start' ? 'request-start' : 'request-completion',
            record
          );
          if (record.event === 'start') {
            queueMicrotask(() => collect('pending', record));
          } else {
            setTimeout(() => {
              collect('settle', record);
              active.delete(record.id);
            }, 50);
          }
        },
        stop() {
          observer.takeRecords().forEach(recordMutation);
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
          };
        },
      };
    },
    {
      panes: LIFECYCLE_LAYER_PANES,
      ownershipSelector: LIFECYCLE_OWNERSHIP_SELECTOR,
    }
  );

  return {
    report: (record: RecordedOverviewRequest) =>
      page.evaluate((value) => {
        (window as LedgerWindow).__overviewLifecycle?.request(value);
      }, record),
    stop: async () => {
      const ledger = await page.evaluate(() =>
        (window as LedgerWindow).__overviewLifecycle!.stop()
      );
      return { ...ledger, consoleErrors, pageErrors };
    },
  };
}
