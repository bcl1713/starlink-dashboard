import { labels, type Descriptor } from './model';

export const scalarPalette = {
  units: 'K',
  minimum: 190,
  maximum: 310,
  ticks: [190, 250, 310],
  opacity: 0.4,
  stops: [
    [0, 0.25, 1],
    [0.5, 0.25, 0.5],
    [1, 0.25, 0],
  ],
  unavailable:
    'Unavailable: outside coverage (1), missing (2), quality rejected (3); transparent',
};

export function mountProofLabel(d: Descriptor, detail = '') {
  const label = document.createElement('aside');
  label.dataset.aviationProof = 'true';
  label.style.cssText =
    'position:fixed;z-index:9999;bottom:10px;left:12px;max-width:min(900px,calc(100vw - 44px));background:#101829ee;color:white;font:12px sans-serif;padding:10px;pointer-events:none';
  label.textContent = `DIAGNOSTIC • ${labels(d)} • ${detail} • ${(d.attribution ?? []).join('; ')}`;
  if (d.representation === 'latlon-grid-v1') {
    const legend = document.createElement('div');
    legend.dataset.aviationPalette = JSON.stringify(scalarPalette);
    legend.setAttribute('aria-label', 'Weather temperature palette');
    legend.textContent = `${d.region_intervals || typeof d.scan_start_ms === 'number' ? 'IR brightness temperature' : 'Model temperature'}: 190 K · 250 K · 310 K • opacity 40% • ${scalarPalette.unavailable}`;
    const ramp = document.createElement('div');
    ramp.dataset.paletteRamp = 'true';
    ramp.style.cssText =
      'height:12px;max-width:320px;margin:4px 0;background:linear-gradient(to right,rgb(0,64,255),rgb(128,64,128),rgb(255,64,0))';
    legend.prepend(ramp);
    label.append(legend);
  }
  const place = () =>
    (document.fullscreenElement ?? document.body).append(label);
  document.addEventListener('fullscreenchange', place);
  place();
  return Object.assign(label, {
    dispose: () => {
      document.removeEventListener('fullscreenchange', place);
      label.remove();
    },
  });
}
