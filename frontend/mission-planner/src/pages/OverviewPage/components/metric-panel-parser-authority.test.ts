import { describe, expect, it } from 'vitest';

import latencySource from './metric-panel-latency.ts?raw';
import timeSource from './metric-panel-time.ts?raw';
import authoritySource from '../../../services/monitoring-timestamp-internal.ts?raw';

const obsoleteLatencyTimeModule = import.meta.glob(
  './metric-panel-latency-time.ts',
  {
    eager: true,
    import: 'default',
    query: '?raw',
  }
);

describe('metric panel timestamp parser authority', () => {
  it('keeps the exact parser in one internal service authority', () => {
    expect(Object.keys(obsoleteLatencyTimeModule)).toHaveLength(0);
    expect(latencySource).toContain(
      '../../../services/monitoring-timestamp-internal'
    );
    expect(latencySource).not.toMatch(/timestampPattern|daysFromCivil/);
    expect(latencySource).not.toMatch(/parseOffsetSeconds|TimeClip/);
    expect(latencySource).not.toMatch(/[+-]\\d\{2\}:\\d\{2\}/);
    expect(timeSource).not.toMatch(/timestampPattern|daysFromCivil/);
    expect(timeSource).not.toMatch(/parseOffsetSeconds|civilFromDays/);
    expect(timeSource).not.toMatch(/[+-]\\d\{2\}:\\d\{2\}/);
    expect(authoritySource.match(/const timestampPattern/g)).toHaveLength(1);
    expect(authoritySource).toContain('daysFromCivil');
    expect(authoritySource).toContain('parseOffsetSeconds');
    expect(authoritySource).toContain('timeClipSeconds');
  });
});
