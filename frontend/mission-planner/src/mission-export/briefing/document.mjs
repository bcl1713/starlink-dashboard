import { renderTimeline, escapeText as e } from './timeline.mjs';
function dataAsset(value, kind) {
  if (!value?.startsWith(`data:${kind}`) || /["<>]/.test(value))
    throw new Error('Only embedded assets accepted');
  return value;
}
export function composeBriefing(
  payload,
  { mapDataUrl, apoDataUrl, regularFontDataUrl, boldFontDataUrl, cssText }
) {
  const regular = dataAsset(regularFontDataUrl, 'font/'),
    bold = dataAsset(boldFontDataUrl, 'font/'),
    apo = dataAsset(apoDataUrl, 'image/');
  if (/<\/style/i.test(cssText) || /https?:|@import/i.test(cssText))
    throw new Error('Nonlocal CSS rejected');
  const short = (s) =>
    s
      .replaceAll('Commercial Ka', 'Ka')
      .replaceAll('X-Band MILSATCOM', 'X-Band');
  const rows = payload.rows
    .map((r) => {
      const cells = r.displayCells ?? [
        r.et.replaceAll(' ET', ''),
        short(r.impact),
        short(r.remaining.replaceAll(' + ', ', ')),
        {
          'Limited / elevated risk': 'Elevated risk',
          'Communications unavailable': 'Unavailable',
          'Assessment incomplete': 'Incomplete',
        }[r.posture] || r.posture,
      ];
      if (
        !Array.isArray(cells) ||
        cells.length !== 4 ||
        cells.some((cell) => typeof cell !== 'string')
      )
        throw new Error('Expected four display cells');
      return `<tr data-row-id="${e(r.id)}" data-fit><td class="et">${e(cells[0])}</td><td>${e(cells[1])}</td><td class="remaining-cell" data-fit>${e(cells[2])}</td><td class="posture-cell">${e(cells[3])}</td></tr>`;
    })
    .join('');
  const map = mapDataUrl
    ? `<aside class="map-card" data-fit><img src="${dataAsset(mapDataUrl, 'image/')}" alt="Mission route between departure and arrival airports" data-fit></aside>`
    : '';
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'"><title>${e(payload.header.title)}</title><style>@font-face{font-family:Briefing;src:url('${regular}');font-weight:400}@font-face{font-family:Briefing;src:url('${bold}');font-weight:700}${cssText}</style></head><body><main class="briefing-page ${map ? 'with-map' : 'without-map'}" data-ready="true"><header><div class="header-copy" data-fit><div class="eyebrow">CUSTOMER MISSION BRIEF · TRIAL <span>${e(payload.header.date)}</span></div><h1 data-fit>${e(payload.header.title)}</h1>${payload.header.subtitle ? `<p class="subtitle" data-fit>${e(payload.header.subtitle)}</p>` : ''}<p class="timing" data-fit>${e(payload.header.timing)}</p></div><img class="apo" src="${apo}" alt="APO" data-fit></header><section class="timeline-section" data-fit>${payload.header.notice ? `<p class="notice" data-fit>${e(payload.header.notice)}</p>` : ''}${renderTimeline(payload)}<div class="legend" data-fit><span class="nominal">Nominal</span><span class="degraded">Degraded</span><span class="limited">Elevated risk</span><span class="unavailable">Communications unavailable</span></div></section><section class="details"><div class="table-card" data-fit><h2 data-fit>COORDINATION WINDOWS <span>ALL TIMES ET</span></h2><table data-fit><colgroup><col class="time-col"><col class="impact-col"><col class="remain-col"><col class="posture-col"></colgroup><thead><tr data-fit><th>ET</th><th>Event / impact</th><th>Remaining comms</th><th>Posture</th></tr></thead><tbody>${rows}</tbody></table></div>${map}</section><footer data-fit>Communications posture is a prediction, not a throughput guarantee. SOF / AR restrictions remain independent of transport availability.</footer></main></body></html>`;
}
