import { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMission, useUpdateLeg } from '../hooks/api/useMissions';
import { useTimeline } from '../hooks/api/useTimeline';
import { useTimelinePreview } from '../hooks/api/useTimelinePreview';
import { useLegData } from './LegDetailPage/useLegData';
import { LegHeader } from './LegDetailPage/LegHeader';
import { LegConfigTabs } from './LegDetailPage/LegConfigTabs';
import { LegMapVisualization } from './LegDetailPage/LegMapVisualization';
import { TimingSection } from './LegDetailPage/TimingSection';
import { TimelinePreviewSection } from '../components/timeline/TimelinePreviewSection';
import type { SatelliteConfig } from '../types/satellite';
import type { AARConfig } from '../types/aar';
import type { TimelinePreviewRequest } from '../services/timeline';

export function LegDetailPage() {
  const { missionId, legId } = useParams<{
    missionId: string;
    legId: string;
  }>();
  const navigate = useNavigate();
  const { data: mission, isLoading: isMissionLoading } = useMission(
    missionId || ''
  );
  const { data: timeline } = useTimeline(missionId || '', legId || '');
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

  // Build preview request from current config (memoized to prevent constant re-triggering)
  const previewRequest: TimelinePreviewRequest | null = useMemo(() => {
    if (!leg) return null;

    return {
      transports: {
        initial_x_satellite_id:
          satelliteConfig.xband_starting_satellite || 'X-1',
        initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
        x_transitions: satelliteConfig.xband_transitions.map((t) => ({
          latitude: t.latitude,
          longitude: t.longitude,
          to_satellite: t.target_satellite_id,
        })),
        ka_outages: satelliteConfig.ka_outages,
        aar_windows: aarConfig.segments.map((s) => ({
          id: s.id,
          start_waypoint_name: s.start_waypoint_name,
          end_waypoint_name: s.end_waypoint_name,
        })),
        ku_overrides: satelliteConfig.ku_outages.map((k) => ({
          id: k.id,
          start_time: k.start_time,
          duration_seconds: k.duration_seconds,
          reason: k.reason,
        })),
      },
      adjusted_departure_time: leg.adjusted_departure_time || undefined,
    };
  }, [
    leg,
    satelliteConfig.xband_starting_satellite,
    satelliteConfig.xband_transitions,
    satelliteConfig.ka_outages,
    satelliteConfig.ku_outages,
    aarConfig.segments,
  ]);

  // Memoize preview options to prevent unnecessary hook re-runs
  const previewOptions = useMemo(
    () => ({
      debounceMs: 500,
      enabled: !!leg?.route_id,
    }),
    [leg?.route_id]
  );

  // Get timeline preview (debounced)
  const { preview, isCalculating, error } = useTimelinePreview(
    missionId || '',
    legId || '',
    previewRequest,
    previewOptions
  );

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
      const result = await updateLegMutation.mutateAsync({
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

      if (result.warnings && result.warnings.length > 0) {
        alert(
          `Changes saved successfully!\n\nWarnings:\n${result.warnings.join('\n')}`
        );
      } else {
        alert('Changes saved successfully!');
      }
      setHasUnsavedChanges(false);
    } catch (error) {
      console.error('Failed to save:', error);
      alert('Failed to save changes');
    }
  };

  const handleTimingUpdate = async (
    adjustedDepartureTime: string | null,
    warnings?: string[]
  ) => {
    if (!leg) return;

    try {
      const result = await updateLegMutation.mutateAsync({
        ...leg,
        adjusted_departure_time: adjustedDepartureTime,
      });

      if (warnings && warnings.length > 0) {
        alert(
          `Timing updated successfully!\n\nWarnings:\n${warnings.join('\n')}`
        );
      } else if (adjustedDepartureTime === null) {
        alert('Timing reset to original departure time.');
      } else {
        alert('Timing updated successfully!');
      }

      if (result.warnings && result.warnings.length > 0) {
        const warningMessage = result.warnings.join('\n\n');
        alert(`⚠️  Server warnings:\n\n${warningMessage}`);
      }
    } catch (error) {
      console.error('Failed to update timing:', error);
      alert('Failed to update timing. Please try again.');
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
        routeId={leg?.route_id}
        onBackClick={handleBackClick}
      />

      <div className="grid grid-cols-2 gap-6">
        {/* Left Column: Configuration Tabs */}
        <div className="space-y-6">
          <TimingSection
            leg={leg}
            timeline={timeline || null}
            onTimingUpdate={handleTimingUpdate}
            isUpdating={updateLegMutation.isPending}
          />

          <LegConfigTabs
            satelliteConfig={satelliteConfig}
            aarConfig={aarConfig}
            availableSatellites={availableSatellites}
            waypointNames={waypointNames}
            onSatelliteConfigChange={handleSatelliteConfigChange}
            onAARConfigChange={handleAARConfigChange}
          />

          <TimelinePreviewSection
            timeline={preview}
            isCalculating={isCalculating}
            isUnsaved={hasUnsavedChanges}
            error={error}
          />

          <div className="flex justify-end space-x-4">
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
          timelinePreview={preview}
        />
      </div>
    </div>
  );
}
