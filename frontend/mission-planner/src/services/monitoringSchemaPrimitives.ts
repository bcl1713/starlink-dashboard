import { z } from 'zod';

const MAX_EXTERNAL_TEXT = 200;

export const finite = z.number().finite();
export const instant = z.string().datetime({ offset: true });
export const text = z.string().max(MAX_EXTERNAL_TEXT);
export const coordinate = z.strictObject({
  latitude: finite.min(-90).max(90),
  longitude: finite.min(-180).max(180),
});
