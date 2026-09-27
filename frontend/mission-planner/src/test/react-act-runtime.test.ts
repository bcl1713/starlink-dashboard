import * as React from 'react';
import { describe, expect, it } from 'vitest';

describe('React unit-test runtime', () => {
  it('provides a callable act export', () => {
    expect(React.act).toEqual(expect.any(Function));
  });
});
