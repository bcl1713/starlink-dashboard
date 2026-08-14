interface MapLegendProps {
  hasTimeline: boolean;
}

const routeItems = [
  { label: 'Flight route', color: 'var(--route-reference)', style: 'solid' },
  { label: 'X-band handoff', color: 'var(--route-handoff)', style: 'point' },
  { label: 'Ka transition', color: 'var(--route-transition)', style: 'point' },
  { label: 'AAR segment', color: 'var(--route-air-refuel)', style: 'dashed' },
  {
    label: 'Manual AR track',
    color: 'var(--route-manual-track)',
    style: 'dashed',
  },
];

const statusItems = [
  { label: 'Nominal', color: 'var(--status-nominal)', style: 'solid' },
  { label: 'Advisory', color: 'var(--status-advisory)', style: 'solid' },
  { label: 'Degraded', color: 'var(--status-degraded)', style: 'solid' },
  { label: 'Critical', color: 'var(--status-critical)', style: 'solid' },
];

export function MapLegend({ hasTimeline }: MapLegendProps) {
  const items = hasTimeline ? [...routeItems, ...statusItems] : routeItems;

  return (
    <details className="absolute right-3 top-3 z-[1000] max-w-52 rounded-md border border-border bg-card/95 text-card-foreground shadow-sm backdrop-blur">
      <summary className="cursor-pointer px-3 py-2 text-xs font-semibold tracking-wide marker:content-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Map legend
      </summary>
      <ul className="space-y-1 border-t border-border px-3 py-2 text-xs text-muted-foreground">
        {items.map((item) => (
          <li key={item.label} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={
                item.style === 'point'
                  ? 'h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-card'
                  : `h-1 w-5 shrink-0 rounded ${
                      item.style === 'dashed' ? 'border-t-2 border-dashed' : ''
                    }`
              }
              style={
                item.style === 'dashed'
                  ? { borderColor: item.color }
                  : { backgroundColor: item.color }
              }
            />
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
