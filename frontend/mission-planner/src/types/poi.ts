export interface POICreate {
  name: string;
  latitude: number;
  longitude: number;
  icon: string;
  category?: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
}

export interface POIUpdate {
  name?: string;
  latitude?: number;
  longitude?: number;
  icon?: string;
  category?: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
}

export interface POIWithETA {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  icon: string;
  category: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  eta?: string;
  bearing?: number;
  course_status?: 'ahead_on_route' | 'already_passed' | 'not_on_route';
}
