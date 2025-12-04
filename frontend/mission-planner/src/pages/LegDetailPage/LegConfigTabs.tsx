import { Link } from 'react-router-dom';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../components/ui/tabs';
import { XBandConfig } from '../../components/satellites/XBandConfig';
import { KaOutageConfig } from '../../components/satellites/KaOutageConfig';
import { KuOutageConfig } from '../../components/satellites/KuOutageConfig';
import { AARSegmentEditor } from '../../components/aar/AARSegmentEditor';
import type { SatelliteConfig } from '../../types/satellite';
import type { AARConfig } from '../../types/aar';

interface LegConfigTabsProps {
  satelliteConfig: SatelliteConfig;
  aarConfig: AARConfig;
  availableSatellites: string[];
  waypointNames: string[];
  onSatelliteConfigChange: (updates: Partial<SatelliteConfig>) => void;
  onAARConfigChange: (config: AARConfig) => void;
}

/**
 * Tabs component containing all configuration sections for a leg
 */
export function LegConfigTabs({
  satelliteConfig,
  aarConfig,
  availableSatellites,
  waypointNames,
  onSatelliteConfigChange,
  onAARConfigChange,
}: LegConfigTabsProps) {
  return (
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
            <h2 className="text-xl font-semibold">X-Band Configuration</h2>
            <Link
              to="/satellites"
              className="text-sm text-blue-600 hover:underline"
            >
              Manage Satellites →
            </Link>
          </div>
          <XBandConfig
            startingSatellite={satelliteConfig.xband_starting_satellite}
            transitions={satelliteConfig.xband_transitions}
            onStartingSatelliteChange={(satellite) =>
              onSatelliteConfigChange({
                xband_starting_satellite: satellite,
              })
            }
            onTransitionsChange={(transitions) =>
              onSatelliteConfigChange({
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
              onSatelliteConfigChange({ ka_outages: outages })
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
              onSatelliteConfigChange({ ku_outages: outages })
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
              onAARConfigChange({ ...aarConfig, segments })
            }
            availableWaypoints={waypointNames}
          />
        </div>
      </TabsContent>
    </Tabs>
  );
}
