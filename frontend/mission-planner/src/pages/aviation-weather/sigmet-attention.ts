import type { AviationAdvisory } from '@/services/aviation-features';
import type {
  RouteSigmetEntry,
  SelectedSigmetEntry,
  RouteSigmetSnapshot,
} from '@/services/route-sigmets';
import { sigmetReportLabel } from './sigmet-report-label';

type Common = { reports: AviationAdvisory[]; label: string; color: string };
export type SigmetAttentionItem = Common &
  (
    | { kind: 'intersecting'; entry: RouteSigmetEntry }
    | { kind: 'selected'; entry: SelectedSigmetEntry }
  );
const colors = ['#7dd3fc', '#f0abfc', '#fde68a'];
export function sigmetNoticeColor(key: string): string {
  let hash = 0;
  for (const char of key) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return colors[hash % colors.length];
}
export function sigmetAttentionItems(
  snapshot: RouteSigmetSnapshot | null,
  reports: readonly AviationAdvisory[],
  nowMs: number
): SigmetAttentionItem[] {
  if (!snapshot?.context) return [];
  const byId = new Map(
    reports
      .filter(
        (r) =>
          !r.properties.cancelled &&
          r.properties.valid_from_ms <= nowMs &&
          nowMs < r.properties.expires_at_ms
      )
      .map((r) => [r.id, r])
  );
  const seen = new Set<string>();
  const items: SigmetAttentionItem[] = [];
  for (const kind of ['intersecting', 'selected'] as const) {
    const entries =
      kind === 'intersecting' ? snapshot.entries : snapshot.selected_entries;
    for (const entry of entries) {
      if (
        seen.has(entry.bulletin_key) ||
        entry.acknowledged ||
        entry.valid_from_ms > nowMs ||
        nowMs >= entry.expires_at_ms ||
        !entry.feature_ids.every((id) => byId.has(id))
      )
        continue;
      seen.add(entry.bulletin_key);
      const bound = entry.feature_ids.map((id) => byId.get(id)!);
      const common = {
        reports: bound,
        label: sigmetReportLabel(bound),
        color: sigmetNoticeColor(entry.bulletin_key),
      };
      if (kind === 'intersecting')
        items.push({ ...common, kind, entry: entry as RouteSigmetEntry });
      else items.push({ ...common, kind, entry });
    }
  }
  return items.sort(
    (a, b) =>
      b.entry.attention_order - a.entry.attention_order ||
      a.entry.notice_key.localeCompare(b.entry.notice_key)
  );
}
