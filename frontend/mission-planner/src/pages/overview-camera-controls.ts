import { CameraControlsImpl } from '@react-three/drei';

/** Preserve the current transition across hidden tabs without replaying hidden time. */
export class OverviewCameraControls extends CameraControlsImpl {
  private discardResumedDelta = false;

  discardNextDelta() {
    this.discardResumedDelta = true;
  }

  override update(delta: number) {
    if (document.hidden) return false;
    if (this.discardResumedDelta) {
      this.discardResumedDelta = false;
      return super.update(0);
    }
    return super.update(delta);
  }
}
