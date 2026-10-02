/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { OverviewMapLegend } from './OverviewMapLegend';
afterEach(cleanup);
const all = {
  aircraft: true,
  route: true,
  history: true,
  groundEntryPoint: true,
  plannedLink: true,
  linkState: 'normal' as const,
};
describe('rendered map layers', () => {
  it('identifies all five rendered layers without diagnostic controls', () => {
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
      'Planned satellite link',
    ]);
    expect(legend.querySelector('select, strong, input')).toBeNull();
    expect(legend.querySelectorAll('[aria-hidden="true"]')).toHaveLength(5);
  });
  it.each([
    ['aircraft', 'Aircraft'],
    ['route', 'Planned route'],
    ['history', 'Track history'],
    ['groundEntryPoint', 'Ground entry point'],
    ['plannedLink', 'Planned satellite link'],
  ])('omits an undrawn %s layer', (property, label) => {
    render(<OverviewMapLegend {...all} {...{ [property]: false }} />);
    expect(screen.queryByText(label)).toBeNull();
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
  });
  it('does not manufacture entries when no layers are rendered', () => {
    render(
      <OverviewMapLegend
        aircraft={false}
        route={false}
        history={false}
        groundEntryPoint={false}
        plannedLink={false}
        linkState={null}
      />
    );
    expect(screen.queryByRole('listitem')).toBeNull();
  });
});
