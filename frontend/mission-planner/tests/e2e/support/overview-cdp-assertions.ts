import {
  assertSettledSuccessfulHistoryStartDeltas,
  type HistoryCadenceContract,
} from '../../../src/pages/OverviewPage/overview-history-cadence';
import type { captureCdpContinuity } from './overview-cdp-capture';
import type { LifecycleSample } from './overview-lifecycle-types';

/**
 * Browser-runtime callers pass CDP records only after their terminal state is
 * settled.  The source contract rejects early starts and late starts outside
 * its explicit measurement budget; it is deliberately not a request count.
 */
export function assertHistoryCadenceEvidence(
  evidence: Awaited<ReturnType<typeof captureCdpContinuity>>,
  contract: HistoryCadenceContract
) {
  assertSettledSuccessfulHistoryStartDeltas(
    evidence.cdpNetworkLedger,
    contract
  );
}

export function assertContinuityEvidence(
  evidence: Awaited<ReturnType<typeof captureCdpContinuity>>
) {
  const { eventLedger, frames } = evidence;
  if (eventLedger.retention.status !== 'complete') {
    throw new Error(
      `Lifecycle evidence retention overflow: ${eventLedger.retention.overflowed.join(', ')}`
    );
  }
  if (evidence.cdpRetention?.status !== 'complete' && evidence.cdpRetention) {
    throw new Error(
      `CDP evidence retention overflow: ${evidence.cdpRetention.overflowed.join(', ')}`
    );
  }
  if (!frames.length) throw new Error('No supporting screenshot was captured');
  assertMonotonic(
    frames.map((frame) => frame.startMs),
    'screenshot timestamps'
  );
  assertMonotonic(
    eventLedger.mutations.map((mutation) => mutation.at),
    'mutation timestamps'
  );
  assertMonotonic(
    eventLedger.samples.map((sample) => sample.at),
    'lifecycle sample timestamps'
  );
  if (eventLedger.consoleErrors.length || eventLedger.pageErrors.length) {
    throw new Error(
      `Browser errors: ${[
        ...eventLedger.consoleErrors,
        ...eventLedger.pageErrors,
      ].join('; ')}`
    );
  }
  const criticalRemovals = eventLedger.mutations.filter(
    (mutation) => mutation.criticalRemoval
  );
  if (criticalRemovals.length) {
    throw new Error(`Observed ${criticalRemovals.length} critical removals`);
  }
  const invalidAttributes = eventLedger.mutations.filter(
    (mutation) =>
      (mutation.attributeName === 'aria-busy' &&
        mutation.newValue === 'true') ||
      (mutation.attributeName === 'aria-hidden' && mutation.newValue === 'true')
  );
  if (invalidAttributes.length) {
    const mutation = invalidAttributes[0]!;
    throw new Error(
      `Observed render-observable attribute ${mutation.attributeName}=${mutation.newValue} on ${mutation.target}`
    );
  }
  if (eventLedger.identityTransitions.length) {
    throw new Error(
      `Object identity changed: ${JSON.stringify(
        eventLedger.identityTransitions.slice(0, 3)
      )}`
    );
  }

  const baseline = eventLedger.samples.find(
    (sample) => sample.phase === 'baseline'
  );
  if (!baseline) throw new Error('Missing pre-request baseline sample');
  if (!eventLedger.samples.some((sample) => sample.phase === 'mutation')) {
    throw new Error('No mutation lifecycle samples were retained');
  }
  for (const sample of eventLedger.samples)
    assertLastGoodSample(sample, baseline);
  if (evidence.cdpNetworkLedger.length) assertRequestCorrelation(evidence);
}

export function assertLastGoodSample(
  sample: LifecycleSample,
  baseline: LifecycleSample
) {
  for (const region of sample.regions) {
    const before = baseline.regions.find((item) => item.key === region.key);
    if (
      !region.identity ||
      region.width <= 0 ||
      region.height <= 0 ||
      !region.signature
    ) {
      throw new Error(
        `Missing or empty ${region.key} during ${sample.phase} at ${sample.at}`
      );
    }
    if (region.signature === 'loading') {
      throw new Error(`Observed empty ${region.key} placeholder`);
    }
    if (
      before &&
      !['root', 'map'].includes(region.key) &&
      region.signature !== before.signature
    ) {
      throw new Error(
        `Region last-good signature regressed for ${region.key} during ${sample.phase}: ${JSON.stringify({ before: before.signature, after: region.signature })}`
      );
    }
  }
  if (sample.layers.length !== 12) {
    throw new Error(`Expected 12 layers during ${sample.phase}`);
  }
  if (sample.charts.length !== 3) {
    throw new Error(`Expected 3 charts during ${sample.phase}`);
  }
  sample.layers.forEach((layer, index) => {
    const before = baseline.layers[index];
    if (
      !before ||
      !layer.controlId ||
      !layer.ownerId ||
      !layer.objectId ||
      layer.label !== before.label
    ) {
      throw new Error(
        `Layer ownership/order failed at ${index} during ${sample.phase}`
      );
    }
    if (layer.checked !== before.checked) {
      throw new Error(`Layer setting changed for ${layer.label}`);
    }
    if (
      layer.objectId !== before.objectId ||
      layer.renderedCount !== layer.expectedCount ||
      layer.expectedCount !== before.expectedCount ||
      layer.signature !== before.signature
    ) {
      throw new Error(`Rendered count regressed for ${layer.label}`);
    }
  });
  sample.charts.forEach((chart, index) => {
    const before = baseline.charts[index];
    if (
      !before ||
      !chart.canvasId ||
      !chart.seriesOwnerId ||
      !chart.objectId ||
      chart.label !== before.label
    ) {
      throw new Error(`Chart ownership/order failed at ${index}`);
    }
    if (
      chart.objectId !== before.objectId ||
      !/^\d+x\d+:1:stable$/.test(chart.signature) ||
      chart.seriesCount <= 0 ||
      chart.seriesCount !== before.seriesCount ||
      chart.signature !== before.signature
    ) {
      throw new Error(`Chart series/signature regressed for ${chart.label}`);
    }
  });
  if (
    sample.focusId !== baseline.focusId ||
    sample.focusLabel !== baseline.focusLabel ||
    sample.scrollX !== baseline.scrollX ||
    sample.scrollY !== baseline.scrollY ||
    sample.poiFilter !== baseline.poiFilter ||
    sample.disclosures.join() !== baseline.disclosures.join()
  ) {
    throw new Error(
      `Operator state changed during ${sample.phase} at ${sample.at}`
    );
  }
}

export function assertRetainedRenderSample(
  sample: LifecycleSample,
  baseline: LifecycleSample
) {
  for (const region of sample.regions) {
    if (!region.identity || region.width <= 0 || region.height <= 0) {
      throw new Error(`Missing retained ${region.key} during ${sample.phase}`);
    }
  }
  sample.layers.forEach((layer, index) => {
    const before = baseline.layers[index];
    if (!before || layer.objectId !== before.objectId) {
      throw new Error(`Retained layer changed for ${layer.label}`);
    }
  });
  sample.charts.forEach((chart, index) => {
    const before = baseline.charts[index];
    if (
      !before ||
      chart.objectId !== before.objectId ||
      chart.seriesCount <= 0 ||
      chart.seriesCount !== before.seriesCount
    ) {
      throw new Error(`Retained chart changed for ${chart.label}`);
    }
  });
}

function assertRequestCorrelation(
  evidence: Awaited<ReturnType<typeof captureCdpContinuity>>
) {
  const primary = evidence.cdpNetworkLedger.filter((record) =>
    record.url.startsWith('/api/')
  );
  if (!primary.length) throw new Error('No browser-originated API CDP records');
  const samplePhases = new Map<string, Set<string>>();
  for (const sample of evidence.eventLedger.samples) {
    const request = sample.request;
    if (!request || !('cdpRequestId' in request)) continue;
    const phases = samplePhases.get(request.cdpRequestId) ?? new Set<string>();
    phases.add(sample.phase);
    samplePhases.set(request.cdpRequestId, phases);
  }
  for (const record of primary) {
    if (
      !record.cdpRequestId ||
      !record.url ||
      !record.method ||
      !record.type ||
      record.responseTimestamp === null ||
      record.terminalOutcome === 'pending' ||
      record.terminalTimestamp === null ||
      record.terminalTimestamp < record.requestTimestamp
    ) {
      throw new Error(`Incomplete CDP lifecycle: ${JSON.stringify(record)}`);
    }
    const phases = samplePhases.get(record.cdpRequestId);
    if (
      !phases?.has('cdp-request-start') ||
      !phases.has('cdp-request-terminal')
    ) {
      throw new Error(
        `CDP request ${record.cdpRequestId} lacks DOM correlation`
      );
    }
  }
  const eventNames = new Set(
    evidence.cdpNetworkEvents.map((event) => event.name)
  );
  for (const required of [
    'Network.requestWillBeSent',
    'Network.responseReceived',
    'Network.loadingFinished',
  ] as const) {
    if (!eventNames.has(required)) {
      throw new Error(`Missing browser-originated CDP event: ${required}`);
    }
  }
  const cycles = (kind: 'scheduled' | 'manual') =>
    new Set(
      evidence.fixtureRequestLedger
        .filter(
          (record) =>
            record.kind === kind &&
            record.source === 'telemetry' &&
            record.event === 'complete'
        )
        .map((record) => record.cycle)
    );
  if (cycles('scheduled').size < 5) {
    throw new Error('Fewer than five scheduled telemetry cycles completed');
  }
  if (cycles('manual').size < 1) {
    throw new Error('No actual manual telemetry cycle completed');
  }
  const manualCompletion = evidence.fixtureRequestLedger.some(
    (record) =>
      record.kind === 'manual' &&
      record.source === 'history' &&
      record.event === 'complete'
  );
  if (!manualCompletion)
    throw new Error('Manual history completion did not settle');
}

function assertMonotonic(values: readonly number[], label: string) {
  for (let index = 1; index < values.length; index += 1) {
    if (values[index]! < values[index - 1]!) {
      throw new Error(`Non-monotonic ${label} at index ${index}`);
    }
  }
}
