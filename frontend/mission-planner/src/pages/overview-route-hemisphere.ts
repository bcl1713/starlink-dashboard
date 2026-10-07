import { Matrix3, Triangle, Vector3 } from 'three';

/** Find a containing hemisphere from route extremes, independent of sample density.
 * The closest point to the origin in their convex hull faces the smallest cap.
 * Fully correct a support of at most four points each step, avoiding slow segment
 * convergence near the horizon. A hull containing the origin has no hemisphere.
 */
export function routeHemisphere(points: Vector3[]): Vector3 | null {
  const directions = points.map((point) => point.clone().normalize());
  let support = [directions[0]];
  const center = support[0].clone();
  const origin = new Vector3();
  for (let iteration = 0; iteration < 256; iteration++) {
    const extreme = directions.reduce((worst, point) =>
      point.dot(center) < worst.dot(center) ? point : worst
    );
    if (center.lengthSq() - extreme.dot(center) < 1e-10) break;
    const vertices = [...support, extreme];
    if (vertices.length === 4) {
      const [a, b, c, d] = vertices.map((p) => p.clone());
      a.sub(d);
      b.sub(d);
      c.sub(d);
      const basis = new Matrix3().set(
        a.x,
        b.x,
        c.x,
        a.y,
        b.y,
        c.y,
        a.z,
        b.z,
        c.z
      );
      if (Math.abs(basis.determinant()) > 1e-12) {
        const weights = d.negate().applyMatrix3(basis.invert());
        if (
          Math.min(weights.x, weights.y, weights.z) >= -1e-10 &&
          weights.x + weights.y + weights.z <= 1 + 1e-10
        )
          return null;
      }
    }
    let closest = vertices[0].clone(),
      nextSupport = [vertices[0]];
    const consider = (point: Vector3, active: Vector3[]) => {
      if (point.lengthSq() < closest.lengthSq()) {
        closest = point;
        nextSupport = active;
      }
    };
    for (let i = 0; i < vertices.length; i++) {
      const a = vertices[i];
      consider(a.clone(), [a]);
      for (let j = 0; j < i; j++) {
        const b = vertices[j],
          edge = b.clone().sub(a);
        if (edge.lengthSq() > 1e-12) {
          const weight = Math.min(
            1,
            Math.max(0, -a.dot(edge) / edge.lengthSq())
          );
          consider(a.clone().addScaledVector(edge, weight), [a, b]);
        }
        for (let k = 0; k < j; k++) {
          const c = vertices[k];
          if (edge.clone().cross(c.clone().sub(a)).lengthSq() < 1e-16) continue;
          const triangle = new Triangle(a, b, c);
          const point = triangle.closestPointToPoint(origin, new Vector3());
          const weights = triangle.getBarycoord(point, new Vector3())!;
          consider(
            point,
            [a, b, c].filter((_, index) => weights.getComponent(index) > 1e-10)
          );
        }
      }
    }
    center.copy(closest);
    support = nextSupport;
    if (center.lengthSq() < 1e-8) return null;
  }
  const facing = center.normalize();
  return points.every((point) => point.dot(facing) * 28 >= 4.04)
    ? facing
    : null;
}
