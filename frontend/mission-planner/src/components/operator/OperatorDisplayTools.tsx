import { Link } from 'react-router-dom';
import { OverviewDisplaySettingsCard } from '@/pages/OverviewDisplaySettingsCard';
import { OverviewLinkSettingsCard } from '@/pages/OverviewLinkSettingsCard';
import { OverviewBoundarySettingsCard } from '@/pages/OverviewBoundarySettingsCard';
import { OverviewHistorySettingsCard } from '@/pages/OverviewHistorySettingsCard';
import { OverviewWeatherSettingsCard } from '@/pages/weather/OverviewWeatherSettingsCard';
import { OverviewAdsbSettingsCard } from '@/pages/adsb/OverviewAdsbSettingsCard';
import { AviationSettingsCard } from '@/pages/aviation-weather/AviationSettingsCard';
import { OverviewPresetsCard } from './OverviewPresetsCard';

export function OperatorDisplayTools({ missionId }: { missionId: string }) {
  return (
    <section
      id="display-tools"
      aria-label="Display tools"
      className="scroll-mt-4 space-y-4 rounded-xl border bg-card p-4"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto font-semibold">Display tools</h2>
        <Link
          to={
            missionId
              ? `/missions/${encodeURIComponent(missionId)}`
              : '/missions'
          }
          className="inline-flex min-h-11 items-center rounded-md border px-3"
        >
          Mission planning
        </Link>
      </div>
      <div id="operator-display-controls" className="space-y-5">
        <nav
          aria-label="Display control groups"
          className="flex flex-wrap gap-2"
        >
          <button
            className="ws-button"
            onClick={() =>
              document
                .getElementById('operator-camera-controls')
                ?.scrollIntoView({ block: 'start' })
            }
          >
            Camera
          </button>
          <button
            className="ws-button"
            onClick={() =>
              document
                .getElementById('operator-visibility-controls')
                ?.scrollIntoView({ block: 'start' })
            }
          >
            Visibility and presets
          </button>
          <button
            className="ws-button"
            onClick={() =>
              document
                .getElementById('operator-weather-controls')
                ?.scrollIntoView({ block: 'start' })
            }
          >
            Weather and ADS-B
          </button>
        </nav>
        <div id="operator-camera-controls" className="scroll-mt-3">
          <OverviewDisplaySettingsCard />
        </div>
        <p className="text-sm text-muted-foreground">
          Shared across all Overview displays on this installation: visibility
          switches, presets and history window. These settings also apply from
          other devices. Recenter above targets a connected window in this
          browser only.
        </p>
        <h3
          id="operator-visibility-controls"
          className="font-semibold scroll-mt-3"
        >
          Visibility and presets
        </h3>
        <OverviewPresetsCard />
        <OverviewHistorySettingsCard live />
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <OverviewLinkSettingsCard />
          <OverviewLinkSettingsCard group="metrics" />
          <OverviewLinkSettingsCard group="map" />
          <OverviewLinkSettingsCard group="panels" />
          <OverviewLinkSettingsCard group="aircraft" />
          <OverviewBoundarySettingsCard />
        </div>
        <h3
          id="operator-weather-controls"
          className="font-semibold scroll-mt-3"
        >
          Weather and aircraft
        </h3>
        <div className="grid items-start gap-4 md:grid-cols-2">
          <OverviewWeatherSettingsCard />
          <OverviewAdsbSettingsCard controlsOnly />
        </div>
        <AviationSettingsCard controlsOnly />
      </div>
    </section>
  );
}
