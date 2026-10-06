import { useState } from 'react';
import {
  Activity,
  Globe2,
  Radio,
  Monitor,
  Plane,
  Satellite,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { OverviewCameraSettingsCard } from './OverviewCameraSettingsCard';
import { OverviewDisplaySettingsCard } from './OverviewDisplaySettingsCard';
import { OverviewHistorySettingsCard } from './OverviewHistorySettingsCard';
import { OverviewMapDiagnostics } from './OverviewMapDiagnostics';
import { OverviewLinkSettingsCard } from './OverviewLinkSettingsCard';
import { ManualXBandSelectionCard } from './ManualXBandSelectionCard';
import { OrbitalTrafficDiagnostics } from './OrbitalTrafficDiagnostics';
import { OverviewAdsbSettingsCard } from './adsb/OverviewAdsbSettingsCard';
import { OverviewAdsbSourceStatus } from './adsb/OverviewAdsbSourceStatus';
import { useOverviewClockSettings } from '@/hooks/api/useOverviewClockSettings';
import { GPSControlCard } from '../components/gps/GPSControlCard';
import { useUpdateOverviewClockSettings } from '@/hooks/api/useUpdateOverviewClockSettings';
import { OperationalClockSettingsForm } from './OperationalClockSettingsForm';
import { ConfigurationSection } from './ConfigurationSection';
import { OverviewWeatherSettingsCard } from './weather/OverviewWeatherSettingsCard';

const sections = [
  {
    value: 'overview',
    label: 'Overview',
    icon: Globe2,
    description: 'History, camera behavior, weather and operational clocks.',
  },
  {
    value: 'traffic',
    label: 'Network Traffic',
    icon: Radio,
    description: 'Map layers and network traffic paths shown on Overview.',
  },
  {
    value: 'aircraft',
    label: 'Aircraft Traffic',
    icon: Plane,
    description: 'Browse worldwide aircraft and manage the Overview selection.',
  },
  {
    value: 'display',
    label: 'Displays',
    icon: Monitor,
    description: 'Discover Overview displays and recenter a connected view.',
  },
  {
    value: 'terminal',
    label: 'Terminal Controls',
    icon: Satellite,
    description: 'Physical terminal controls and GPS receiver status.',
  },
  {
    value: 'diagnostics',
    label: 'Diagnostics',
    icon: Activity,
    description: 'Health and source status for Overview traffic and map data.',
  },
];

export function ConfigurationPage() {
  const { data, isLoading, isError } = useOverviewClockSettings();
  const {
    mutate,
    isError: isSaveError,
    isPending,
  } = useUpdateOverviewClockSettings();
  const [section, setSection] = useState('overview');
  const active = sections.find((item) => item.value === section)!;
  // Keep editors and display discovery mounted while switching tabs. Unsaved
  // drafts and explicitly selected remote displays must survive navigation.
  const panelClass = 'mt-0 space-y-5 data-[state=inactive]:hidden';
  return (
    <div className="dark min-h-[calc(100dvh-4rem)] bg-background text-foreground">
      <div className="mx-auto w-full max-w-6xl p-4 sm:p-6">
        <header className="mb-5">
          <h1 className="text-3xl font-semibold tracking-tight">
            Configuration
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Manage Overview, traffic, connected displays and terminal controls.
          </p>
        </header>
        <Tabs value={section} onValueChange={setSection}>
          <div className="overflow-x-auto pb-1">
            <TabsList
              aria-label="Configuration sections"
              className="w-max justify-start gap-1"
            >
              {sections.map(({ value, label, icon: Icon }) => (
                <TabsTrigger key={value} value={value} className="gap-2 px-4">
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          <p className="my-4 text-sm text-muted-foreground">
            {active.description}
          </p>
          <TabsContent
            value="overview"
            forceMount
            hidden={section !== 'overview'}
            className={panelClass}
          >
            <ConfigurationSection
              title="Overview behavior"
              description="Set the history window and camera follow preference."
            >
              <div className="divide-y">
                <OverviewHistorySettingsCard embedded />
                <OverviewCameraSettingsCard embedded />
              </div>
            </ConfigurationSection>
            <OverviewWeatherSettingsCard />
            {isLoading ? (
              <ConfigurationSection title="Operational clocks">
                <p role="status">Loading operational clocks...</p>
              </ConfigurationSection>
            ) : isError || !data ? (
              <ConfigurationSection title="Operational clocks">
                <p role="alert">Operational clocks unavailable</p>
              </ConfigurationSection>
            ) : (
              <OperationalClockSettingsForm
                clocks={data.clocks}
                isSaving={isPending}
                error={
                  isSaveError
                    ? 'Unable to save operational clocks. Please try again.'
                    : undefined
                }
                onSave={(settings) => mutate(settings)}
              />
            )}
          </TabsContent>
          <TabsContent
            value="traffic"
            forceMount
            hidden={section !== 'traffic'}
            className={panelClass}
          >
            <OverviewLinkSettingsCard />
            <ManualXBandSelectionCard />
          </TabsContent>
          <TabsContent
            value="aircraft"
            forceMount
            hidden={section !== 'aircraft'}
            className={panelClass}
          >
            <OverviewAdsbSettingsCard active={section === 'aircraft'} />
          </TabsContent>
          <TabsContent
            value="display"
            forceMount
            hidden={section !== 'display'}
            className={panelClass}
          >
            <OverviewDisplaySettingsCard />
          </TabsContent>
          <TabsContent
            value="terminal"
            forceMount
            hidden={section !== 'terminal'}
            className={panelClass}
          >
            <GPSControlCard />
          </TabsContent>
          <TabsContent
            value="diagnostics"
            forceMount
            hidden={section !== 'diagnostics'}
            className={panelClass}
          >
            <div className="grid items-start gap-5 lg:grid-cols-2">
              <OverviewMapDiagnostics />
              <OrbitalTrafficDiagnostics />
            </div>
            <OverviewAdsbSourceStatus />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
