interface StatusWithPosition {
  position: {
    latitude: number;
    longitude: number;
  };
}

export function projectAircraftPosition(status: StatusWithPosition) {
  return {
    latitude: status.position.latitude,
    longitude: status.position.longitude,
  };
}
