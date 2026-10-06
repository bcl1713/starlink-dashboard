import type { AviationView } from './aviation-controller';
// Geometry/material ownership belongs to the controller; React only attaches
// admitted objects. Fiber must not dispose objects retained between renders.
export function AviationLayer({ view }: { view: AviationView }) {
  return (
    <group name="Native aviation weather">
      {Object.entries(view.layers).map(([layer, item]) =>
        item.drawing ? (
          <primitive
            key={`${layer}:${item.drawing.object.uuid}`}
            object={item.drawing.object}
            dispose={null}
          />
        ) : null
      )}
    </group>
  );
}
