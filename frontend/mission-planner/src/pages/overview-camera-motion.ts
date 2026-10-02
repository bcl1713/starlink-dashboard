/** Progress follows a speed/acceleration-limited path; no duration is prescribed. */
export function cameraMotionLimits(
  angle: number,
  zoom: number,
  offset: number
) {
  const channels = [
    [angle, (10 * Math.PI) / 180, (2 * Math.PI) / 180],
    [zoom, 0.5, 0.15],
    [offset, 0.12, 0.04],
  ].filter(([travel]) => travel > 1e-10);
  return channels.length
    ? {
        maxSpeed: Math.min(
          ...channels.map(([travel, speed]) => speed / travel)
        ),
        acceleration: Math.min(
          ...channels.map(([travel, , acceleration]) => acceleration / travel)
        ),
      }
    : { maxSpeed: 0, acceleration: 0 };
}

export function advanceCameraMotion(
  progress: number,
  speed: number,
  delta: number,
  maxSpeed: number,
  acceleration: number
) {
  if (!maxSpeed || !acceleration) return { progress: 1, speed: 0 };
  let remainingTime = Math.max(0, delta);
  // Split a frame at acceleration/cruise/braking boundaries for exact stopping.
  for (let i = 0; i < 4 && remainingTime > 1e-10 && progress < 1; i++) {
    const remaining = 1 - progress;
    const brakingDistance = (speed * speed) / (2 * acceleration);
    if (remaining <= brakingDistance + 1e-10) {
      const step = Math.min(remainingTime, speed / acceleration);
      progress += speed * step - (acceleration * step * step) / 2;
      speed = Math.max(0, speed - acceleration * step);
      remainingTime -= step;
      if (speed < 1e-10) return { progress: 1, speed: 0 };
    } else if (speed >= maxSpeed - 1e-10) {
      const step = Math.min(
        remainingTime,
        (remaining - brakingDistance) / speed
      );
      progress += speed * step;
      remainingTime -= step;
    } else {
      const untilBraking =
        (Math.sqrt((speed * speed) / 2 + acceleration * remaining) - speed) /
        acceleration;
      const step = Math.min(
        remainingTime,
        (maxSpeed - speed) / acceleration,
        untilBraking
      );
      progress += speed * step + (acceleration * step * step) / 2;
      speed += acceleration * step;
      remainingTime -= step;
    }
  }
  return { progress: Math.min(1, progress), speed };
}
