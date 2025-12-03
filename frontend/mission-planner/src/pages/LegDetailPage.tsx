import { useParams, useNavigate } from 'react-router-dom';
import { useMission, useUpdateLeg } from '../hooks/api/useMissions';
import { useLegData } from './LegDetailPage/useLegData';
import { LegHeader } from './LegDetailPage/LegHeader';
import { LegConfigTabs } from './LegDetailPage/LegConfigTabs';
import { LegMapVisualization } from './LegDetailPage/LegMapVisualization';
import type { SatelliteConfig } from '../types/satellite';
import type { AARConfig } from '../types/aar';

export function LegDetailPage() {
  const { missionId, legId } = useParams<{
    missionId: string;
    legId: string;
  }>();
  const navigate = useNavigate();
  const { data: mission, isLoading: isMissionLoading } = useMission(
    missionId || ''
  );
  const updateLegMutation = useUpdateLeg(missionId || '', legId || '');

  // Find the current leg
  const leg = mission?.legs.find((l) => l.id === legId);

  // Use custom hook for data management
  const {
    satelliteConfig,
    setSatelliteConfig,
    aarConfig,
    setAARConfig,
    routeCoordinates,
    availableWaypoints,
    waypointNames,
    availableSatellites,
    kaTransitions,
    hasUnsavedChanges,
    setHasUnsavedChanges,
  } = useLegData({
    routeId: leg?.route_id,
    missionId: missionId,
    legTransports: leg?.transports,
  });

  const handleSatelliteConfigChange = (updates: Partial<SatelliteConfig>) => {
    const updatedConfig = { ...satelliteConfig, ...updates };
    setSatelliteConfig(updatedConfig);
    setHasUnsavedChanges(true);
  };

  const handleAARConfigChange = (config: AARConfig) => {
    setAARConfig(config);
    setHasUnsavedChanges(true);
  };

  const handleBackClick = () => {
    if (hasUnsavedChanges) {
      if (
        window.confirm(
          'You have unsaved changes. Are you sure you want to leave?'
        )
      ) {
        navigate(`/missions/${missionId}`);
      }
    } else {
      navigate(`/missions/${missionId}`);
    }
  };

  const handleSave = async () => {
    if (!leg) return;

    try {
      await updateLegMutation.mutateAsync({
        ...leg,
        transports: {
          initial_x_satellite_id:
            satelliteConfig.xband_starting_satellite || 'X-1',
          initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
          x_transitions: satelliteConfig.xband_transitions,
          ka_outages: satelliteConfig.ka_outages,
          aar_windows: aarConfig.segments,
          ku_overrides: satelliteConfig.ku_outages,
        },
      });
      alert('Changes saved successfully!');
      setHasUnsavedChanges(false);
    } catch (error) {
      console.error('Failed to save:', error);
      alert('Failed to save changes');
    }
  };

  // Loading state
  if (isMissionLoading) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-muted-foreground">Loading leg configuration...</p>
      </div>
    );
  }

  // Leg not found state
  if (!leg) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Leg not found</p>
        <button
          className="mt-4 px-4 py-2 border rounded-md hover:bg-gray-100"
          onClick={() => navigate(`/missions/${missionId}`)}
        >
          Back to Mission
        </button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <LegHeader
        missionId={missionId || ''}
        legId={legId || ''}
        onBackClick={handleBackClick}
      />

      <div className="grid grid-cols-2 gap-6">
        {/* Left Column: Configuration Tabs */}
        <div>
          <LegConfigTabs
            satelliteConfig={satelliteConfig}
            aarConfig={aarConfig}
            availableSatellites={availableSatellites}
            waypointNames={waypointNames}
            onSatelliteConfigChange={handleSatelliteConfigChange}
            onAARConfigChange={handleAARConfigChange}
          />

          <div className="flex justify-end space-x-4 mt-6">
            <button
              className="px-4 py-2 border rounded-md hover:bg-gray-100"
              onClick={() => navigate(`/missions/${missionId}`)}
            >
              Cancel
            </button>
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              onClick={handleSave}
              disabled={updateLegMutation.isPending}
            >
              {updateLegMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>

        {/* Right Column: Map Visualization */}
        <LegMapVisualization
          routeCoordinates={routeCoordinates}
          satelliteConfig={satelliteConfig}
          aarConfig={aarConfig}
          kaTransitions={kaTransitions}
          waypointNames={waypointNames}
          availableWaypoints={availableWaypoints}
        />
      </div>
    </div>
  );
}
