import {
  json2satrec,
  propagate,
  gstime,
  eciToEcf,
  type SatRec,
} from 'satellite.js';
import {
  EARTH_RADIUS_KM,
  ELEMENT_FIELDS,
  MAX_OBJECTS,
  type CatalogObject,
  type PropagationResult,
} from './types';

export function epochEligible(epoch: string, utcMs: number): boolean {
  const time = Date.parse(epoch);
  return (
    Number.isFinite(time) &&
    time >= utcMs - 72 * 3600_000 &&
    time <= utcMs + 600_000
  );
}

/** Records are initialized only on catalog installation, never on animation frames. */
export class CatalogPropagator {
  private records: { object: CatalogObject; record: SatRec | null }[];
  readonly ids: string[];
  constructor(objects: readonly CatalogObject[]) {
    this.records = [...objects]
      .sort((a, b) => Number(a.NORAD_CAT_ID) - Number(b.NORAD_CAT_ID))
      .slice(0, MAX_OBJECTS)
      .map((object) => {
        let record: SatRec | null = null;
        try {
          if (
            ELEMENT_FIELDS.every((key) => Number.isFinite(object[key])) &&
            object.MEAN_MOTION > 0 &&
            object.ECCENTRICITY >= 0 &&
            object.ECCENTRICITY < 1
          ) {
            // Only unused descriptive metadata is supplied for the library's type.
            // All propagation elements come from the validated provider object.
            record = json2satrec({
              ...object,
              OBJECT_NAME: '',
              OBJECT_ID: '',
              ELEMENT_SET_NO: 0,
            });
          }
        } catch {
          record = null;
        }
        return { object, record };
      });
    this.ids = this.records.map(({ object }) => object.NORAD_CAT_ID);
  }
  update(
    utcMs: number,
    positionsKm = new Float64Array(this.ids.length * 3),
    valid = new Uint8Array(this.ids.length)
  ): PropagationResult {
    positionsKm.fill(0);
    valid.fill(0);
    const date = new Date(utcMs),
      angle = gstime(date);
    if (Number.isFinite(utcMs))
      this.records.forEach(({ object, record }, index) => {
        if (!record || !epochEligible(object.EPOCH, utcMs)) return;
        try {
          const result = propagate(record, date);
          if (!result || record.error || !result.position) return;
          const { x, y, z } = eciToEcf(result.position, angle);
          if (
            ![x, y, z].every(Number.isFinite) ||
            Math.hypot(x, y, z) <= EARTH_RADIUS_KM
          )
            return;
          positionsKm.set([x, y, z], index * 3);
          valid[index] = 1;
        } catch {
          /* One failed spacecraft cannot invalidate its neighbors. */
        }
      });
    return {
      utcMs,
      ids: this.ids,
      positionsKm: positionsKm.subarray(0, this.ids.length * 3),
      valid: valid.subarray(0, this.ids.length),
    };
  }
}
export function propagateCatalog(
  objects: readonly CatalogObject[],
  utcMs: number
): PropagationResult {
  return new CatalogPropagator(objects).update(utcMs);
}
