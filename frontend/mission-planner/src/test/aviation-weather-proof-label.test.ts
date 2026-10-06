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
    label.remove();
  }
});
