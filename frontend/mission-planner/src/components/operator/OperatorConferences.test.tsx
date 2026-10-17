/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as api from '@/services/operator';
import { health, page } from '@/test/operator-fixtures';
import { OperatorCommunications } from './OperatorCommunications';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('retains conference draft when the disclosure is closed and reopened', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorCommunications missionId="mission-a" />
    </QueryClientProvider>
  );
  const disclosure = screen
    .getByText('Conferences and customers')
    .closest('details')!;
  disclosure.open = true;
  fireEvent(disclosure, new Event('toggle'));
  fireEvent.click(
    await screen.findByRole('button', { name: 'New conference' })
  );
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Retain synthetic draft' },
  });
  disclosure.open = false;
  fireEvent(disclosure, new Event('toggle'));
  disclosure.open = true;
  fireEvent(disclosure, new Event('toggle'));
  expect(
    (screen.getByLabelText('Conference name (optional)') as HTMLInputElement)
      .value
  ).toBe('Retain synthetic draft');
  view.unmount();
  client.clear();
});
