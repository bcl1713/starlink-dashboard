export interface GPSConfig {
  enabled: boolean;
  ready: boolean;
  satellites: number;
}

export interface GPSConfigUpdate {
  enabled: boolean;
}

export interface GPSError {
  type: 'permission_denied' | 'unavailable' | 'unknown';
  message: string;
}
