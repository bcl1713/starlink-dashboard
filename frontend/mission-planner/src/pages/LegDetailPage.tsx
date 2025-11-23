import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { XBandConfig } from '../components/satellites/XBandConfig';
import { KaOutageConfig } from '../components/satellites/KaOutageConfig';
import { KuOutageConfig } from '../components/satellites/KuOutageConfig';
import { AARSegmentEditor } from '../components/aar/AARSegmentEditor';
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
                handleSatelliteConfigChange({ xband_transitions: transitions })
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
            />
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex justify-end space-x-4">
        <button className="px-4 py-2 border rounded-md hover:bg-gray-100">
          Cancel
        </button>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          Save Changes
        </button>
      </div>
    </div>
  );
}
