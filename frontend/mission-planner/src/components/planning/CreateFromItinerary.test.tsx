/** @vitest-environment jsdom */
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, it, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CreateFromItinerary } from './CreateFromItinerary';
afterEach(cleanup);
it('offers the ordinary mission importer from the existing entry point', () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CreateFromItinerary open onClose={() => {}} onSuccess={() => {}} />
    </QueryClientProvider>
  );
  expect(screen.getByLabelText('Itinerary PDF')).toBeVisible();
  expect(screen.getByLabelText('Route KMLs')).toBeVisible();
  expect(
    screen.getByRole('button', { name: 'Generate mission' })
  ).toBeDisabled();
});
