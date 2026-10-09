/** Assign contiguous canonical rows using the coordinator's print measurements. */
export async function planBriefingPages({ payload, measure, budget }) {
  if (payload.schemaVersion !== 2 || !payload.legs?.length)
    throw new Error('Mission requires ordered legs');
  const fail = (code, message) => Object.assign(new Error(message), { code });
  const pages = [],
    legIds = new Set();
  for (const leg of payload.legs) {
    if (!leg.legId || legIds.has(leg.legId))
      throw new Error('Duplicate leg identity');
    legIds.add(leg.legId);
    if (new Set(leg.rows.map((r) => r.id)).size !== leg.rows.length)
      throw new Error('Duplicate row identity');
    const legPages = [];
    let offset = 0;
    do {
      if (legPages.length === 3)
        throw fail('page-budget', 'Leg exceeds three pages');
      const kind = legPages.length ? 'continuation' : 'primary';
      const remaining = leg.rows.slice(offset);
      const fits = async (count, continued) => {
        budget.workRemainingMs();
        const result = await measure({
          legId: leg.legId,
          kind,
          rowIds: remaining.slice(0, count).map((r) => r.id),
          continued,
        });
        budget.workRemainingMs();
        return result.fits === true;
      };
      let count = remaining.length;
      if (!(await fits(count, false))) {
        // Adding rows cannot reduce content height at fixed fonts and widths.
        let low = 0,
          high = count - 1;
        while (low < high) {
          const mid = Math.ceil((low + high) / 2);
          if (await fits(mid, true)) low = mid;
          else high = mid - 1;
        }
        count = low;
        if (!count || !(await fits(count, true)))
          throw fail('overflow', 'Essential content or one row cannot fit');
      }
      const rows = remaining.slice(0, count);
      legPages.push({
        legId: leg.legId,
        legPage: legPages.length + 1,
        kind,
        flightStartUtc: leg.flight.startUtc,
        flightEndUtc: leg.flight.endUtc,
        rowStartUtc: rows[0]?.startUtc ?? null,
        rowEndUtc: rows.at(-1)?.endUtc ?? null,
        rowIds: rows.map((r) => r.id),
      });
      offset += count;
    } while (offset < leg.rows.length);
    for (const page of legPages)
      pages.push({
        ...page,
        page: pages.length + 1,
        legPageCount: legPages.length,
      });
  }
  return {
    schemaVersion: 2,
    missionId: payload.missionId,
    snapshotFingerprint: payload.snapshotFingerprint,
    pages,
  };
}
