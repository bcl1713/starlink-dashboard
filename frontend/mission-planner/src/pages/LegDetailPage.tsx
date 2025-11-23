import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { XBandConfig } from '../components/satellites/XBandConfig';
import { KaOutageConfig } from '../components/satellites/KaOutageConfig';
import { KuOutageConfig } from '../components/satellites/KuOutageConfig';
import { AARSegmentEditor } from '../components/aar/AARSegmentEditor';
import { RouteMap } from '../components/common/RouteMap';
import type { SatelliteConfig } from '../types/satellite';
import type { AARConfig } from '../types/aar';

export function LegDetailPage() {
  const { missionId, legId } = useParams<{ missionId: string; legId: string }>();

  // TODO: Replace with actual API calls to fetch leg data
  const [satelliteConfig, setSatelliteConfig] = useState<SatelliteConfig>({
    xband_starting_satellite: undefined,
    xband_transitions: [],
    ka_outages: [],
    ku_outages: [],
  });

  const [aarConfig, setAARConfig] = useState<AARConfig>({
    segments: [],
  });

  // Example available satellites (TODO: fetch from backend)
  const availableSatellites = [
    'X-Band-1',
    'X-Band-2',
    'X-Band-3',
    'X-Band-4',
    'X-Band-5',
  ];

  // Example available waypoints (TODO: fetch from route)
  const availableWaypoints = [
    'WP001',
    'WP002',
    'WP003',
    'WP004',
    'WP005',
  ];

  // TODO: Fetch actual route coordinates from backend
  // Placeholder route coordinates (example: Denver to DC)
  const routeCoordinates: [number, number][] = [
    [39.7392, -104.9903], // Denver
    [39.8, -104.5],
    [40.0, -103.0],
    [40.5, -101.0],
    [41.0, -99.0],
    [41.8, -96.0],
    [42.0, -93.0],
    [41.5, -90.0],
    [41.0, -87.0],
    [40.5, -84.0],
    [40.0, -81.0],
    [39.5, -78.0],
    [39.0, -77.0],
    [38.9072, -77.0369], // Washington DC
  ];

  // Generate map coordinates: route + transition markers
  const mapCoordinates = [...routeCoordinates];

  // Add X-Band transition points to the map
  satelliteConfig.xband_transitions.forEach((transition) => {
    mapCoordinates.push([transition.latitude, transition.longitude]);
  });

  const handleSatelliteConfigChange = (
    updates: Partial<SatelliteConfig>
  ) => {
    setSatelliteConfig({ ...satelliteConfig, ...updates });
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
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
                <h2 className="text-xl font-semibold mb-4">
                  X-Band Configuration
                </h2>
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
                  onSegmentsChange={(segments) =>
                    setAARConfig({ ...aarConfig, segments })
                  }
                  availableWaypoints={availableWaypoints}
                />
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end space-x-4 mt-6">
            <button className="px-4 py-2 border rounded-md hover:bg-gray-100">
              Cancel
            </button>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              Save Changes
            </button>
          </div>
        </div>

        {/* Right Column: Map Visualization */}
        <div className="sticky top-6 h-fit">
          <h2 className="text-xl font-semibold mb-4">Route Visualization</h2>
          <RouteMap coordinates={mapCoordinates} height="600px" />
          <div className="mt-4 text-sm text-gray-600 space-y-1">
            <p>• Blue line: Flight route</p>
            <p>• Markers: X-Band transition points</p>
            <p className="text-gray-400">AAR segments visualization coming soon</p>
          </div>
        </div>
      </div>
    </div>
  );
}
