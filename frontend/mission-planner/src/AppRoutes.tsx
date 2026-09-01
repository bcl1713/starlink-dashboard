import { Navigate, Route, Routes } from 'react-router-dom';

import { ConfigurationPage } from './pages/ConfigurationPage';
import { DataExportPage } from './pages/DataExportPage';
import { LegDetailPage } from './pages/LegDetailPage';
import { MissionDetailPage } from './pages/MissionDetailPage';
import { MissionsPage } from './pages/MissionsPage';
import { OverviewPage } from './pages/OverviewPage';
import { POIManagerPage } from './pages/POIManagerPage';
import { RouteManagerPage } from './pages/RouteManagerPage';
import SatelliteManagerPage from './pages/SatelliteManagerPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/overview" element={<OverviewPage />} />
      <Route path="/missions" element={<MissionsPage />} />
      <Route path="/missions/:missionId" element={<MissionDetailPage />} />
      <Route
        path="/missions/:missionId/legs/:legId"
        element={<LegDetailPage />}
      />
      <Route path="/satellites" element={<SatelliteManagerPage />} />
      <Route path="/pois" element={<POIManagerPage />} />
      <Route path="/routes" element={<RouteManagerPage />} />
      <Route path="/export" element={<DataExportPage />} />
      <Route path="/configuration" element={<ConfigurationPage />} />
      <Route path="/" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
