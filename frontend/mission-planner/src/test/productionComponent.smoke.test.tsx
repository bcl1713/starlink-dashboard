// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Card } from '@/components/ui/card';

describe('production component harness', () => {
  it('renders a component graph that traverses the application alias', () => {
    render(<Card className="smoke-marker">Alias resolved</Card>);

    expect(screen.getByText('Alias resolved').className).toContain(
      'smoke-marker'
    );
  });

  it('starts the next test with a clean DOM', () => {
    expect(screen.queryByText('Alias resolved')).toBeNull();
  });
});
