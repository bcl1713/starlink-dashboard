import type { GfsView } from './gfs-controller';
/** The controller owns the resources; React only attaches the admitted object. */
export function GfsLayer({ view }: { view: GfsView }) {
  return view.drawing ? (
    <primitive
      key={view.drawing.object.uuid}
      object={view.drawing.object}
      dispose={null}
    />
  ) : null;
}
