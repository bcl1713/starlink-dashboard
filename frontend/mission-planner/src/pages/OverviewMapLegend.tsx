import { useId, useRef, useState, type ReactNode } from 'react';
import { satcomLineStyle } from './satcom-link-style';
import { TRAFFIC_PATH_STYLE } from './overview-traffic-style';

interface OverviewMapLegendProps {
  children?: ReactNode;
  collapsible?: boolean;
  countries?: boolean;
  subdivisions?: boolean;
  satellites?: boolean;
  adsb?: boolean;
  aircraft: boolean;
  route: boolean;
  history: boolean;
  groundEntryPoint: boolean;
  trafficPath: boolean;
  plannedLink: boolean;
  linkState: 'normal' | 'warning' | null;
}

/** Layer samples use the scene's draw guards, including retained geometry. */
export function OverviewMapLegend({
  children,
  collapsible = false,
  countries = false,
  subdivisions = false,
  satellites = false,
  adsb = false,
  aircraft,
  route,
  history,
  groundEntryPoint,
  trafficPath,
  plannedLink,
  linkState,
}: OverviewMapLegendProps) {
  const [expanded, setExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const entries = [
    {
      visible: countries,
      label: 'Country borders',
      sample: 'globe-legend__route globe-legend__route--countries',
    },
    {
      visible: subdivisions,
      label: 'State/province borders',
      sample: 'globe-legend__route globe-legend__route--subdivisions',
    },
    {
      visible: adsb,
      label: 'ADS-B aircraft',
      sample: 'globe-legend__marker globe-legend__marker--adsb',
    },
    {
      visible: satellites,
      label: 'Satellites',
      sample: 'globe-legend__marker globe-legend__marker--orbital',
    },
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
      visible: trafficPath,
      label: 'Traffic path',
      sample: 'globe-legend__route globe-legend__route--traffic-path',
    },
    {
      visible: plannedLink,
      label: 'Planned satellite link',
      sample: 'globe-legend__route globe-legend__route--planned-link',
    },
  ];
  return (
    <aside
      className="globe-legend"
      aria-label="Globe legend"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && collapsible && expanded) {
          event.stopPropagation();
          setExpanded(false);
          toggle.current?.focus();
        }
      }}
    >
      {collapsible ? (
        <button
          ref={toggle}
          type="button"
          className="globe-legend__toggle"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((value) => !value)}
        >
          Legend
        </button>
      ) : (
        <p className="globe-legend__title">Legend</p>
      )}
      {(countries || subdivisions) && (
        <p className="globe-legend__boundary-note">
          Natural Earth · dashed: disputed/uncertain
        </p>
      )}
      <div id={listId} hidden={collapsible && !expanded}>
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
                      : entry.label === 'Traffic path'
                        ? { background: TRAFFIC_PATH_STYLE.core.color }
                        : undefined
                  }
                />
                <span>{entry.label}</span>
              </li>
            ))}
        </ul>
        {children}
      </div>
    </aside>
  );
}
