interface Props {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
}

function safeCoordinates(latitude: number, longitude: number) {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90) return null;
  const normalizedLongitude = ((((longitude + 180) % 360) + 360) % 360) - 180;
  return { latitude, longitude: normalizedLongitude };
}

export function CurrentPositionMap({ latitude, longitude }: Props) {
  const position =
    latitude === null ||
    latitude === undefined ||
    longitude === null ||
    longitude === undefined
      ? null
      : safeCoordinates(latitude, longitude);
  if (!position) return <p>Position unavailable</p>;

  const x = ((position.longitude + 180) / 360) * 360;
  const y = ((90 - position.latitude) / 180) * 180;
  const alternative = `Current position: ${position.latitude.toFixed(4)}, ${position.longitude.toFixed(4)}`;

  return (
    <figure className="current-position-map">
      <svg
        viewBox="0 0 360 180"
        role="img"
        aria-label={alternative}
        preserveAspectRatio="xMidYMid meet"
      >
        <rect width="360" height="180" className="map-ocean" />
        <path d="M0 90H360M180 0V180" className="map-gridline" />
        <circle cx={x} cy={y} r="5" className="map-position" />
      </svg>
      <figcaption>{alternative}</figcaption>
    </figure>
  );
}
