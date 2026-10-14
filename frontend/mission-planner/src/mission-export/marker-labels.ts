export interface MarkerAnchor {
  id: string;
  text: string;
  x: number;
  y: number;
}
export interface MarkerLabel extends MarkerAnchor {
  anchorX: number;
  anchorY: number;
  radius: number;
  fontSize: number;
}

/** Move labels only; exact occurrence anchors and identities remain untouched. */
export function placeMarkerLabels(
  anchors: MarkerAnchor[],
  width: number,
  height: number
): MarkerLabel[] {
  const scale = Math.min(width / 280, height / 180);
  const labels: MarkerLabel[] = [];
  for (const anchor of anchors) {
    const radius = (Math.max(18, anchor.text.length * 7 + 8) * scale) / 2;
    const gap = 3 * scale;
    let placed: MarkerLabel | undefined;
    for (let ring = 1; ring <= 7 && !placed; ring++) {
      for (let direction = 0; direction < 8; direction++) {
        const angle = (direction * Math.PI) / 4;
        const distance = (radius * 2 + gap) * ring;
        const x = anchor.x + Math.cos(angle) * distance;
        const y = anchor.y + Math.sin(angle) * distance;
        if (
          x - radius < 0 ||
          y - radius < 0 ||
          x + radius > width ||
          y + radius > height
        )
          continue;
        if (
          labels.some(
            (label) =>
              Math.hypot(x - label.x, y - label.y) < radius + label.radius + gap
          )
        )
          continue;
        if (
          anchors.some(
            (point) => Math.hypot(x - point.x, y - point.y) < radius + gap
          )
        )
          continue;
        placed = {
          ...anchor,
          x,
          y,
          anchorX: anchor.x,
          anchorY: anchor.y,
          radius,
          fontSize: 10 * scale,
        };
        break;
      }
    }
    if (!placed)
      throw new Error('Requested window labels cannot all fit this map view');
    labels.push(placed);
  }
  return labels;
}
