import { OverviewCameraSettingsCard } from './OverviewCameraSettingsCard';
import { OverviewDisplaySettingsCard } from './OverviewDisplaySettingsCard';
import { OverviewHistorySettingsCard } from './OverviewHistorySettingsCard';
import { OverviewMapDiagnostics } from './OverviewMapDiagnostics';
import { OverviewAdsbSettingsCard } from './adsb/OverviewAdsbSettingsCard';
import { OverviewLinkSettingsCard } from './OverviewLinkSettingsCard';
import { OrbitalTrafficDiagnostics } from './OrbitalTrafficDiagnostics';
import { useOverviewClockSettings } from '@/hooks/api/useOverviewClockSettings';
import { GPSControlCard } from '../components/gps/GPSControlCard';
import { useUpdateOverviewClockSettings } from '@/hooks/api/useUpdateOverviewClockSettings';
import { OperationalClockSettingsForm } from './OperationalClockSettingsForm';

export function ConfigurationPage() {
  const { data, isLoading, isError } = useOverviewClockSettings();

  const {
    mutate,
    isError: isSaveError,
    isPending,
  } = useUpdateOverviewClockSettings();
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Configuration</h1>
      </div>

      <div className="max-w-xl">
        <GPSControlCard />
        <OverviewHistorySettingsCard />
        <OverviewLinkSettingsCard />
        <OverviewAdsbSettingsCard />
        <OrbitalTrafficDiagnostics />
        <OverviewCameraSettingsCard />
        <OverviewDisplaySettingsCard />
        <OverviewMapDiagnostics />
        {isLoading ? (
          <p role="status">Loading operational clocks...</p>
        ) : isError || !data ? (
          <p role="alert">Operational clocks unavailable</p>
        ) : (
          <>
            {isSaveError && (
              <p role="alert">
                Unable to save operational clocks. Please try again.
              </p>
            )}
            <OperationalClockSettingsForm
              clocks={data.clocks}
              isSaving={isPending}
              onSave={(settings) => mutate(settings)}
            />
          </>
        )}
      </div>
    </div>
  );
}
