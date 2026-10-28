import {
  createContext,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { RootState } from '@react-three/fiber';
import { TuningPanel } from '../experiments/bloom/TuningPanel';
import type { BloomMode, BloomSettings } from '../experiments/bloom/contracts';
import {
  OverviewBloomComposer,
  type FrameEvidence,
} from '../experiments/bloom/OverviewBloomComposer';
import { describeFrame } from '../experiments/bloom/metrics';
import {
  DEFAULT_OVERVIEW_AMBIENT_INTENSITY,
  OverviewAmbientIntensity,
  OverviewAtmosphereIntensity,
  useOverviewAmbientIntensity,
  OverviewBloomEmission,
  OverviewBloomMode,
} from './overview-bloom-mode';

import {
  OVERVIEW_BLOOM_SETTINGS,
  OVERVIEW_BLOOM_AMBIENT_INTENSITY,
  OVERVIEW_BLOOM_ATMOSPHERE_INTENSITY,
  OVERVIEW_BLOOM_EMISSIONS,
} from './overview-bloom-tuning';

type RenderedFrame = { state: RootState; dimensions: FrameEvidence };
const BloomScene = createContext<{
  mode: BloomMode;
  settings: BloomSettings;
  onFrame: (state: RootState, dimensions: FrameEvidence) => void;
} | null>(null);

// The provider stays in place while tuning, keeping the real Canvas and all its
// live data, camera controls and animation pools mounted. Bloom is the default;
// the query flag controls only whether the temporary tuning panel is shown.
export function OverviewBloom({
  debug = false,
  children,
}: {
  debug?: boolean;
  children: ReactNode;
}) {
  const [mode, setMode] = useState<BloomMode>('bloom');
  const [settings, setSettings] = useState(OVERVIEW_BLOOM_SETTINGS);
  const [emissions, setEmissions] = useState(OVERVIEW_BLOOM_EMISSIONS);
  const [ambientIntensity, setAmbientIntensity] = useState(
    OVERVIEW_BLOOM_AMBIENT_INTENSITY
  );
  const [atmosphereIntensity, setAtmosphereIntensity] = useState(
    OVERVIEW_BLOOM_ATMOSPHERE_INTENSITY
  );
  const frame = useRef<RenderedFrame | null>(null);
  const active = mode === 'bloom';
  const getReport = () => {
    const last = frame.current;
    return {
      schema: 'overview-bloom-tuning/v1',
      scene: 'overview',
      capturedAt: new Date().toISOString(),
      mode,
      settings,
      emissions,
      lighting: { ambientIntensity, atmosphereIntensity },
      lightingOverridesActive: active,
      emissionOverridesActive: active,
      frame: last
        ? {
            ...describeFrame(last.state, last.dimensions),
            camera: {
              position: last.state.camera.position.toArray(),
              quaternion: last.state.camera.quaternion.toArray(),
              zoom: last.state.camera.zoom,
            },
          }
        : null,
    };
  };
  return (
    <BloomScene.Provider
      value={{
        mode,
        settings,
        onFrame: (state, dimensions) => {
          if (debug) frame.current = { state, dimensions };
        },
      }}
    >
      <OverviewAmbientIntensity.Provider
        value={active ? ambientIntensity : DEFAULT_OVERVIEW_AMBIENT_INTENSITY}
      >
        <OverviewAtmosphereIntensity.Provider
          value={active ? atmosphereIntensity : 1}
        >
          <OverviewBloomMode.Provider value={active}>
            <OverviewBloomEmission.Provider value={emissions}>
              {children}
              {debug && (
                <TuningPanel
                  active={active}
                  busy={false}
                  ambientIntensity={ambientIntensity}
                  onAmbientIntensity={setAmbientIntensity}
                  atmosphereIntensity={atmosphereIntensity}
                  onAtmosphereIntensity={setAtmosphereIntensity}
                  mode={mode}
                  onMode={setMode}
                  settings={settings}
                  emissions={emissions}
                  isolateCities={false}
                  allowIsolation={false}
                  onIsolate={() => {}}
                  onSettings={setSettings}
                  onEmissions={setEmissions}
                  onCityPreset={() => {
                    setMode('bloom');
                    setSettings({
                      ...OVERVIEW_BLOOM_SETTINGS,
                      strength: 1,
                      threshold: 0.4,
                      radius: 0.3,
                      maxDimension: 1920,
                    });
                    setEmissions({ ...OVERVIEW_BLOOM_EMISSIONS, cities: 30 });
                  }}
                  onReset={() => {
                    setSettings(OVERVIEW_BLOOM_SETTINGS);
                    setEmissions(OVERVIEW_BLOOM_EMISSIONS);
                    setAmbientIntensity(OVERVIEW_BLOOM_AMBIENT_INTENSITY);
                    setAtmosphereIntensity(OVERVIEW_BLOOM_ATMOSPHERE_INTENSITY);
                  }}
                  getReport={getReport}
                />
              )}
            </OverviewBloomEmission.Provider>
          </OverviewBloomMode.Provider>
        </OverviewAtmosphereIntensity.Provider>
      </OverviewAmbientIntensity.Provider>
    </BloomScene.Provider>
  );
}

export function OverviewBloomScene() {
  const debug = useContext(BloomScene);
  return debug ? <OverviewBloomComposer {...debug} /> : null;
}

export function OverviewAmbientLight() {
  const intensity = useOverviewAmbientIntensity();
  return <ambientLight intensity={intensity} />;
}
