/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  render,
  screen,
  within,
  fireEvent,
} from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OverviewMapLegend } from './OverviewMapLegend';
afterEach(cleanup);
const all = {
  aircraft: true,
  route: true,
  history: true,
  groundEntryPoint: true,
  trafficPath: true,
  plannedLink: true,
  linkState: 'normal' as const,
};
describe('rendered map layers', () => {
  it('identifies all six rendered layers without diagnostic controls', () => {
    render(<OverviewMapLegend {...all} />);
    const legend = screen.getByRole('complementary', { name: 'Globe legend' });
    expect(
      within(legend)
        .getAllByRole('listitem')
        .map((row) => row.textContent)
    ).toEqual([
      'Aircraft',
      'Planned route',
      'Track history',
      'Ground entry point',
      'Traffic path',
      'Planned satellite link',
    ]);
    expect(legend.querySelector('select, strong, input')).toBeNull();
    expect(legend.querySelectorAll('[aria-hidden="true"]')).toHaveLength(6);
  });
  it.each([
    ['aircraft', 'Aircraft'],
    ['route', 'Planned route'],
    ['history', 'Track history'],
    ['groundEntryPoint', 'Ground entry point'],
    ['trafficPath', 'Traffic path'],
    ['plannedLink', 'Planned satellite link'],
  ])('omits an undrawn %s layer', (property, label) => {
    render(<OverviewMapLegend {...all} {...{ [property]: false }} />);
    expect(screen.queryByText(label)).toBeNull();
    expect(screen.getAllByRole('listitem')).toHaveLength(5);
  });
  it('does not manufacture entries when no layers are rendered', () => {
    render(
      <OverviewMapLegend
        aircraft={false}
        route={false}
        history={false}
        groundEntryPoint={false}
        trafficPath={false}
        plannedLink={false}
        linkState={null}
      />
    );
    expect(screen.queryByRole('listitem')).toBeNull();
  });
});

// Catches disclosure that hides state or loses dismissal focus.
it('discloses one list and restores focus on Escape', () => {
  render(<OverviewMapLegend {...all} collapsible />);
  const toggle = screen.getByRole('button', { name: 'Legend' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('list')).toBeNull();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getAllByRole('listitem')).toHaveLength(6);
  fireEvent.keyDown(screen.getByRole('list'), { key: 'Escape' });
  expect(toggle).toHaveFocus();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

it('uses the scene violet sample independently of an X-band warning', () => {
  render(<OverviewMapLegend {...all} linkState="warning" />);
  expect(screen.getByText('Traffic path').previousElementSibling).toHaveStyle({
    background: '#c084fc',
  });
  expect(
    screen.getByText('Planned satellite link').previousElementSibling
  ).toHaveStyle({ background: '#ef4444' });
});

it('includes Satellites only when eligible sprites actually draw', () => {
  const view = render(<OverviewMapLegend {...all} satellites={false} />);
  expect(screen.queryByText('Satellites')).toBeNull();
  view.rerender(<OverviewMapLegend {...all} satellites />);
  expect(screen.getByText('Satellites')).toBeInTheDocument();
});

it('adds ADS-B only when its layer has active contacts', () => {
  const props = {
    aircraft: false,
    route: false,
    history: false,
    groundEntryPoint: false,
    trafficPath: false,
    plannedLink: false,
    linkState: null,
  };
  const view = render(<OverviewMapLegend {...props} adsb />);
  expect(screen.getByText('ADS-B aircraft')).not.toBeNull();
  view.rerender(<OverviewMapLegend {...props} adsb={false} />);
  expect(screen.queryByText('ADS-B aircraft')).toBeNull();
});
