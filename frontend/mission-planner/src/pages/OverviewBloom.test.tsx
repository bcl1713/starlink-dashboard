/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewBloom, OverviewBloomScene } from './OverviewBloom';
import {
  useOverviewAmbientIntensity,
  useOverviewAtmosphereIntensity,
  useOverviewBloom,
  useOverviewBloomEmission,
} from './overview-bloom-mode';

vi.mock('../experiments/bloom/OverviewBloomComposer', () => ({
  OverviewBloomComposer: ({
    mode,
    settings,
  }: {
    mode: string;
    settings: { threshold: number };
  }) => (
    <output data-testid="composer">
      {mode}:{settings.threshold}
    </output>
  ),
}));
function Scene() {
  const active = useOverviewBloom(),
    emission = useOverviewBloomEmission();
  const ambientIntensity = useOverviewAmbientIntensity();
  const atmosphereIntensity = useOverviewAtmosphereIntensity();
  return (
    <output data-testid="actual-scene">
      {JSON.stringify({
        active,
        emission,
        ambientIntensity,
        atmosphereIntensity,
      })}
    </output>
  );
}
afterEach(cleanup);
it('enables the selected bloom preset on ordinary Overview without showing debug controls', () => {
  render(
    <OverviewBloom debug={false}>
      <Scene />
      <OverviewBloomScene />
    </OverviewBloom>
  );
  expect(screen.queryByLabelText('Temporary bloom tuning')).toBeNull();
  expect(screen.getByTestId('composer').textContent).toBe('bloom:0');
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).active
  ).toBe(true);
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).ambientIntensity
  ).toBe(0.1);
});
it('applies controls to the existing scene and copies all current values without a separate app', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  });
  const { rerender } = render(
    <OverviewBloom debug>
      <Scene />
      <OverviewBloomScene />
    </OverviewBloom>
  );
  expect(
    screen.getByRole('spinbutton', { name: 'Bloom strength' })
  ).toHaveProperty('value', '0.15');
  expect(
    screen.getByRole('spinbutton', { name: 'Bloom threshold' })
  ).toHaveProperty('value', '0');
  expect(
    screen.getByRole('spinbutton', { name: 'Bloom radius' })
  ).toHaveProperty('value', '0');
  expect(screen.getByLabelText('City light color')).toHaveProperty(
    'value',
    '#ffbe6f'
  );
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).emission
  ).toEqual({
    cities: 4,
    cityColor: '#ffbe6f',
    lines: 1.7,
    particles: 0.1,
    pois: 25,
    aircraft: 1.7,
  });
  fireEvent.change(
    screen.getByRole('slider', { name: 'Atmosphere glow slider' }),
    { target: { value: '0.35' } }
  );
  fireEvent.change(
    screen.getByRole('slider', { name: 'Ambient lighting slider' }),
    { target: { value: '0.15' } }
  );
  fireEvent.change(
    screen.getByRole('spinbutton', { name: 'Cities emission' }),
    {
      target: { value: '36' },
    }
  );
  fireEvent.change(screen.getByLabelText('City light color'), {
    target: { value: '#ffaa33' },
  });
  fireEvent.change(
    screen.getByRole('spinbutton', { name: 'Bloom threshold' }),
    {
      target: { value: '0.4' },
    }
  );
  fireEvent.change(
    screen.getByRole('spinbutton', { name: 'Aircraft emission' }),
    {
      target: { value: '12' },
    }
  );
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).emission.cities
  ).toBe(36);
  expect(screen.getByTestId('composer').textContent).toBe('bloom:0.4');
  fireEvent.click(screen.getByRole('button', { name: 'Copy settings' }));
  await waitFor(() => expect(writeText).toHaveBeenCalled());
  const report = JSON.parse(writeText.mock.calls[0][0]);
  expect(report.scene).toBe('overview');
  expect(report.settings.threshold).toBe(0.4);
  expect(report.emissions).toMatchObject({
    cities: 36,
    cityColor: '#ffaa33',
    aircraft: 12,
  });
  expect(report.emissionOverridesActive).toBe(true);
  expect(report.lighting).toEqual({
    ambientIntensity: 0.15,
    atmosphereIntensity: 0.35,
  });
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).ambientIntensity
  ).toBe(0.15);
  expect(report).not.toHaveProperty('scenario');
  fireEvent.change(screen.getByLabelText('Rendering mode'), {
    target: { value: 'current' },
  });
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).active
  ).toBe(false);
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).ambientIntensity
  ).toBe(0.5);
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!)
      .atmosphereIntensity
  ).toBe(1);
  fireEvent.change(screen.getByLabelText('Rendering mode'), {
    target: { value: 'bloom' },
  });
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).ambientIntensity
  ).toBe(0.15);
  fireEvent.click(screen.getByRole('button', { name: 'Reset tuning' }));
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!).ambientIntensity
  ).toBe(0.1);
  expect(
    JSON.parse(screen.getByTestId('actual-scene').textContent!)
      .atmosphereIntensity
  ).toBe(0);
  rerender(
    <OverviewBloom debug={false}>
      <Scene />
      <OverviewBloomScene />
    </OverviewBloom>
  );
  expect(screen.getByTestId('composer').textContent).toBe('bloom:0');
  expect(screen.queryByLabelText('Temporary bloom tuning')).toBeNull();
});
