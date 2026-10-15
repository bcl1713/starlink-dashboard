const degreesToRadians = Math.PI / 180;

export function globePosition(
  latitude: number,
  longitude: number,
  radius: number
): [number, number, number] {
  const latitudeRadians = latitude * degreesToRadians;
  const longitudeRadians = longitude * degreesToRadians;

  return [
    radius * Math.cos(latitudeRadians) * Math.cos(longitudeRadians),
    radius * Math.sin(latitudeRadians),
    -radius * Math.cos(latitudeRadians) * Math.sin(longitudeRadians),
  ];
}
