import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { XBandConfig } from '../components/satellites/XBandConfig';
import { KaOutageConfig } from '../components/satellites/KaOutageConfig';
import { KuOutageConfig } from '../components/satellites/KuOutageConfig';
import { AARSegmentEditor } from '../components/aar/AARSegmentEditor';
import { RouteMap } from '../components/common/RouteMap';
import type { SatelliteConfig } from '../types/satellite';
import type { AARConfig } from '../types/aar';
import { useMission, useUpdateLeg } from '../hooks/api/useMissions';
import { routesApi } from '../services/routes';
import { satelliteService, type SatelliteResponse } from '../services/satellites';

export function LegDetailPage() {
  const { missionId, legId } = useParams<{ missionId: string; legId: string }>();
  const navigate = useNavigate();
  const { data: mission, isLoading: isMissionLoading } = useMission(
    missionId || ''
  );
  const updateLegMutation = useUpdateLeg(missionId || '', legId || '');

  // Find the current leg
  const leg = mission?.legs.find((l) => l.id === legId);

  // State for configurations
  const [satelliteConfig, setSatelliteConfig] = useState<SatelliteConfig>({
    xband_starting_satellite: undefined,
    xband_transitions: [],
    ka_outages: [],
    ku_outages: [],
  });

  const [aarConfig, setAARConfig] = useState<AARConfig>({
    segments: [],
  });

  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([]);
  const [availableWaypoints, setAvailableWaypoints] = useState<string[]>([]);
  const [availableSatellites, setAvailableSatellites] = useState<string[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Load satellites on component mount
  useEffect(() => {
    satelliteService
      .getAll()
      .then((satellites: SatelliteResponse[]) =>
        setAvailableSatellites(satellites.map((s: SatelliteResponse) => s.satellite_id))
      )
      .catch((err: Error) => console.error('Failed to load satellites:', err));
  }, []);

  // Load route coordinates and waypoints when leg changes
  useEffect(() => {
    if (leg?.route_id) {
      routesApi
        .getCoordinates(leg.route_id)
        .then((coords) => setRouteCoordinates(coords))
        .catch((err) => console.error('Failed to load route coordinates:', err));

      routesApi
        .getWaypoints(leg.route_id)
        .then((waypoints) => setAvailableWaypoints(waypoints))
        .catch((err) => console.error('Failed to load route waypoints:', err));
    } else {
      setAvailableWaypoints([]);
    }
  }, [leg?.route_id]);

  // Initialize state from leg data
  useEffect(() => {
    if (leg?.transports) {
      setSatelliteConfig({
        xband_starting_satellite: leg.transports.initial_x_satellite_id,
        xband_transitions: (leg.transports.x_transitions as any[]) || [],
        ka_outages: (leg.transports.ka_outages as any[]) || [],
        ku_outages: (leg.transports.ku_overrides as any[]) || [],
      });
      setAARConfig({
        segments: (leg.transports.aar_windows as any[]) || [],
      });
    }
  }, [leg?.transports]);


  // Generate map coordinates: route only (transitions handled separately as markers)
  const mapCoordinates = [...routeCoordinates];

  const handleSatelliteConfigChange = (
    updates: Partial<SatelliteConfig>
  ) => {
    setSatelliteConfig({ ...satelliteConfig, ...updates });
    setHasUnsavedChanges(true);
  };

  const handleBackClick = () => {
    if (hasUnsavedChanges) {
      if (window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
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
      <div>
        <Button
          variant="ghost"
          onClick={handleBackClick}
          className="mb-4"
        >
          ← Back to Mission
        </Button>
        <h1 className="text-3xl font-bold">Leg Configuration</h1>
        <p className="text-muted-foreground">
          Mission: {missionId} | Leg: {legId}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left Column: Configuration Tabs */}
        <div>
          <Tabs defaultValue="xband" className="w-full">
            <TabsList>
              <TabsTrigger value="xband">X-Band</TabsTrigger>
              <TabsTrigger value="ka">Ka Outages</TabsTrigger>
              <TabsTrigger value="ku">Ku/Starlink Outages</TabsTrigger>
              <TabsTrigger value="aar">AAR Segments</TabsTrigger>
            </TabsList>

            <TabsContent value="xband" className="space-y-4">
              <div className="rounded-lg border p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-semibold">
                    X-Band Configuration
                  </h2>
                  <Link to="/satellites" className="text-sm text-blue-600 hover:underline">
                    Manage Satellites →
                  </Link>
                </div>
                <XBandConfig
                  startingSatellite={satelliteConfig.xband_starting_satellite}
                  transitions={satelliteConfig.xband_transitions}
                  onStartingSatelliteChange={(satellite) =>
                    handleSatelliteConfigChange({
                      xband_starting_satellite: satellite,
                    })
                  }
                  onTransitionsChange={(transitions) =>
                    handleSatelliteConfigChange({
                      xband_transitions: transitions,
                    })
                  }
                  availableSatellites={availableSatellites}
                />
              </div>
            </TabsContent>

            <TabsContent value="ka" className="space-y-4">
              <div className="rounded-lg border p-6">
                <h2 className="text-xl font-semibold mb-4">
                  Ka Outage Configuration
                </h2>
                <KaOutageConfig
                  outages={satelliteConfig.ka_outages}
                  onOutagesChange={(outages) =>
                    handleSatelliteConfigChange({ ka_outages: outages })
                  }
                />
              </div>
            </TabsContent>

            <TabsContent value="ku" className="space-y-4">
              <div className="rounded-lg border p-6">
                <h2 className="text-xl font-semibold mb-4">
                  Ku/Starlink Outage Configuration
                </h2>
                <KuOutageConfig
                  outages={satelliteConfig.ku_outages}
                  onOutagesChange={(outages) =>
                    handleSatelliteConfigChange({ ku_outages: outages })
                  }
                />
              </div>
            </TabsContent>

            <TabsContent value="aar" className="space-y-4">
              <div className="rounded-lg border p-6">
                <h2 className="text-xl font-semibold mb-4">
                  AAR Segment Configuration
                </h2>
                <AARSegmentEditor
                  segments={aarConfig.segments}
                  onSegmentsChange={(segments) => {
                    setAARConfig({ ...aarConfig, segments });
                    setHasUnsavedChanges(true);
                  }}
                  availableWaypoints={availableWaypoints}
                />
              </div>
            </TabsContent>
          </Tabs>

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
        <div className="sticky top-6 h-fit">
          <h2 className="text-xl font-semibold mb-4">Route Visualization</h2>
          <RouteMap
            coordinates={mapCoordinates}
            xbandTransitions={satelliteConfig.xband_transitions}
            aarSegments={aarConfig.segments}
            kaOutages={satelliteConfig.ka_outages || []}
            kuOutages={satelliteConfig.ku_outages || []}
            height="600px"
          />
          <div className="mt-4 text-sm text-gray-600 space-y-1">
            <p>• Blue line: Flight route</p>
            <p>• Blue circles: X-Band transition points</p>
            <p>• Green dashed line: AAR segments</p>
            <p>• See below map for Ka/Ku outage timeline</p>
          </div>
        </div>
      </div>
    </div>
  );
}
