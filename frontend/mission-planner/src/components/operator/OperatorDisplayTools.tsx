import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { OverviewDisplaySettingsCard } from '@/pages/OverviewDisplaySettingsCard';
import { OverviewLinkSettingsCard } from '@/pages/OverviewLinkSettingsCard';
import { OverviewBoundarySettingsCard } from '@/pages/OverviewBoundarySettingsCard';
import { OverviewHistorySettingsCard } from '@/pages/OverviewHistorySettingsCard';
import { OverviewPresetsCard } from './OverviewPresetsCard';

export function OperatorDisplayTools({ missionId }: { missionId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section
      id="display-tools"
      aria-label="Display tools"
      className="scroll-mt-4 space-y-4 rounded-xl border bg-card p-4"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto font-semibold">Display tools</h2>
        <Button
          variant="outline"
          aria-expanded={open}
          aria-controls="operator-display-controls"
          onClick={() => setOpen(!open)}
        >
          {open ? 'Hide' : 'Show'} display controls
        </Button>
        <Link
          to="/overview"
          className="inline-flex min-h-11 items-center rounded-md border px-3"
        >
          Open Overview
        </Link>
        <Link
          to="/configuration"
          className="inline-flex min-h-11 items-center rounded-md border px-3"
        >
          Display settings
        </Link>
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
      {open && (
        <div id="operator-display-controls" className="space-y-5">
          <OverviewDisplaySettingsCard />
          <p className="text-sm text-muted-foreground">
            Shared across all Overview displays on this installation: visibility
            switches, presets and history window. These settings also apply from
            other devices. Recenter above targets a connected window in this
            browser only.
          </p>
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
        </div>
      )}
    </section>
  );
}
