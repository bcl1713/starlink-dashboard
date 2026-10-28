/** @vitest-environment jsdom */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { TuningPanel } from './TuningPanel';
import { DEFAULT_BLOOM } from './contracts';
import { DEFAULT_EMISSION } from '../../pages/overview-bloom-mode';

it('offers shareable current JSON even without timing runs and provides a clipboard fallback', async () => {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error('unavailable')) },
  });
  render(
    <TuningPanel
      active
      busy={false}
      settings={DEFAULT_BLOOM}
      emissions={DEFAULT_EMISSION}
      isolateCities={false}
      onSettings={() => {}}
      onEmissions={() => {}}
      onIsolate={() => {}}
      onCityPreset={() => {}}
      onReset={() => {}}
      getReport={() => ({
        emissions: { cities: 42, cityColor: '#ffaa33' },
        sourceSha: 'test',
      })}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Copy settings' }));
  await waitFor(() =>
    expect(
      screen.getByText('Select the JSON below and copy it into our chat.')
    ).toBeTruthy()
  );
  const json = screen.getByLabelText('Feedback JSON') as HTMLTextAreaElement;
  expect(JSON.parse(json.value).emissions.cities).toBe(42);
  expect(
    screen
      .getByRole('button', { name: 'Download settings.json' })
      .hasAttribute('disabled')
  ).toBe(false);
});
