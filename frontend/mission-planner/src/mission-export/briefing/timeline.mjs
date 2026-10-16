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
export const TRANSPORT_BLUE = '#899db9';
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
  let out = `<svg class="timeline" viewBox="0 0 1240 246" role="img" aria-label="Communications posture, transport availability and SOF restrictions">`;

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
        state === 'Down'
          ? TRANSPORT_BLUE
          : state === '?'
            ? '#dce2e8'
            : '#edf1f5',
        `data-transport="${n}" data-state="${escapeText(state)}"${n === 2 && i.xStarshieldConflict ? ` data-x-starshield-conflict="${escapeText(i.xStarshieldConflict)}"` : ''}`
      );
    }
    if (n === 2) {
      const conflicts = [];
      for (const i of payload.intervals) {
        const kind = i.xStarshieldConflict;
        if (
          !(
            (kind === 'blocked' && i.decisions[n] === 'Down') ||
            (kind === 'released' && i.decisions[n] === 'Up')
          )
        )
          continue;
        const last = conflicts.at(-1);
        if (
          last &&
          last.endUtc === i.startUtc &&
          last.xStarshieldConflict === kind
        )
          last.endUtc = i.endUtc;
        else conflicts.push({ ...i });
      }
      for (const run of conflicts) {
        const label =
          run.xStarshieldConflict === 'blocked'
            ? 'Starshield conflict'
            : 'Conflict released';
        const shown =
          width(run) >= 150
            ? label
            : width(run) >= 60
              ? run.xStarshieldConflict === 'blocked'
                ? 'Conflict'
                : run.xStarshieldConflict === 'released'
                  ? 'Released'
                  : ''
              : '';
        if (shown)
          out += text(
            x(run.startUtc) + width(run) / 2,
            y + 14,
            shown,
            `text-anchor="middle" class="lane-state conflict-label${run.xStarshieldConflict === 'blocked' ? ' light' : ''}" data-conflict-label data-svg-label`
          );
      }
    }
    const unknownRuns = [];
    for (const i of payload.intervals) {
      if (i.decisions[n] !== '?') continue;
      const last = unknownRuns.at(-1);
      if (last && last.endUtc === i.startUtc) last.endUtc = i.endUtc;
      else unknownRuns.push({ ...i });
    }
    for (const run of unknownRuns) {
      if (width(run) >= 40)
        out += text(
          x(run.startUtc) + width(run) / 2,
          y + 14,
          '?',
          'text-anchor="middle" class="lane-state"'
        );
    }
  });
  for (const transition of payload.popTransitions ?? []) {
    const low = Math.max(start, Date.parse(transition.windowStartUtc));
    const high = Math.min(end, Date.parse(transition.windowEndUtc));
    if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low)
      continue;
    out += rect(
      {
        startUtc: new Date(low).toISOString(),
        endUtc: new Date(high).toISOString(),
      },
      144,
      22,
      'none',
      `data-pop-transition="${escapeText(transition.id)}" stroke="#735124" stroke-width="2" role="img" aria-label="Starshield PoP transition possible — brief call interruption."`
    );
  }
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
    out += rect(i, 202, 18, TRANSPORT_BLUE, 'data-restriction');
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
