interface StatusWithPosition {
  position?: {
    latitude: number;
    longitude: number;
  };
}

export function projectAircraftPosition(status: StatusWithPosition) {
  if (!status.position) {
    return null;
  }
  return {
    latitude: status.position.latitude,
    longitude: status.position.longitude,
  };
}
