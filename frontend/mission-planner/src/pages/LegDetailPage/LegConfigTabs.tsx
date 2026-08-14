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
import { ManualAARTrackEditor } from '../../components/aar/ManualAARTrackEditor';
import type { SatelliteConfig } from '../../types/satellite';
import type { AARConfig, ManualAARTrack } from '../../types/aar';

interface LegConfigTabsProps {
  satelliteConfig: SatelliteConfig;
  aarConfig: AARConfig;
  availableSatellites: string[];
  waypointNames: string[];
  onSatelliteConfigChange: (updates: Partial<SatelliteConfig>) => void;
  onAARConfigChange: (config: AARConfig) => void;
  onManualTrackSave: (track: ManualAARTrack) => Promise<void>;
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
  onManualTrackSave,
}: LegConfigTabsProps) {
  return (
    <Tabs defaultValue="xband" className="w-full">
      <TabsList className="h-auto w-full flex-wrap justify-start gap-1">
        <TabsTrigger value="xband">X-Band</TabsTrigger>
        <TabsTrigger value="ka">Ka Outages</TabsTrigger>
        <TabsTrigger value="ku">Ku/Starlink Outages</TabsTrigger>
        <TabsTrigger value="aar">AAR Segments</TabsTrigger>
        <TabsTrigger value="manual-ar">Manual AR Tracks</TabsTrigger>
      </TabsList>

      <TabsContent value="xband" className="space-y-4">
        <div className="rounded-lg border p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
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
        <div className="rounded-lg border p-4 sm:p-6">
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
        <div className="rounded-lg border p-4 sm:p-6">
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
        <div className="rounded-lg border p-4 sm:p-6">
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

      <TabsContent value="manual-ar" className="space-y-4">
        <div className="rounded-lg border p-4 sm:p-6">
          <h2 className="text-xl font-semibold mb-4">Manual AR Track</h2>
          <ManualAARTrackEditor
            tracks={aarConfig.manualTracks}
            onSaveTrack={onManualTrackSave}
            onRemoveTrack={(trackId) =>
              onAARConfigChange({
                ...aarConfig,
                manualTracks: aarConfig.manualTracks.filter(
                  (track) => track.id !== trackId
                ),
              })
            }
          />
        </div>
      </TabsContent>
    </Tabs>
  );
}
