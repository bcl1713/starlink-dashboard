import { Switch } from '@/components/ui/switch';
import { ConfigurationSection } from './ConfigurationSection';
import { useId } from 'react';
import { useOverviewLinkSettings } from '@/hooks/api/useOverviewLinkSettings';
import { useUpdateOverviewLinkSettings } from '@/hooks/api/useUpdateOverviewLinkSettings';

const groups = {
  panels: {
    title: 'Overview panels',
    description:
      'Choose the information panels shown on all Overview displays.',
    controls: [
      {
        field: 'operational_clocks_enabled',
        label: 'Operational clocks panel',
        description: 'Show the configured operational clocks.',
      },
      {
        field: 'arrival_panel_enabled',
        label: 'Departure and arrival panel',
        description: 'Show departure, arrival and upcoming POI timing.',
      },
      {
        field: 'planned_satellite_panel_enabled',
        label: 'Planned satellite panel',
        description: 'Show the selected satellite and planning state.',
      },
      {
        field: 'map_status_enabled',
        label: 'Map status panel',
        description: 'Show map, weather and geographic source notices.',
      },
      {
        field: 'legend_enabled',
        label: 'Map legend',
        description: 'Show keys for visible layers and atmosphere data.',
      },
    ],
  },
  map: {
    title: 'Route and points of interest',
    description: 'Choose the mission layers shown on the globe.',
    controls: [
      {
        field: 'planned_route_enabled',
        label: 'Planned route',
        description: 'Show the mission route on the globe.',
      },
      {
        field: 'poi_markers_enabled',
        label: 'Points of interest',
        description: 'Show mission POI markers and labels.',
      },
    ],
  },
  network: {
    title: 'Network map layers',
    description:
      'Choose network links and satellite markers shown on Overview.',
    controls: [
      {
        field: 'starshield_link_enabled',
        label: 'Starshield data link',
        description: 'Show aircraft-to-PoP traffic.',
      },
      {
        field: 'orbital_traffic_enabled',
        label: 'Orbital traffic view',
        description:
          'Show the experimental constellation and inferred traffic path.',
      },
      {
        field: 'x_band_link_enabled',
        label: 'X-band data link',
        description: 'Show the configured satellite link and its activity.',
      },
      {
        field: 'configured_satellites_enabled',
        label: 'Configured satellite markers',
        description: 'Show configured X-band satellites and their labels.',
      },
      {
        field: 'ground_entry_point_enabled',
        label: 'Ground entry point',
        description: 'Show the ground entry point marker and label.',
      },
    ],
  },
  aircraft: {
    title: 'Own aircraft',
    description: 'Choose the tracked aircraft layers shown on Overview.',
    controls: [
      {
        field: 'aircraft_marker_enabled',
        label: 'Own aircraft marker',
        description: 'Show the current aircraft position and heading.',
      },
      {
        field: 'aircraft_history_enabled',
        label: 'Aircraft history',
        description: 'Show the aircraft’s flown track on the globe.',
      },
    ],
  },
  metrics: {
    title: 'Network metric panels',
    description: 'Show or hide each network graph independently.',
    controls: [
      {
        field: 'latency_panel_enabled',
        label: 'Network latency panel',
        description: 'Show latency and its history.',
      },
      {
        field: 'downlink_panel_enabled',
        label: 'Downlink throughput panel',
        description: 'Show downlink throughput and its history.',
      },
      {
        field: 'uplink_panel_enabled',
        label: 'Uplink throughput panel',
        description: 'Show uplink throughput and its history.',
      },
      {
        field: 'packet_loss_panel_enabled',
        label: 'Packet loss panel',
        description: 'Show packet loss and its history.',
      },
      {
        field: 'obstruction_panel_enabled',
        label: 'Dish obstruction panel',
        description: 'Show dish obstruction and its history.',
      },
    ],
  },
} as const;

export function OverviewLinkSettingsCard({
  group = 'network',
}: {
  group?: keyof typeof groups;
}) {
  const { data, isError } = useOverviewLinkSettings();
  const {
    mutate,
    isPending,
    isSuccess,
    isError: saveError,
  } = useUpdateOverviewLinkSettings();
  const id = useId();
  const { title, description, controls } = groups[group];

  return (
    <ConfigurationSection title={title} description={description}>
      <div className="divide-y">
        {controls.map(({ field, label, description }) => (
          <div key={field} className="min-w-0 py-4 first:pt-0 last:pb-0">
            <label className="flex min-h-11 items-center justify-between gap-6 text-sm font-medium">
              <span>
                <span className="block">{label}</span>
                <span
                  id={`${id}-${field}`}
                  className="mt-1 block text-sm font-normal text-muted-foreground"
                >
                  {description}
                </span>
              </span>
              <Switch
                aria-label={label}
                checked={data ? (data[field] ?? true) : false}
                disabled={!data || isPending}
                aria-describedby={`${id}-${field}`}
                onChange={(event) => mutate({ [field]: event.target.checked })}
              />
            </label>
          </div>
        ))}
      </div>
      {!data && !isError && <p role="status">Loading layer settings…</p>}
      {isError && <p role="alert">Layer settings unavailable</p>}
      {isPending && <p role="status">Saving layer settings…</p>}
      {isSuccess && <p role="status">Layer settings saved</p>}
      {saveError && (
        <p role="alert">Unable to save layer settings. Please try again.</p>
      )}
    </ConfigurationSection>
  );
}
