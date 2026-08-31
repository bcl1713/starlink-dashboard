import type { captureCdpContinuity } from './overview-cdp-capture';
import type { LifecycleSample } from './overview-lifecycle-types';

export function assertContinuityEvidence(
  evidence: Awaited<ReturnType<typeof captureCdpContinuity>>
) {
  const { eventLedger, frames, requestLedger } = evidence;
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
  assertRequestCorrelation(evidence);

  const observedIds = new Set(
    eventLedger.samples.flatMap((sample) =>
      sample.request ? [sample.request.id] : []
    )
  );
  const measuredErrors = requestLedger.filter(
    (record) =>
      observedIds.has(record.id) &&
      record.firstParty &&
      ['error', 'failed', 'blocked'].includes(record.event)
  );
  if (measuredErrors.length) {
    throw new Error(
      `Measured first-party errors: ${JSON.stringify(measuredErrors)}`
    );
  }
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
    if (/^\d+:Loading$/i.test(region.signature)) {
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
      !/^\d+x\d+:[1-9]\d*:[\da-f]+$/.test(chart.signature) ||
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
  const measured = evidence.eventLedger.samples.flatMap((sample) =>
    sample.request ? [sample] : []
  );
  const byId = new Map<string, Set<string>>();
  for (const sample of measured) {
    const request = sample.request!;
    if (!request.id || !request.source || request.cycle < 1 || !request.kind) {
      throw new Error(`Incomplete request correlation at ${sample.at}`);
    }
    const phases = byId.get(request.id) ?? new Set<string>();
    phases.add(sample.phase);
    byId.set(request.id, phases);
  }
  for (const [id, phases] of byId) {
    if (!phases.has('request-start') || !phases.has('request-completion')) {
      throw new Error(`Request ${id} lacks start/completion observation`);
    }
  }
  const cycles = (kind: 'scheduled' | 'manual') =>
    new Set(
      measured
        .filter(
          (sample) =>
            sample.phase === 'request-completion' &&
            sample.request?.kind === kind &&
            sample.request.source === 'telemetry' &&
            sample.request.event === 'complete'
        )
        .map((sample) => sample.request!.cycle)
    );
  if (cycles('scheduled').size < 5) {
    throw new Error('Fewer than five scheduled telemetry cycles completed');
  }
  if (cycles('manual').size < 1) {
    throw new Error('No actual manual telemetry cycle completed');
  }
  const manualCompletion = measured.some(
    (sample) =>
      sample.phase === 'settle' &&
      sample.request?.kind === 'manual' &&
      sample.request.source === 'history' &&
      sample.request.event === 'complete'
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
