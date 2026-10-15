import { describe, expect, it } from 'vitest';
import { satcomLineStyle } from './satcom-link-style';

describe('satcom active-link style', () => {
  it('uses the normal blue line style for a normal active X-band link', () => {
    expect(satcomLineStyle('normal')).toMatchObject({
      outer: { color: '#1d4ed8' },
      glow: { color: '#3b82f6' },
      core: { color: '#3b82f6' },
    });
  });

  it('uses the warning red line style for a warning active X-band link', () => {
    expect(satcomLineStyle('warning')).toMatchObject({
      outer: { color: '#b91c1c' },
      glow: { color: '#ef4444' },
      core: { color: '#ef4444' },
    });
  });
});
