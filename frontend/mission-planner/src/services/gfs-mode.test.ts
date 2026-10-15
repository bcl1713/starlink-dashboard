import { expect, it } from 'vitest';

it.each([
  [false, false, false, false],
  [true, false, true, false],
  [false, true, false, true],
  [true, true, true, false],
])(
  'resolves %s/%s without mutating the snapshot',
  async (winds, temperature, wind, temp) => {
    const modulePath = './gfs-mode';
    const { resolveGfsFlags } = await import(modulePath);
    const flags = Object.freeze({ winds, temperature });
    expect(resolveGfsFlags(flags)).toEqual({ winds: wind, temperature: temp });
    expect(flags).toEqual({ winds, temperature });
  }
);
