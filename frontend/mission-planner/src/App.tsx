import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { MissionsPage } from './pages/MissionsPage';
import { MissionDetailPage } from './pages/MissionDetailPage';
import { LegDetailPage } from './pages/LegDetailPage';
import SatelliteManagerPage from './pages/SatelliteManagerPage';
import { RouteManagerPage } from './pages/RouteManagerPage';
import { POIManagerPage } from './pages/POIManagerPage';
import { DataExportPage } from './pages/DataExportPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <nav className="bg-gray-800 text-white p-4 mb-6">
          <div className="container mx-auto flex gap-6">
            <Link to="/missions" className="hover:underline">
              Missions
            </Link>
            <Link to="/satellites" className="hover:underline">
              Satellites
            </Link>
            <Link to="/pois" className="hover:underline">
              POIs
            </Link>
            <Link to="/routes" className="hover:underline">
              Routes
            </Link>
            <Link to="/export" className="hover:underline">
              Data Export
            </Link>
          </div>
        </nav>
        <Routes>
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
          <Route path="/" element={<Navigate to="/missions" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
