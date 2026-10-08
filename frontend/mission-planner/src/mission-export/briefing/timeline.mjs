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
  let out = `<svg class="timeline" viewBox="0 0 1240 218" role="img" aria-label="Communications posture, transport availability and SOF restrictions"><defs><pattern id="down" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#d2d8df"/><path d="M0 8L8 0" stroke="#99a4b0"/></pattern></defs>`;

  out += text(0, 64, 'Overall posture', 'class="hero-label"');
  for (const i of payload.intervals) {
    const w = width(i),
      px = x(i.startUtc);
    out += rect(
      i,
      40,
      38,
      COLORS[i.posture] || COLORS['Posture uncertain'],
      `data-posture="${escapeText(i.posture)}" data-interval-start="${i.startUtc}"`
    );
    const uncertain = i.posture === 'Posture uncertain';
    const label = uncertain
      ? `${i.decisions.filter((v) => v === 'Up').length} confirmed`
      : {
          Nominal: '3-Up',
          Degraded: '2-Up',
          'Limited / elevated risk': '1-Up',
          'Communications unavailable': '0-Up',
        }[i.posture] || i.posture;
    if (uncertain) continue;
    if (w >= 90)
      out += text(
        px + w / 2,
        65,
        label,
        `text-anchor="middle" class="band-label ${i.posture === 'Nominal' ? 'light' : ''}" data-svg-label`
      );
    else if (i.posture === 'Communications unavailable')
      out +=
        `<path d="M${px + w / 2} 40V15H${px + 68}" fill="none" stroke="#b72e36"/>` +
        text(
          px + 73,
          20,
          '0-Up · 5 min',
          'class="outage-callout" data-callout data-svg-label'
        );
  }
  for (const i of unknownGroups.filter((i) => width(i) >= 90)) {
    out += text(
      x(i.startUtc) + width(i) / 2,
      65,
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
        `<path d="M${anchor} 40L${labelX} 24" fill="none" stroke="#526678"/>` +
        text(
          labelX,
          20,
          `${i.decisions.filter((v) => v === 'Up').length} confirmed`,
          'text-anchor="middle" class="confirmed-callout" data-callout data-svg-label'
        );
    });
  }
  ['Commercial Ka', 'Starshield', 'X-Band MILSATCOM'].forEach((name, n) => {
    const y = 91 + n * 27;
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
      if (width(i) > 80)
        out += text(
          x(i.startUtc) + width(i) / 2,
          y + 14,
          state,
          'text-anchor="middle" class="lane-state"'
        );
    }
  });
  out += text(0, 188, 'SOF / AR', 'class="lane-label"');
  out += '<rect x="280" y="174" width="960" height="18" fill="#edf1f5"/>';
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
    out += rect(i, 174, 18, '#899db9', 'data-restriction');
    const a = x(i.startUtc);
    out += text(
      a < 700 ? a + width(i) + 8 : a - 8,
      188,
      i.label,
      `text-anchor="${a < 700 ? 'start' : 'end'}" class="restriction-label" data-svg-label`
    );
  }
  const et = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  for (let h = 0; h <= 8; h++) {
    const t = start + ((end - start) * h) / 8;
    const px = 280 + (960 * h) / 8;
    out +=
      `<path d="M${px} 196v5" stroke="#83909e"/>` +
      text(
        px,
        216,
        et.format(t),
        `text-anchor="${h === 0 ? 'start' : h === 8 ? 'end' : 'middle'}" class="axis"`
      );
  }
  return out + '</svg>';
}
