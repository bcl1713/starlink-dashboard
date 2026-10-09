/** Exact UTC geometry. This module never derives transport availability. */
export const escapeText = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ]
  );
export const COLORS = {
  Nominal: '#367755',
  Degraded: '#e6bd4a',
  'Limited / elevated risk': '#da813a',
  'Communications unavailable': '#b72e36',
  'Posture uncertain': '#dce2e8',
};
export function renderTimeline(payload) {
  const start = Date.parse(payload.flight.startUtc),
    end = Date.parse(payload.flight.endUtc);
  if (!Number.isFinite(start) || end <= start)
    throw new Error('Invalid flight bounds');
  const x = (t) => 280 + ((Date.parse(t) - start) / (end - start)) * 960;
  const width = (i) =>
    ((Date.parse(i.endUtc) - Date.parse(i.startUtc)) / (end - start)) * 960;
  const text = (a, b, s, extra = '') =>
    `<text x="${a}" y="${b}" ${extra}>${escapeText(s)}</text>`;
  const rect = (i, y, h, color, extra = '') =>
    `<rect x="${x(i.startUtc)}" y="${y}" ${extra} width="${width(i)}" height="${h}" fill="${color}"/>`;
  const unknownGroups = [];
  for (const i of payload.intervals) {
    if (i.posture !== 'Posture uncertain') continue;
    const count = i.decisions.filter((v) => v === 'Up').length;
    const last = unknownGroups.at(-1);
    if (last && last.endUtc === i.startUtc && last.count === count)
      last.endUtc = i.endUtc;
    else unknownGroups.push({ ...i, count });
  }
  const narrowUnknown = unknownGroups.filter((i) => width(i) < 90);
  let out = `<svg class="timeline" viewBox="0 0 1240 246" role="img" aria-label="Communications posture, transport availability and SOF restrictions"><defs><pattern id="down" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#d2d8df"/><path d="M0 8L8 0" stroke="#99a4b0"/></pattern></defs>`;

  out += text(
    0,
    24,
    'Overall communications posture',
    'class="hero-label" data-svg-label'
  );
  for (const i of payload.intervals) {
    out += rect(
      i,
      68,
      38,
      COLORS[i.posture] || COLORS['Posture uncertain'],
      `data-posture="${escapeText(i.posture)}" data-interval-start="${i.startUtc}"`
    );
  }
  const nominalGroups = [];
  for (const i of payload.intervals) {
    if (i.posture !== 'Nominal') continue;
    const last = nominalGroups.at(-1);
    if (last && last.endUtc === i.startUtc) last.endUtc = i.endUtc;
    else nominalGroups.push({ ...i });
  }
  for (const i of nominalGroups) {
    if (width(i) >= 110) {
      out += text(
        x(i.startUtc) + width(i) / 2,
        93,
        'Nominal',
        'text-anchor="middle" class="band-label light" data-svg-label'
      );
    }
  }
  for (const i of unknownGroups.filter((i) => width(i) >= 90)) {
    out += text(
      x(i.startUtc) + width(i) / 2,
      93,
      `${i.count} confirmed`,
      'text-anchor="middle" class="band-label" data-svg-label'
    );
  }
  if (narrowUnknown.length) {
    const center =
      (x(narrowUnknown[0].startUtc) + x(narrowUnknown.at(-1).endUtc)) / 2;
    narrowUnknown.forEach((i, n) => {
      const anchor = x(i.startUtc) + width(i) / 2;
      const labelX = center + (n - (narrowUnknown.length - 1) / 2) * 180;
      out +=
        `<path d="M${anchor} 68L${labelX} 58" fill="none" stroke="#526678"/>` +
        text(
          labelX,
          54,
          `${i.decisions.filter((v) => v === 'Up').length} confirmed`,
          'text-anchor="middle" class="confirmed-callout" data-callout data-svg-label'
        );
    });
  }
  ['Commercial Ka', 'Starshield', 'X-Band MILSATCOM'].forEach((name, n) => {
    const y = 119 + n * 27;
    out += text(0, y + 15, name, 'class="lane-label"');
    for (const i of payload.intervals) {
      const state = i.decisions[n];
      out += rect(
        i,
        y,
        18,
        state === 'Down' ? 'url(#down)' : state === '?' ? '#e9edf1' : '#b8c7cc',
        `data-transport="${n}" data-state="${escapeText(state)}"`
      );
    }
    const runs = [];
    for (const i of payload.intervals) {
      const state = i.decisions[n];
      const last = runs.at(-1);
      if (last && last.endUtc === i.startUtc && last.state === state)
        last.endUtc = i.endUtc;
      else runs.push({ ...i, state });
    }
    for (const run of runs) {
      if (width(run) >= 40)
        out += text(
          x(run.startUtc) + width(run) / 2,
          y + 14,
          run.state,
          'text-anchor="middle" class="lane-state"'
        );
    }
  });
  out += text(0, 216, 'SOF / AR', 'class="lane-label"');
  out += '<rect x="280" y="202" width="960" height="18" fill="#edf1f5"/>';
  // Join identical restriction segments, but never their quiet gaps.
  const restrictions = [];
  for (const i of payload.intervals) {
    const label = i.restrictionLabels.join(' + ');
    if (!label) continue;
    const last = restrictions.at(-1);
    if (last && last.label === label && last.endUtc === i.startUtc)
      last.endUtc = i.endUtc;
    else restrictions.push({ ...i, label });
  }
  for (const i of restrictions) {
    out += rect(i, 202, 18, '#899db9', 'data-restriction');
  }
  const localDateClock = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  const zones = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    timeZoneName: 'short',
  });
  const zone = (t) =>
    zones.formatToParts(t).find((part) => part.type === 'timeZoneName').value;
  const repeated = (t) =>
    [-3600000, 3600000].some(
      (delta) => localDateClock.format(t) === localDateClock.format(t + delta)
    );
  const showZone =
    zone(start) !== zone(end) || repeated(start) || repeated(end);
  const tickTimes = Array.from(
    { length: 9 },
    (_, h) => start + ((end - start) * h) / 8
  );
  const seconds = tickTimes.some((t) => t % 60000 !== 0);
  const et = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    ...(showZone ? { timeZoneName: 'short' } : {}),
    ...(seconds ? { second: '2-digit' } : {}),
  });
  for (let h = 0; h <= 8; h++) {
    const t = tickTimes[h];
    const px = 280 + (960 * h) / 8;
    out += `<path d="M${px} 224v5" stroke="#83909e"/>`;
    // Keep every exact tick, with room for explicit offset identity.
    if (showZone && h % 2) continue;
    out += text(
      px,
      244,
      et.format(t),
      `text-anchor="${h === 0 ? 'start' : h === 8 ? 'end' : 'middle'}" class="axis" data-svg-label`
    );
  }
  return out + '</svg>';
}
