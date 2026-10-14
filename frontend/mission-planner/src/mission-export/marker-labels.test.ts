import { describe, expect, it } from 'vitest';
import { placeMarkerLabels } from './marker-labels';

describe('canonical marker label placement', () => {
  it('keeps different windows at the same anchor visible and distinct', () => {
    const anchors = ['window-1', 'window-2', 'window-3'].map((id, index) => ({
      id,
      text: String(index + 1),
      x: 600,
      y: 400,
    }));
    const labels = placeMarkerLabels(anchors, 1920, 1080);
    expect(labels.map((label) => label.id)).toEqual(
      anchors.map((anchor) => anchor.id)
    );
    expect(new Set(labels.map((label) => `${label.x},${label.y}`)).size).toBe(
      3
    );
    expect(
      labels.every((label) => label.anchorX === 600 && label.anchorY === 400)
    ).toBe(true);
    for (const label of labels) {
      expect(label.x - label.radius).toBeGreaterThanOrEqual(0);
      expect(label.y - label.radius).toBeGreaterThanOrEqual(0);
      expect(label.x + label.radius).toBeLessThanOrEqual(1920);
      expect(label.y + label.radius).toBeLessThanOrEqual(1080);
    }
  });
  it('rejects a layout that cannot display all labels instead of dropping identities', () => {
    expect(() =>
      placeMarkerLabels(
        Array.from({ length: 200 }, (_, index) => ({
          id: `window-${index}`,
          text: String(index),
          x: 50,
          y: 50,
        })),
        320,
        240
      )
    ).toThrow(/labels/);
  });
});
