import type { StatusResponse } from '@/services/status';

export function projectGroundEntryPoint(
  status: Pick<StatusResponse, 'ground_entry_point'>
) {
  const groundEntryPoint = status.ground_entry_point;

  if (!groundEntryPoint) {
    return null;
  }

  if (!Number.isFinite(groundEntryPoint.latitude)) {
    return null;
  }

  if (!Number.isFinite(groundEntryPoint.longitude)) {
    return null;
  }

  if (
    groundEntryPoint.latitude > 90 ||
    groundEntryPoint.latitude < -90 ||
    groundEntryPoint.longitude > 180 ||
    groundEntryPoint.longitude < -180
  ) {
    return null;
  }

  return {
    latitude: groundEntryPoint.latitude,
    longitude: groundEntryPoint.longitude,
  };
}

export function projectAircraftPosition(
  status: Pick<StatusResponse, 'position'>
) {
  if (!status.position) {
    return null;
  }

  if (!Number.isFinite(status.position.latitude)) {
    return null;
  }

  if (!Number.isFinite(status.position.longitude)) {
    return null;
  }

  if (status.position.latitude > 90 || status.position.latitude < -90) {
    return null;
  }

  if (status.position.longitude > 180 || status.position.longitude < -180) {
    return null;
  }

  return {
    latitude: status.position.latitude,
    longitude: status.position.longitude,
  };
}
