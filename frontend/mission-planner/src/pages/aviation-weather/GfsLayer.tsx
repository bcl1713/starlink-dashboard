import type { GfsView } from './gfs-controller';
import { useFrame } from '@react-three/fiber';
/** The controller owns the resources; React only attaches the admitted object. */
export function GfsLayer({ view }: { view: GfsView }) {
  useFrame((_, delta) => view.drawing?.update?.(delta));
  return view.drawing ? (
    <primitive
      key={view.drawing.object.uuid}
      object={view.drawing.object}
      dispose={null}
    />
  ) : null;
}
