// @vitest-environment jsdom
import { it, expect } from 'vitest';
it('mounts both complete synthetic regional intervals in the actual overlay label', async () => {
  const { mountProofLabel } = await import(
    '../../tests/e2e/support/aviation-weather-proof/proof-label'
  );
  const label = mountProofLabel({
    schema: 'aviation-weather-v1',
    representation: 'latlon-grid-v1',
    grid: {
      width: 720,
      height: 361,
      longitude_start: -180,
      longitude_step: 0.5,
      latitude_start: 90,
      latitude_step: -0.5,
    },
    components: {},
    mask: { byte_size: 259920, sha256: '0'.repeat(64) },
    source_id: 'SYNTHETIC regional interval control',
    region_intervals: [
      { region: 'A', scan_start_ms: 0, scan_end_ms: 1000 },
      { region: 'B', scan_start_ms: 2000, scan_end_ms: 3000 },
    ],
  });
  try {
    expect(document.querySelector('[data-aviation-proof]')).toBe(label);
    expect(label.textContent).toContain('SYNTHETIC regional interval control');
    expect(label.textContent).toContain(
      'A: 1970-01-01T00:00:00.000Z – 1970-01-01T00:00:01.000Z'
    );
    expect(label.textContent).toContain(
      'B: 1970-01-01T00:00:02.000Z – 1970-01-01T00:00:03.000Z'
    );
    expect(label.style.display).not.toBe('none');
  } finally {
    label.dispose();
  }
});

it('declares a scalar palette, ticks, opacity and unavailable mask meaning', async () => {
  const { mountProofLabel } = await import(
    '../../tests/e2e/support/aviation-weather-proof/proof-label'
  );
  const label = mountProofLabel({
    schema: 'aviation-weather-v1',
    representation: 'latlon-grid-v1',
    components: {},
    mask: { byte_size: 1, sha256: '' },
  } as import('../../tests/e2e/support/aviation-weather-proof/model').Descriptor);
  try {
    const legend = label.querySelector('[data-aviation-palette]');
    expect(legend).not.toBeNull();
    expect(legend?.textContent).toContain('190 K');
    expect(legend?.textContent).toContain('250 K');
    expect(legend?.textContent).toContain('310 K');
    expect(legend?.textContent).toContain('40%');
    expect(legend?.textContent).toContain('Unavailable');
  } finally {
    label.dispose();
  }
});
it('null aggregate scans cannot fabricate an epoch interval', async () => {
  const { labels } = await import(
    '../../tests/e2e/support/aviation-weather-proof/model'
  );
  const text = labels({
    representation: 'latlon-grid-v1',
    scan_start_ms: null,
    scan_end_ms: null,
    region_intervals: [{ region: 'A', scan_start_ms: 1000, scan_end_ms: 2000 }],
  } as unknown as import('../../tests/e2e/support/aviation-weather-proof/model').Descriptor);
  expect(text).not.toContain('1970-01-01T00:00:00.000Z');
});

it('moves the palette into fullscreen and removes its event listener on disposal', async () => {
  const { mountProofLabel } = await import(
    '../../tests/e2e/support/aviation-weather-proof/proof-label'
  );
  const label = mountProofLabel({
    representation: 'latlon-grid-v1',
  } as import('../../tests/e2e/support/aviation-weather-proof/model').Descriptor);
  const fullscreen = document.createElement('div');
  document.body.append(fullscreen);
  Object.defineProperty(document, 'fullscreenElement', {
    value: fullscreen,
    configurable: true,
  });
  document.dispatchEvent(new Event('fullscreenchange'));
  expect(label.parentElement).toBe(fullscreen);
  label.dispose();
  Object.defineProperty(document, 'fullscreenElement', {
    value: null,
    configurable: true,
  });
  document.dispatchEvent(new Event('fullscreenchange'));
  expect(label.isConnected).toBe(false);
  fullscreen.remove();
});
