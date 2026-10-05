import { useState } from 'react';
import {
  DEFAULT_CHEVRON_SETTINGS,
  type ChevronSettings,
} from './overview-chevron-settings';
import './OverviewMarkerDebug.css';

const controls: {
  key: keyof ChevronSettings;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  {
    key: 'ownSizePixels',
    label: 'Our aircraft size',
    min: 6,
    max: 24,
    step: 1,
    unit: 'px',
  },
  {
    key: 'trafficSizePixels',
    label: 'Other aircraft size',
    min: 6,
    max: 24,
    step: 1,
    unit: 'px',
  },
  {
    key: 'coreWhiteness',
    label: 'Core brightness',
    min: 0,
    max: 1,
    step: 0.05,
    unit: '',
  },
  {
    key: 'coreWidthPixels',
    label: 'Colored edge width',
    min: 0.1,
    max: 3,
    step: 0.1,
    unit: 'px',
  },
  {
    key: 'glowWidthPixels',
    label: 'Glow width',
    min: 0.2,
    max: 5,
    step: 0.1,
    unit: 'px',
  },
  {
    key: 'glowStrength',
    label: 'Glow strength',
    min: 0,
    max: 1,
    step: 0.05,
    unit: '',
  },
];

export function OverviewMarkerDebug({
  settings,
  onChange,
}: {
  settings: Readonly<ChevronSettings>;
  onChange: (settings: ChevronSettings) => void;
}) {
  const [copyStatus, setCopyStatus] = useState('');
  const values = JSON.stringify(settings, null, 2);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(values);
      setCopyStatus('Copied');
    } catch {
      setCopyStatus('Select the values below to copy them.');
    }
  };
  return (
    <details className="overview-marker-debug" open>
      <summary>Aircraft marker tuning</summary>
      <p>Live preview. Copy the values when you like the result.</p>
      {controls.map(({ key, label, min, max, step, unit }) => (
        <label key={key}>
          <span>
            {label}{' '}
            <span aria-hidden="true">
              {settings[key]}
              {unit}
            </span>
          </span>
          <input
            aria-label={label}
            type="range"
            min={min}
            max={max}
            step={step}
            value={settings[key]}
            onChange={(event) => {
              setCopyStatus('');
              onChange({ ...settings, [key]: Number(event.target.value) });
            }}
          />
        </label>
      ))}
      <div className="overview-marker-debug-actions">
        <button type="button" onClick={() => void copy()}>
          Copy settings
        </button>
        <button
          type="button"
          onClick={() => {
            onChange({ ...DEFAULT_CHEVRON_SETTINGS });
            setCopyStatus('');
          }}
        >
          Reset defaults
        </button>
      </div>
      <span role="status">{copyStatus}</span>
      <textarea
        aria-label="Marker settings to share"
        readOnly
        value={values}
        onFocus={(event) => event.target.select()}
        rows={8}
      />
    </details>
  );
}
