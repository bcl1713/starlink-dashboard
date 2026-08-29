import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { Button } from '../components/ui/button';

describe('React DOM test environment', () => {
  test('renders the application Button component into jsdom', () => {
    render(<Button>Mission planner unit test environment</Button>);

    expect(
      screen.getByRole('button', {
        name: 'Mission planner unit test environment',
      })
    ).toBeInTheDocument();
  });

  test('cleans up DOM between tests', () => {
    expect(
      screen.queryByRole('button', {
        name: 'Mission planner unit test environment',
      })
    ).not.toBeInTheDocument();
  });
});
