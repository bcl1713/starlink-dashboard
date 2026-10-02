import { satcomLineStyle } from './satcom-link-style';

interface OverviewMapLegendProps {
  aircraft: boolean;
  route: boolean;
  history: boolean;
  groundEntryPoint: boolean;
  plannedLink: boolean;
  linkState: 'normal' | 'warning' | null;
}

/** Layer samples use the scene's draw guards, including retained geometry. */
export function OverviewMapLegend({
  aircraft,
  route,
  history,
  groundEntryPoint,
  plannedLink,
  linkState,
}: OverviewMapLegendProps) {
  const entries = [
    {
      visible: aircraft,
      label: 'Aircraft',
      sample: 'globe-legend__marker globe-legend__marker--aircraft',
    },
    { visible: route, label: 'Planned route', sample: 'globe-legend__route' },
    {
      visible: history,
      label: 'Track history',
      sample: 'globe-legend__route globe-legend__route--history',
    },
    {
      visible: groundEntryPoint,
      label: 'Ground entry point',
      sample: 'globe-legend__marker globe-legend__marker--ground-entry',
    },
    {
      visible: plannedLink,
      label: 'Planned satellite link',
      sample: 'globe-legend__route globe-legend__route--planned-link',
    },
  ];
  return (
    <aside className="globe-legend" aria-label="Globe legend">
      <p className="globe-legend__title">Legend</p>
      <ul className="globe-legend__items">
        {entries
          .filter((entry) => entry.visible)
          .map((entry) => (
            <li key={entry.label}>
              <span
                className={entry.sample}
                aria-hidden="true"
                style={
                  entry.label === 'Planned satellite link'
                    ? { background: satcomLineStyle(linkState).core.color }
                    : undefined
                }
              />
              <span>{entry.label}</span>
            </li>
          ))}
      </ul>
    </aside>
  );
}
