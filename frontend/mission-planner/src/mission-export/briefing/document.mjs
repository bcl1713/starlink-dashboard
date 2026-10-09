import { renderTimeline, escapeText as e } from './timeline.mjs';
function dataAsset(value, kind) {
  if (!value?.startsWith(`data:${kind}`) || /["<>]/.test(value))
    throw new Error('Only embedded assets accepted');
  return value;
}
export function composeBriefing(
  payload,
  { mapDataUrl, apoDataUrl, regularFontDataUrl, boldFontDataUrl, cssText },
  page = null
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
      return `<tr data-row-id="${e(r.id)}" data-fit><td class="et" data-fit>${e(cells[0])}</td><td data-fit>${e(cells[1])}</td><td class="remaining-cell" data-fit>${e(cells[2])}</td><td class="posture-cell" data-fit>${e(cells[3])}</td></tr>`;
    })
    .join('');
  const pageCopy =
    page && (page.kind === 'continuation' || page.continued)
      ? `<p class="page-copy" data-fit>${page.kind === 'continuation' ? 'Coordination windows continued · ' : ''}Page ${page.legPage} of ${page.legPageCount}${payload.rows.length ? ` · Windows ${e(payload.rows[0].displayCells[0])} through ${e(payload.rows.at(-1).displayCells[0])}` : ''}${page.continued ? ' · continues on next page' : ''}</p>`
      : '';
  const map =
    mapDataUrl && page?.kind !== 'continuation'
      ? `<aside class="map-card" data-fit><img src="${dataAsset(mapDataUrl, 'image/')}" alt="Mission route between departure and arrival airports" data-fit></aside>`
      : '';
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'"><title>${e(payload.header.title)}</title><style>@font-face{font-family:Briefing;src:url('${regular}');font-weight:400}@font-face{font-family:Briefing;src:url('${bold}');font-weight:700}${cssText}</style></head><body><main class="briefing-page ${map ? 'with-map' : 'without-map'}${page?.kind === 'continuation' ? ' continuation' : ''}" data-leg-id="${e(payload.legId)}" data-ready="true"><header><div class="header-copy" data-fit><div class="eyebrow">CUSTOMER MISSION BRIEF · TRIAL <span>${e(payload.header.date)}</span></div><h1 data-fit>${e(payload.header.title)}</h1>${payload.header.subtitle ? `<p class="subtitle" data-fit>${e(payload.header.subtitle)}</p>` : ''}<p class="timing" data-fit>${e(payload.header.timing)}</p></div><img class="apo" src="${apo}" alt="APO" data-fit></header><section class="timeline-section" data-fit>${payload.header.notice ? `<p class="notice" data-fit>${e(payload.header.notice)}</p>` : ''}${page?.kind === 'continuation' ? '' : renderTimeline(payload)}<div class="legend" data-fit><span class="nominal">Nominal</span><span class="degraded">Degraded</span><span class="limited">Elevated risk</span><span class="unavailable">Communications unavailable</span></div></section>${pageCopy}<section class="details"><div class="table-card" data-fit><h2 data-fit>COORDINATION WINDOWS <span>ALL TIMES ET</span></h2><table data-fit><colgroup><col class="time-col"><col class="impact-col"><col class="remain-col"><col class="posture-col"></colgroup><thead><tr data-fit><th>ET</th><th>Event / impact</th><th>Remaining comms</th><th>Posture</th></tr></thead><tbody>${rows}</tbody></table></div>${map}</section><footer data-fit>All times are approximate. Communications posture is predicted, not guaranteed. SOF / AR restrictions are independent of transport availability.</footer></main></body></html>`;
}

/** Compose one candidate page; the coordinator measures this at print layout. */
export function composeMissionPage(leg, descriptor, assets) {
  const byId = new Map(leg.rows.map((row) => [row.id, row]));
  const rows = descriptor.rowIds.map((id) => {
    if (!byId.has(id)) throw new Error('Unknown page row');
    return byId.get(id);
  });
  return composeBriefing(
    { ...leg, rows },
    { ...assets, mapDataUrl: assets.maps?.[leg.legId] ?? assets.mapDataUrl },
    descriptor
  );
}

/** Assemble an already measured assignment without changing canonical records. */
export function composeMissionBriefing(payload, plan, assets) {
  if (
    payload.schemaVersion !== 2 ||
    plan.schemaVersion !== 2 ||
    payload.missionId !== plan.missionId ||
    payload.snapshotFingerprint !== plan.snapshotFingerprint
  )
    throw new Error('Mission/page identity mismatch');
  const expected = payload.legs.flatMap((leg) =>
    leg.rows.map((row) => [leg.legId, row.id])
  );
  const assigned = plan.pages.flatMap((page) =>
    page.rowIds.map((id) => [page.legId, id])
  );
  if (JSON.stringify(expected) !== JSON.stringify(assigned))
    throw new Error('Mission page row coverage mismatch');
  const documents = plan.pages.map((page) => {
    const leg = payload.legs.find((leg) => leg.legId === page.legId);
    if (!leg) throw new Error('Unknown page leg identity');
    return composeMissionPage(
      leg,
      { ...page, continued: page.legPage < page.legPageCount },
      assets
    );
  });
  if (!documents.length) throw new Error('Mission requires pages');
  const head = documents[0].slice(0, documents[0].indexOf('<body>') + 6);
  const bodies = documents.map((doc) =>
    doc.slice(doc.indexOf('<body>') + 6, doc.lastIndexOf('</body>'))
  );
  return head + bodies.join('') + '</body></html>';
}
