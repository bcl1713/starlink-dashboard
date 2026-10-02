import { CameraControlsImpl } from '@react-three/drei';
import { PerspectiveCamera } from 'three';

interface ProjectionAxis {
  value: number;
  target: number;
  velocity: number;
}

/** The same critically damped, speed-limited equation used by camera-controls. */
function dampProjection(
  axis: ProjectionAxis,
  smoothTime: number,
  delta: number
) {
  if (delta <= 0) return;
  const omega = 2 / Math.max(0.0001, smoothTime);
  const x = omega * delta;
  const decay = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const change = Math.max(
    -0.08 * smoothTime,
    Math.min(0.08 * smoothTime, axis.value - axis.target)
  );
  const intermediateTarget = axis.value - change;
  const momentum = (axis.velocity + omega * change) * delta;
  axis.velocity = (axis.velocity - omega * momentum) * decay;
  axis.value = intermediateTarget + (change + momentum) * decay;
  if (
    Math.abs(axis.value - axis.target) < 1e-7 &&
    Math.abs(axis.velocity) < 1e-7
  ) {
    axis.value = axis.target;
    axis.velocity = 0;
  }
}

/** One damped control for framing, following, reset, fullscreen and gestures. */
export class OverviewCameraControls extends CameraControlsImpl {
  maxAngularSpeed = (10 * Math.PI) / 180;
  private discardResumedDelta = false;
  private projection?: {
    width: number;
    height: number;
    x: ProjectionAxis;
    y: ProjectionAxis;
  };

  discardNextDelta() {
    this.discardResumedDelta = true;
  }

  setProjectionOffset(
    width: number,
    height: number,
    offsetX: number,
    offsetY: number,
    transition: boolean
  ) {
    if (!(this._camera instanceof PerspectiveCamera)) return;
    const view = this._camera.view;
    this.projection ??= {
      width,
      height,
      x: {
        value: view?.enabled ? view.offsetX / view.fullWidth : 0,
        target: 0,
        velocity: 0,
      },
      y: {
        value: view?.enabled ? view.offsetY / view.fullHeight : 0,
        target: 0,
        velocity: 0,
      },
    };
    const projection = this.projection;
    projection.width = width;
    projection.height = height;
    projection.x.target = offsetX / width;
    projection.y.target = offsetY / height;
    if (!transition) {
      for (const axis of [projection.x, projection.y]) {
        axis.value = axis.target;
        axis.velocity = 0;
      }
    }
    this.applyProjection();
  }

  resizeProjection(width: number, height: number) {
    if (!this.projection) return false;
    this.projection.width = width;
    this.projection.height = height;
    this.applyProjection();
    return true;
  }

  freezeProjection() {
    if (this.projection)
      for (const axis of [this.projection.x, this.projection.y]) {
        axis.target = axis.value;
        axis.velocity = 0;
      }
  }

  private applyProjection() {
    if (!(this._camera instanceof PerspectiveCamera) || !this.projection)
      return;
    const { width, height, x, y } = this.projection;
    this._camera.setViewOffset(
      width,
      height,
      x.value * width,
      y.value * height,
      width,
      height
    );
  }

  override update(delta: number) {
    if (document.hidden) return false;
    if (this.discardResumedDelta) {
      this.discardResumedDelta = false;
      delta = 0;
    }
    if (this.projection) {
      for (const axis of [this.projection.x, this.projection.y]) {
        dampProjection(axis, this.smoothTime, delta);
        if (axis.value !== axis.target || axis.velocity !== 0)
          this._needsUpdate = true;
      }
    }
    // CameraControls caps dolly speed but leaves rotation uncapped. Limit the
    // damping error vector exactly as its speed-limited dolly equation does.
    const theta = this._sphericalEnd.theta,
      phi = this._sphericalEnd.phi;
    if (!this._isUserControllingRotate) {
      const dx = theta - this._spherical.theta,
        dy = phi - this._spherical.phi;
      const distance = Math.hypot(dx, dy);
      const maximum = this.maxAngularSpeed * this.smoothTime;
      if (distance > maximum) {
        this._sphericalEnd.theta =
          this._spherical.theta + (dx * maximum) / distance;
        this._sphericalEnd.phi =
          this._spherical.phi + (dy * maximum) / distance;
      }
    }
    const updated = super.update(delta);
    this._sphericalEnd.theta = theta;
    this._sphericalEnd.phi = phi;
    this.applyProjection();
    return updated;
  }
}
