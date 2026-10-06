import { labels, type Descriptor } from './model';

export function mountProofLabel(d: Descriptor, detail = '') {
  const label = document.createElement('aside');
  label.dataset.aviationProof = 'true';
  label.style.cssText =
    'position:fixed;z-index:9999;bottom:10px;left:12px;max-width:900px;background:#101829ee;color:white;font:12px sans-serif;padding:10px;pointer-events:none';
  label.textContent = `DIAGNOSTIC • ${labels(d)} • ${detail} • ${(d.attribution ?? []).join('; ')}`;
  document.body.append(label);
  return label;
}
