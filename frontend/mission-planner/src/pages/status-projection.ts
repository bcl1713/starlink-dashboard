import type { StatusResponse } from '@/services/status';

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
