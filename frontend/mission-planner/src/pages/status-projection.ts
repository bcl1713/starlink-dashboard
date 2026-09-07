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
  if (status.position.latitude > 90 || status.position.latitude < -90) {
    return null;
  }
  return {
    latitude: status.position.latitude,
    longitude: status.position.longitude,
  };
}
