import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  useMatch,
} from 'react-router-dom';
import { Menu, Radio } from 'lucide-react';
import { MissionsPage } from './pages/MissionsPage';
import { MissionDetailPage } from './pages/MissionDetailPage';
import { LegDetailPage } from './pages/LegDetailPage';
import SatelliteManagerPage from './pages/SatelliteManagerPage';
import { RouteManagerPage } from './pages/RouteManagerPage';
import { POIManagerPage } from './pages/POIManagerPage';
import { DataExportPage } from './pages/DataExportPage';
import { ConfigurationPage } from './pages/ConfigurationPage';
import { OverviewPage } from './pages/OverviewPage';
import { PageThemeContext } from './lib/page-theme';
import { useDocumentFullscreen } from './hooks/useDocumentFullscreen';

const queryClient = new QueryClient();

const navigationItems = [
  { to: '/missions', label: 'Missions' },
  { to: '/satellites', label: 'Satellites' },
  { to: '/pois', label: 'POIs' },
  { to: '/routes', label: 'Routes' },
  { to: '/export', label: 'Data Export' },
  { to: '/configuration', label: 'Configuration' },
  { to: '/overview', label: 'Overview' },
];

function AppNavigation() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav
      className="dark border-b bg-card text-foreground"
      aria-label="Primary navigation"
    >
      <div className="mx-auto flex min-h-16 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <NavLink
          to="/missions"
          className="flex items-center gap-2 font-semibold tracking-tight text-foreground"
          onClick={() => setIsOpen(false)}
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Radio className="size-4" aria-hidden="true" />
          </span>
          Mission Planner
        </NavLink>
        <button
          type="button"
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-input text-foreground md:hidden"
          aria-label="Toggle navigation"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((open) => !open)}
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>
        <div className="hidden items-center gap-1 md:flex">
          {navigationItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </div>
      {isOpen && (
        <div className="border-t bg-card px-4 py-2 md:hidden">
          <div className="mx-auto grid max-w-[1440px] gap-1">
            {navigationItems.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setIsOpen(false)}
                className={({ isActive }) =>
                  `min-h-11 rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive
                      ? 'bg-accent text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}

function AppShell() {
  const isFullscreen = useDocumentFullscreen();
  const isOverview = useMatch('/overview') !== null;
  const theme = isOverview ? '' : 'dark text-foreground';
  return (
    <PageThemeContext.Provider value={theme}>
      <div className="app-shell">
        {!isFullscreen && <AppNavigation />}
        <div
          className={`app-route-content ${isOverview ? '' : 'management-page dark bg-background text-foreground'}`}
        >
          <Routes>
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/missions" element={<MissionsPage />} />
            <Route
              path="/missions/:missionId"
              element={<MissionDetailPage />}
            />
            <Route
              path="/missions/:missionId/legs/:legId"
              element={<LegDetailPage />}
            />
            <Route path="/satellites" element={<SatelliteManagerPage />} />
            <Route path="/pois" element={<POIManagerPage />} />
            <Route path="/routes" element={<RouteManagerPage />} />
            <Route path="/export" element={<DataExportPage />} />
            <Route path="/configuration" element={<ConfigurationPage />} />
            <Route path="/" element={<Navigate to="/missions" replace />} />
          </Routes>
        </div>
      </div>
    </PageThemeContext.Provider>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
