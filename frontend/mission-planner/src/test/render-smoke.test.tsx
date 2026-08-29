import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

function SmokeComponent() {
  return <main>Mission planner unit test environment</main>;
}

describe('React DOM test environment', () => {
  test('renders React content into jsdom', () => {
    render(<SmokeComponent />);

    expect(
      screen.getByText('Mission planner unit test environment'),
    ).toBeInTheDocument();
  });
});
