/** @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { expect, it, vi } from 'vitest';
import { OverviewMarkerDebug } from './OverviewMarkerDebug';
import { DEFAULT_CHEVRON_SETTINGS } from './overview-chevron-settings';

it('lets the user tune, copy and reset the actual marker settings', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  });
  function Harness() {
    const [settings, setSettings] = useState(DEFAULT_CHEVRON_SETTINGS);
    return <OverviewMarkerDebug settings={settings} onChange={setSettings} />;
  }
  render(<Harness />);
  fireEvent.change(screen.getByLabelText('Our aircraft size'), {
    target: { value: '9' },
  });
  fireEvent.change(screen.getByLabelText('Glow width'), {
    target: { value: '2.4' },
  });
  const values = screen.getByLabelText(
    'Marker settings to share'
  ) as HTMLTextAreaElement;
  expect(JSON.parse(values.value)).toMatchObject({
    ownSizePixels: 9,
    glowWidthPixels: 2.4,
  });
  fireEvent.click(screen.getByRole('button', { name: 'Copy settings' }));
  expect(writeText).toHaveBeenCalledWith(values.value);
  fireEvent.click(screen.getByRole('button', { name: 'Reset defaults' }));
  expect(JSON.parse(values.value)).toEqual(DEFAULT_CHEVRON_SETTINGS);
});
