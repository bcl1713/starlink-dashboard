// @ts-expect-error Vitest runs this source ownership check in Node.
import { readFileSync } from 'node:fs';
// @ts-expect-error Vitest runs this source ownership check in Node.
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

declare const process: { cwd(): string };

const source = readFileSync(join(process.cwd(), 'src/App.tsx'), 'utf8');

describe('AppRoutes production ownership', () => {
  it('routes to production page components instead of a catch-all shell', () => {
    for (const statement of [
      "import { OverviewPage } from './pages/OverviewPage';",
      "import { MissionsPage } from './pages/MissionsPage';",
      "import { MissionDetailPage } from './pages/MissionDetailPage';",
      "import { LegDetailPage } from './pages/LegDetailPage';",
      "import SatelliteManagerPage from './pages/SatelliteManagerPage';",
      "import { RouteManagerPage } from './pages/RouteManagerPage';",
      "import { POIManagerPage } from './pages/POIManagerPage';",
      "import { DataExportPage } from './pages/DataExportPage';",
      "import { ConfigurationPage } from './pages/ConfigurationPage';",
    ]) {
      expect(source).toContain(statement);
    }
    expect(source).toContain(
      '<Route path="/overview" element={<OverviewPage />} />'
    );
    expect(source).toContain(
      '<Route path="/" element={<Navigate to="/overview" replace />} />'
    );
    expect(source).not.toContain('<Route path="*"');
  });
});
