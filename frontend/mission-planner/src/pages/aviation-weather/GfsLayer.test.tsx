import { expect, it } from 'vitest';
import { create } from '@react-three/test-renderer';
import { lease } from '@/test/gfs-lease';
import { createGridDrawing } from './grid-renderer';
import { WeatherBudget } from './weather-budget';
import { GfsLayer } from './GfsLayer';
import { emptyGfsView } from './gfs-controller';

it('advances only the currently attached drawing and leaves disposal to its owner', async () => {
  const budget = new WeatherBudget(),
    a = createGridDrawing(lease(), { winds: true, temperature: false }, budget);
  const renderer = await create(
    <GfsLayer view={{ ...emptyGfsView, drawing: a }} />
  );
  await renderer.advanceFrames(2, 1 / 30);
  const first = a.object.getObjectByName('GFS wind particles');
  expect(first).toBeTruthy();
  expect(first!.userData.windParticles.vertexCount).toBeGreaterThan(0);
  const b = createGridDrawing(
    lease(),
    { winds: false, temperature: true },
    budget
  );
  const before = first!.userData.windParticles.points.slice();
  await renderer.update(<GfsLayer view={{ ...emptyGfsView, drawing: b }} />);
  await renderer.advanceFrames(2, 1 / 30);
  expect(Array.from(first!.userData.windParticles.points)).toEqual(
    Array.from(before)
  );
  await renderer.unmount();
  a.dispose();
  b.dispose();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
