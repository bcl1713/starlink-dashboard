import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MissionsPage } from './pages/MissionsPage';
import { LegDetailPage } from './pages/LegDetailPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/missions" element={<MissionsPage />} />
          <Route path="/missions/:missionId/legs/:legId" element={<LegDetailPage />} />
          <Route path="/" element={<Navigate to="/missions" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
