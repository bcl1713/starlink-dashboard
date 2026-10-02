import { expect, it } from 'vitest';
import {
  advanceCameraMotion,
  cameraMotionLimits,
} from './overview-camera-motion';

it('settles tiny moves without imposing a minimum duration', () => {
  const limits = cameraMotionLimits(0.0001, 0, 0);
  let state = { progress: 0, speed: 0 };
  for (let i = 0; i < 10; i++)
    state = advanceCameraMotion(
      state.progress,
      state.speed,
      1 / 60,
      limits.maxSpeed,
      limits.acceleration
    );
  expect(state).toEqual({ progress: 1, speed: 0 });
});

it('splits a large frame across acceleration, cruise and braking without overshooting', () => {
  const limits = cameraMotionLimits(Math.PI, 0, 0);
  expect(
    advanceCameraMotion(0, 0, 100, limits.maxSpeed, limits.acceleration)
  ).toEqual({ progress: 1, speed: 0 });
});
