import { useRef, useState } from 'react';
import type { BloomEmission } from '../../pages/overview-bloom-mode';
import { resolveCityEmission } from '../../pages/overview-bloom-mode';
import type { BloomSettings, BloomView } from './contracts';
import { download } from './metrics';

export function TuningPanel({
  active,
  busy,
  settings,
  emissions,
  isolateCities,
  onSettings,
  onEmissions,
  onIsolate,
  onCityPreset,
  onReset,
  getReport,
}: {
  active: boolean;
  busy: boolean;
  settings: BloomSettings;
  emissions: BloomEmission;
  isolateCities: boolean;
  onSettings: (settings: BloomSettings) => void;
  onEmissions: (emissions: BloomEmission) => void;
  onIsolate: (value: boolean) => void;
  onCityPreset: () => void;
  onReset: () => void;
  getReport: () => object;
}) {
  const [text, setText] = useState(''),
    [message, setMessage] = useState('');
  const area = useRef<HTMLTextAreaElement>(null);
  const city = resolveCityEmission(true, emissions);
  const luminance =
    city.intensity *
    (city.color.r * 0.299 + city.color.g * 0.587 + city.color.b * 0.114);
  const capture = () => {
    const value = JSON.stringify(getReport(), null, 2);
    setText(value);
    return value;
  };
  const copy = async () => {
    const value = capture();
    try {
      await navigator.clipboard.writeText(value);
      setMessage('Settings copied — paste them into our chat.');
    } catch {
      setMessage('Select the JSON below and copy it into our chat.');
      requestAnimationFrame(() => {
        area.current?.focus();
        area.current?.select();
      });
    }
  };
  return (
    <aside
      className="bloom-tuning overview-marker-debug"
      aria-label="Temporary bloom tuning"
    >
      <strong>Temporary bloom tuning</strong>
      <p>
        {active
          ? 'Live in B · changes keep camera and particles.'
          : 'Select B to apply emission and debug controls.'}
      </p>
      <div className="tuning-actions">
        <button disabled={busy} onClick={onCityPreset}>
          Find city glow
        </button>
        <button disabled={busy} onClick={onReset}>
          Reset tuning
        </button>
      </div>
      <div className="tuning-actions">
        <button disabled={busy} onClick={() => void copy()}>
          Copy settings
        </button>
        <button
          disabled={busy}
          onClick={() =>
            download(
              'overview-bloom-settings.json',
              capture(),
              'application/json'
            )
          }
        >
          Download settings.json
        </button>
      </div>
      <p aria-live="polite">{message}</p>
      {text && (
        <label>
          Feedback JSON{' '}
          <textarea
            ref={area}
            aria-label="Feedback JSON"
            value={text}
            readOnly
            onFocus={(e) => e.currentTarget.select()}
          />
        </label>
      )}
      <fieldset disabled={busy || !active}>
        <label>
          View{' '}
          <select
            aria-label="Bloom debug view"
            value={settings.view}
            onChange={(e) =>
              onSettings({ ...settings, view: e.target.value as BloomView })
            }
          >
            <option value="final">Final scene</option>
            <option value="bright">Bright pass · before blur</option>
            <option value="bloom">Bloom only · light spill</option>
          </select>
        </label>
        <label>
          <input
            aria-label="Cities only"
            type="checkbox"
            checked={isolateCities}
            onChange={(e) => onIsolate(e.target.checked)}
          />
          Isolate cities · mute terrain
        </label>
        <label>
          Exposure{' '}
          <input
            aria-label="Exposure"
            type="number"
            min="0.1"
            max="5"
            step="0.1"
            value={settings.exposure}
            onChange={(e) =>
              onSettings({
                ...settings,
                exposure: Math.min(
                  5,
                  Math.max(0.1, Number(e.target.value) || 0.1)
                ),
              })
            }
          />
        </label>
        <label>
          Warm city color{' '}
          <input
            aria-label="City light color"
            type="color"
            value={emissions.cityColor}
            onChange={(e) =>
              onEmissions({ ...emissions, cityColor: e.target.value })
            }
          />
          <code>{emissions.cityColor}</code>
        </label>
        {(
          [
            ['cities', 'Cities', 100],
            ['lines', 'Routes & links', 30],
            ['particles', 'Particles', 30],
            ['pois', 'POI cores', 40],
            ['aircraft', 'Aircraft', 30],
          ] as const
        ).map(([key, label, max]) => (
          <label key={key}>
            {label} emission{' '}
            <div className="tuning-value">
              <input
                aria-label={`${label} emission slider`}
                type="range"
                min="0"
                max={max}
                step="0.1"
                value={emissions[key]}
                onChange={(e) =>
                  onEmissions({ ...emissions, [key]: Number(e.target.value) })
                }
              />
              <input
                aria-label={`${label} emission`}
                type="number"
                min="0"
                max={max}
                step="0.1"
                value={emissions[key]}
                onChange={(e) =>
                  onEmissions({
                    ...emissions,
                    [key]: Math.min(
                      max,
                      Math.max(0, Number(e.target.value) || 0)
                    ),
                  })
                }
              />
            </div>
          </label>
        ))}
      </fieldset>
      <p className="tuning-readout">
        City maximum before filtering: {luminance.toFixed(2)} linear luma;
        threshold {settings.threshold.toFixed(2)}. Texture filtering, night fade
        and bright-buffer downsampling reduce actual pixels. Bright pass shows
        what clears the threshold; Bloom only shows the resulting glow.
      </p>
    </aside>
  );
}
