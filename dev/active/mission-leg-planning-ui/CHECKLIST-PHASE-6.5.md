# Checklist for Phase 6.5: Missing Features & Polish

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Status:** In Progress
**Skill:** executing-plan-checklist

> This checklist is intentionally extremely detailed and assumes the executor
> has no prior knowledge of the repo or codebase. Every step must be followed
> exactly, in order, without combining or skipping.

---

## Navigation Improvements

### 1.1: Add "Back to Mission" button to LegDetailPage

- [ ] Open `frontend/mission-planner/src/pages/LegDetailPage.tsx`
- [ ] Import `useNavigate` from react-router-dom if not already imported:

  ```typescript
  import { useNavigate } from 'react-router-dom';
  ```

- [ ] Add navigate hook at top of component:

  ```typescript
  const navigate = useNavigate();
  ```

- [ ] Locate the page header section (likely contains the leg name/title)
- [ ] Add a "Back to Mission" button before the leg title:

  ```typescript
  <Button
    variant="ghost"
    onClick={() => navigate(`/missions/${missionId}`)}
    className="mb-4"
  >
    ← Back to Mission
  </Button>
  ```

- [ ] Ensure `missionId` is available (from URL params or leg data)
- [ ] Save the file
- [ ] Expected: Button appears at top of leg detail page

### 1.2: Test navigation flow

- [ ] Start frontend dev server:

  ```bash
  cd frontend/mission-planner
  npm run dev
  ```

- [ ] Open browser to http://localhost:5173/missions
- [ ] Click on a mission to open mission detail page
- [ ] Click on a leg to open leg detail page
- [ ] Click "Back to Mission" button
- [ ] Expected: Navigate back to mission detail page
- [ ] Expected: No errors in browser console

### 1.3: Handle unsaved changes warning (optional enhancement)

- [ ] In LegDetailPage, add state to track if form is dirty:

  ```typescript
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  ```

- [ ] Update form onChange handlers to set `hasUnsavedChanges` to true
- [ ] Add confirmation before navigation if changes exist:

  ```typescript
  const handleBackClick = () => {
    if (hasUnsavedChanges) {
      if (window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
        navigate(`/missions/${missionId}`);
      }
    } else {
      navigate(`/missions/${missionId}`);
    }
  };
  ```

- [ ] Update button onClick to use `handleBackClick`
- [ ] Save the file

### 1.4: Commit navigation improvements

- [ ] Stage changes:

  ```bash
  git add frontend/mission-planner/src/pages/LegDetailPage.tsx
  ```

- [ ] Commit:

  ```bash
  git commit -m "feat: add Back to Mission button on leg detail page

  - Add navigation button to return to mission detail
  - Add unsaved changes warning
  - Improve UX for multi-page workflow

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push:

  ```bash
  git push origin feat/mission-leg-planning-ui
  ```

---

## Map Visualization Fixes

### 2.1: Fix X-Band transition rendering (segments → point markers)

- [ ] Open `frontend/mission-planner/src/components/common/RouteMap.tsx`
- [ ] Locate where X-Band transitions are rendered
- [ ] Check if transitions are being rendered as LineString (segments) or Point (markers)
- [ ] If rendered as segments, change to point markers:

  ```typescript
  // Remove segment rendering
  // Add point marker rendering
  {xbandTransitions.map((transition, idx) => (
    <Marker
      key={`xband-${idx}`}
      position={[transition.latitude, transition.longitude]}
      icon={createXBandIcon()}
    >
      <Popup>
        X-Band Transition to {transition.satellite_id}
      </Popup>
    </Marker>
  ))}
  ```

- [ ] Create icon function if needed:

  ```typescript
  const createXBandIcon = () => {
    return L.divIcon({
      className: 'xband-marker',
      html: '<div class="w-4 h-4 bg-blue-500 rounded-full border-2 border-white"></div>',
      iconSize: [16, 16],
    });
  };
  ```

- [ ] Save the file
- [ ] Test in browser and verify transitions show as points, not lines

### 2.2: Fix map display on page refresh

- [ ] Open `frontend/mission-planner/src/components/common/RouteMap.tsx`
- [ ] Check if route data is loaded in useEffect hook
- [ ] Add defensive checks for route data:

  ```typescript
  useEffect(() => {
    if (!route || !route.points || route.points.length === 0) {
      return; // Don't render if no route data
    }
    // ... render map
  }, [route]);
  ```

- [ ] Check if map bounds are set correctly:

  ```typescript
  useEffect(() => {
    if (mapRef.current && route && route.points.length > 0) {
      const bounds = L.latLngBounds(route.points.map(p => [p.lat, p.lon]));
      mapRef.current.fitBounds(bounds);
    }
  }, [route]);
  ```

- [ ] Save the file
- [ ] Test: Refresh page while on leg detail page
- [ ] Expected: Map renders correctly with route visible

### 2.3: Add AAR segment visualization

- [ ] Open `frontend/mission-planner/src/components/common/RouteMap.tsx`
- [ ] Add props for AAR segments:

  ```typescript
  interface RouteMapProps {
    route: Route;
    xbandTransitions?: XBandTransition[];
    aarSegments?: AARSegment[]; // NEW
  }
  ```

- [ ] Add AAR segment rendering logic:

  ```typescript
  {aarSegments?.map((segment, idx) => {
    // Find waypoints by index or name
    const startPoint = route.points.find(p => p.name === segment.start_waypoint);
    const endPoint = route.points.find(p => p.name === segment.end_waypoint);

    if (!startPoint || !endPoint) return null;

    // Get route points between start and end
    const segmentPoints = getRoutePointsBetween(route.points, startPoint, endPoint);

    return (
      <Polyline
        key={`aar-${idx}`}
        positions={segmentPoints.map(p => [p.lat, p.lon])}
        color="green"
        weight={6}
        opacity={0.6}
      >
        <Popup>
          AAR Segment: {segment.start_waypoint} → {segment.end_waypoint}
        </Popup>
      </Polyline>
    );
  })}
  ```

- [ ] Add helper function:

  ```typescript
  const getRoutePointsBetween = (points: Point[], start: Point, end: Point): Point[] => {
    const startIdx = points.findIndex(p => p.name === start.name);
    const endIdx = points.findIndex(p => p.name === end.name);
    return points.slice(startIdx, endIdx + 1);
  };
  ```

- [ ] Save the file
- [ ] Update LegDetailPage to pass aarSegments prop

### 2.4: Add Ka outage visualization

- [ ] In RouteMap.tsx, add props for Ka outages:

  ```typescript
  kaOutages?: KaOutage[];
  ```

- [ ] Add Ka outage markers:

  ```typescript
  {kaOutages?.map((outage, idx) => {
    // Ka outages are time-based, not location-based
    // Show as time overlay on route or info panel
    return (
      <div key={`ka-${idx}`} className="ka-outage-indicator">
        Ka Outage: {outage.start_time} ({outage.duration_seconds}s)
      </div>
    );
  })}
  ```

- [ ] Consider alternative: Add timeline component below map
- [ ] Save the file

### 2.5: Add Ku outage visualization

- [ ] In RouteMap.tsx, add props for Ku outages:

  ```typescript
  kuOutages?: KuOutageOverride[];
  ```

- [ ] Add Ku outage markers (similar to Ka):

  ```typescript
  {kuOutages?.map((outage, idx) => {
    return (
      <div key={`ku-${idx}`} className="ku-outage-indicator">
        Ku Outage: {outage.start_time} ({outage.duration_seconds}s)
        {outage.reason && ` - ${outage.reason}`}
      </div>
    );
  })}
  ```

- [ ] Save the file

### 2.6: Add auto-calculated Ka transitions

- [ ] This requires backend calculation based on CommKa.kmz coverage
- [ ] Check if backend already calculates Ka transitions
- [ ] If not, add calculation logic to backend mission builder
- [ ] Add Ka transitions to API response
- [ ] Update frontend types to include Ka transitions
- [ ] Render Ka transitions on map (similar to X-Band but different color)
- [ ] Save changes

### 2.7: Commit map visualization fixes

- [ ] Stage all map-related changes
- [ ] Commit:

  ```bash
  git commit -m "feat: add comprehensive map visualizations

  - Fix X-Band transitions to show as point markers
  - Fix map initialization on page refresh
  - Add AAR segment overlays (green polylines)
  - Add Ka outage indicators
  - Add Ku outage indicators with reasons
  - Add auto-calculated Ka transition markers

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push changes

---

## Satellite Manager

### 3.1: Create satellite manager page component

- [ ] Create new file: `frontend/mission-planner/src/pages/SatelliteManagerPage.tsx`
- [ ] Add basic page structure:

  ```typescript
  import { useState } from 'react';
  import { Button } from '@/components/ui/button';

  export default function SatelliteManagerPage() {
    const [satellites, setSatellites] = useState<Satellite[]>([]);

    return (
      <div className="container mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Satellite Manager</h1>
        <Button onClick={() => {/* Open create dialog */}}>
          Add Satellite
        </Button>
        {/* Satellite list will go here */}
      </div>
    );
  }
  ```

- [ ] Save the file

### 3.2: Create Satellite type definition

- [ ] Open or create `frontend/mission-planner/src/types/satellite.ts`
- [ ] Add Satellite interface if not exists:

  ```typescript
  export interface Satellite {
    id: string;
    name: string;
    type: 'X-Band' | 'Ka-Band' | 'Ku-Band';
    description?: string;
    created_at?: string;
  }
  ```

- [ ] Save the file

### 3.3: Create satellite API service

- [ ] Create `frontend/mission-planner/src/services/satellites.ts`
- [ ] Add CRUD functions:

  ```typescript
  import apiClient from './api-client';
  import type { Satellite } from '@/types/satellite';

  export const satelliteService = {
    async getAll(): Promise<Satellite[]> {
      const response = await apiClient.get('/satellites');
      return response.data;
    },

    async create(satellite: Omit<Satellite, 'id'>): Promise<Satellite> {
      const response = await apiClient.post('/satellites', satellite);
      return response.data;
    },

    async update(id: string, satellite: Partial<Satellite>): Promise<Satellite> {
      const response = await apiClient.put(`/satellites/${id}`, satellite);
      return response.data;
    },

    async delete(id: string): Promise<void> {
      await apiClient.delete(`/satellites/${id}`);
    },
  };
  ```

- [ ] Save the file

### 3.4: Create satellite manager hooks

- [ ] Create `frontend/mission-planner/src/hooks/api/useSatellites.ts`
- [ ] Add React Query hooks:

  ```typescript
  import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
  import { satelliteService } from '@/services/satellites';

  export const useSatellites = () => {
    return useQuery({
      queryKey: ['satellites'],
      queryFn: satelliteService.getAll,
    });
  };

  export const useCreateSatellite = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: satelliteService.create,
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['satellites'] });
      },
    });
  };

  export const useUpdateSatellite = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: ({ id, data }: { id: string; data: any }) =>
        satelliteService.update(id, data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['satellites'] });
      },
    });
  };

  export const useDeleteSatellite = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: satelliteService.delete,
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['satellites'] });
      },
    });
  };
  ```

- [ ] Save the file

### 3.5: Implement satellite list view

- [ ] Open `frontend/mission-planner/src/pages/SatelliteManagerPage.tsx`
- [ ] Add satellite list rendering:

  ```typescript
  const { data: satellites, isLoading } = useSatellites();

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Satellite Manager</h1>
      <Button onClick={() => setShowCreateDialog(true)}>
        Add Satellite
      </Button>

      {isLoading && <p>Loading satellites...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {satellites?.map(satellite => (
          <Card key={satellite.id}>
            <CardHeader>
              <CardTitle>{satellite.name}</CardTitle>
              <CardDescription>{satellite.type}</CardDescription>
            </CardHeader>
            <CardContent>
              <p>{satellite.description}</p>
            </CardContent>
            <CardFooter>
              <Button variant="outline" onClick={() => handleEdit(satellite)}>
                Edit
              </Button>
              <Button variant="destructive" onClick={() => handleDelete(satellite.id)}>
                Delete
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
  ```

- [ ] Save the file

### 3.6: Create AddSatelliteDialog component

- [ ] Create `frontend/mission-planner/src/components/satellites/AddSatelliteDialog.tsx`
- [ ] Implement dialog with form for satellite creation
- [ ] Add fields: name, type (dropdown), description
- [ ] Wire up to useCreateSatellite hook
- [ ] Save the file

### 3.7: Add satellite manager to routing

- [ ] Open `frontend/mission-planner/src/App.tsx`
- [ ] Add route for satellite manager:

  ```typescript
  import SatelliteManagerPage from './pages/SatelliteManagerPage';

  // In routes:
  <Route path="/satellites" element={<SatelliteManagerPage />} />
  ```

- [ ] Save the file

### 3.8: Add navigation link from home page

- [ ] Open main navigation component (likely in App.tsx or a Layout component)
- [ ] Add link to satellite manager:

  ```typescript
  <Link to="/satellites">Satellites</Link>
  ```

- [ ] Save the file

### 3.9: Add "Manage Satellites" link from leg editor

- [ ] Open `frontend/mission-planner/src/pages/LegDetailPage.tsx`
- [ ] Add link near satellite configuration section:

  ```typescript
  <Link to="/satellites" className="text-sm text-blue-600">
    Manage Satellites →
  </Link>
  ```

- [ ] Save the file

### 3.10: Commit satellite manager

- [ ] Stage all satellite manager files
- [ ] Commit:

  ```bash
  git commit -m "feat: add satellite manager page with CRUD operations

  - Create SatelliteManagerPage with list view
  - Add satellite API service and React Query hooks
  - Add AddSatelliteDialog for creating satellites
  - Add navigation links from home page and leg editor
  - Enable users to manage satellite catalog

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push changes

---

## Leg Activation

### 4.1: Add activate leg button to mission detail page

- [ ] Open `frontend/mission-planner/src/pages/MissionDetailPage.tsx`
- [ ] Locate leg list/cards section
- [ ] Add "Activate" button to each leg card:

  ```typescript
  <Button
    onClick={() => handleActivateLeg(leg.id)}
    variant={leg.is_active ? "default" : "outline"}
  >
    {leg.is_active ? "Active" : "Activate"}
  </Button>
  ```

- [ ] Save the file

### 4.2: Check if backend activation endpoint exists

- [ ] Check `backend/starlink-location/app/mission/routes_v2.py`
- [ ] Look for activation endpoint like `POST /api/v2/missions/{id}/legs/{leg_id}/activate`
- [ ] If missing, add endpoint:

  ```python
  @router.post("/{mission_id}/legs/{leg_id}/activate")
  async def activate_leg(mission_id: str, leg_id: str):
      """Activate a specific leg (deactivates others)."""
      # Load mission
      # Set all legs active=False
      # Set target leg active=True
      # Save mission
      # Return success
  ```

- [ ] Save backend file if modified

### 4.3: Add activation API call to frontend

- [ ] Open `frontend/mission-planner/src/services/missions.ts`
- [ ] Add activate function:

  ```typescript
  async activateLeg(missionId: string, legId: string): Promise<void> {
    await apiClient.post(`/api/v2/missions/${missionId}/legs/${legId}/activate`);
  }
  ```

- [ ] Save the file

### 4.4: Create useActivateLeg hook

- [ ] Open `frontend/mission-planner/src/hooks/api/useMissions.ts`
- [ ] Add mutation hook:

  ```typescript
  export const useActivateLeg = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: ({ missionId, legId }: { missionId: string; legId: string }) =>
        missionService.activateLeg(missionId, legId),
      onSuccess: (_, variables) => {
        queryClient.invalidateQueries({ queryKey: ['missions', variables.missionId] });
      },
    });
  };
  ```

- [ ] Save the file

### 4.5: Wire up activation in MissionDetailPage

- [ ] Open `frontend/mission-planner/src/pages/MissionDetailPage.tsx`
- [ ] Add hook:

  ```typescript
  const activateLeg = useActivateLeg();
  ```

- [ ] Implement handler:

  ```typescript
  const handleActivateLeg = (legId: string) => {
    activateLeg.mutate({ missionId: mission.id, legId });
  };
  ```

- [ ] Save the file

### 4.6: Add active leg indicator

- [ ] In MissionDetailPage, update leg card to show active status:

  ```typescript
  {leg.is_active && (
    <Badge variant="success">Active</Badge>
  )}
  ```

- [ ] Add visual styling for active leg (border, background color, etc.)
- [ ] Save the file

### 4.7: Test leg activation

- [ ] Start dev servers (frontend and backend)
- [ ] Navigate to mission detail page
- [ ] Click "Activate" on a leg
- [ ] Verify leg shows as active
- [ ] Verify other legs are deactivated
- [ ] Check backend data to confirm activation persisted

### 4.8: Commit leg activation

- [ ] Stage all activation-related files
- [ ] Commit:

  ```bash
  git commit -m "feat: add leg activation functionality

  - Add Activate button to mission detail page
  - Add backend activation endpoint (if missing)
  - Add activation API service and hook
  - Show active leg indicator with badge
  - Ensure only one leg active at a time

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push changes

---

## Complete Export Package

### 5.1: Update backend export package structure

- [ ] Open `backend/starlink-location/app/mission/package_exporter.py`
- [ ] Review current export structure
- [ ] Plan directory structure:

  ```
  mission-{id}.zip
  ├── mission.json
  ├── manifest.json
  ├── legs/
  │   ├── {leg-id-1}.json
  │   └── {leg-id-2}.json
  ├── routes/
  │   ├── {route-id-1}.kml
  │   └── {route-id-2}.kml
  ├── exports/
  │   ├── mission/
  │   │   ├── mission-timeline.csv
  │   │   ├── mission-timeline.xlsx
  │   │   ├── mission-slides.pptx
  │   │   └── mission-report.pdf
  │   └── legs/
  │       ├── {leg-id-1}/
  │       │   ├── timeline.csv
  │       │   ├── timeline.xlsx
  │       │   ├── slides.pptx
  │       │   └── report.pdf
  │       └── {leg-id-2}/
  │           ├── timeline.csv
  │           ├── timeline.xlsx
  │           ├── slides.pptx
  │           └── report.pdf
  ```

- [ ] Document structure in comments

### 5.2: Generate per-leg CSV exports

- [ ] In package_exporter.py, locate export loop for legs
- [ ] For each leg, generate CSV:

  ```python
  for leg in mission.legs:
      csv_export = generate_timeline_export(
          leg_id=leg.id,
          format=TimelineExportFormat.CSV
      )
      zf.writestr(f"exports/legs/{leg.id}/timeline.csv", csv_export)
  ```

- [ ] Verify generate_timeline_export exists in exporter.py
- [ ] Save the file

### 5.3: Generate per-leg XLS exports

- [ ] Add XLSX export for each leg:

  ```python
  for leg in mission.legs:
      xlsx_export = generate_timeline_export(
          leg_id=leg.id,
          format=TimelineExportFormat.XLSX
      )
      zf.writestr(f"exports/legs/{leg.id}/timeline.xlsx", xlsx_export)
  ```

- [ ] Save the file

### 5.4: Generate per-leg PPT exports

- [ ] Add PPTX export for each leg:

  ```python
  for leg in mission.legs:
      pptx_export = generate_timeline_export(
          leg_id=leg.id,
          format=TimelineExportFormat.PPTX
      )
      zf.writestr(f"exports/legs/{leg.id}/slides.pptx", pptx_export)
  ```

- [ ] Save the file

### 5.5: Generate per-leg PDF exports

- [ ] Add PDF export for each leg:

  ```python
  for leg in mission.legs:
      pdf_export = generate_timeline_export(
          leg_id=leg.id,
          format=TimelineExportFormat.PDF
      )
      zf.writestr(f"exports/legs/{leg.id}/report.pdf", pdf_export)
  ```

- [ ] Save the file

### 5.6: Generate combined mission CSV export

- [ ] Add function to generate combined timeline:

  ```python
  def generate_mission_timeline_csv(mission: Mission) -> bytes:
      """Generate combined CSV for all legs in mission."""
      # Combine all leg timelines into single CSV
      # Add mission-level header
      # Include leg boundaries/transitions
      pass
  ```

- [ ] Call in export function:

  ```python
  mission_csv = generate_mission_timeline_csv(mission)
  zf.writestr("exports/mission/mission-timeline.csv", mission_csv)
  ```

- [ ] Save the file

### 5.7: Generate combined mission XLS export

- [ ] Add function:

  ```python
  def generate_mission_timeline_xlsx(mission: Mission) -> bytes:
      """Generate combined XLSX for all legs in mission."""
      # Create workbook with multiple sheets
      # One sheet per leg + summary sheet
      pass
  ```

- [ ] Call in export:

  ```python
  mission_xlsx = generate_mission_timeline_xlsx(mission)
  zf.writestr("exports/mission/mission-timeline.xlsx", mission_xlsx)
  ```

- [ ] Save the file

### 5.8: Generate combined mission PPT export

- [ ] Add function:

  ```python
  def generate_mission_slides_pptx(mission: Mission) -> bytes:
      """Generate combined PPTX for all legs in mission."""
      # Create presentation with mission overview
      # Add slides for each leg
      # Include summary/conclusion
      pass
  ```

- [ ] Call in export:

  ```python
  mission_pptx = generate_mission_slides_pptx(mission)
  zf.writestr("exports/mission/mission-slides.pptx", mission_pptx)
  ```

- [ ] Save the file

### 5.9: Generate combined mission PDF export

- [ ] Add function:

  ```python
  def generate_mission_report_pdf(mission: Mission) -> bytes:
      """Generate combined PDF report for entire mission."""
      # Create PDF with mission overview
      # Include timeline for each leg
      # Add maps, charts, summary
      pass
  ```

- [ ] Call in export:

  ```python
  mission_pdf = generate_mission_report_pdf(mission)
  zf.writestr("exports/mission/mission-report.pdf", mission_pdf)
  ```

- [ ] Save the file

### 5.10: Update manifest to list all files

- [ ] In package_exporter.py, update manifest creation:

  ```python
  manifest = {
      "version": "1.0",
      "mission_id": mission.id,
      "mission_name": mission.name,
      "leg_count": len(mission.legs),
      "exported_at": datetime.now(timezone.utc).isoformat(),
      "included_files": {
          "mission_data": ["mission.json", "manifest.json"],
          "legs": [f"legs/{leg.id}.json" for leg in mission.legs],
          "routes": [...],
          "per_leg_exports": [...],
          "mission_exports": [
              "exports/mission/mission-timeline.csv",
              "exports/mission/mission-timeline.xlsx",
              "exports/mission/mission-slides.pptx",
              "exports/mission/mission-report.pdf",
          ],
      },
  }
  ```

- [ ] Save the file

### 5.11: Test export with multi-leg mission

- [ ] Rebuild backend Docker container:

  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  ```

- [ ] Create test mission with 2+ legs
- [ ] Export mission:

  ```bash
  curl -X POST http://localhost:8000/api/v2/missions/test-export/export \
    -o /tmp/test-export.zip
  ```

- [ ] Verify zip contents:

  ```bash
  unzip -l /tmp/test-export.zip
  ```

- [ ] Expected: See all per-leg exports + mission-level exports
- [ ] Open some files to verify they're valid (not corrupted)

### 5.12: Commit export package implementation

- [ ] Stage all export-related files
- [ ] Commit:

  ```bash
  git commit -m "feat: implement complete export package with per-leg and mission-level files

  - Generate CSV, XLS, PPT, PDF for each leg
  - Generate combined CSV, XLS, PPT, PDF for entire mission
  - Update package structure with exports/ directory
  - Update manifest to list all included files
  - Test with multi-leg mission export

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push changes

---

## Cascade Deletion

### 6.1: Update DELETE mission endpoint for cascade

- [ ] Open `backend/starlink-location/app/mission/routes_v2.py`
- [ ] Locate DELETE mission endpoint
- [ ] Update to cascade delete legs:

  ```python
  @router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
  async def delete_mission(mission_id: str):
      """Delete mission and all associated legs."""
      mission = load_mission_v2(mission_id)

      if not mission:
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail=f"Mission {mission_id} not found"
          )

      # Delete all legs first
      for leg in mission.legs:
          # Delete leg routes
          if leg.route_id:
              delete_route(leg.route_id)  # From route manager

          # Delete leg POIs
          delete_leg_pois(mission_id, leg.id)  # Helper function

      # Delete mission directory (includes all legs)
      mission_dir = get_mission_path(mission_id)
      shutil.rmtree(mission_dir)

      logger.info(f"Deleted mission {mission_id} with {len(mission.legs)} legs")
  ```

- [ ] Save the file

### 6.2: Update DELETE leg endpoint for cascade

- [ ] In routes_v2.py, add or update DELETE leg endpoint:

  ```python
  @router.delete("/{mission_id}/legs/{leg_id}", status_code=status.HTTP_204_NO_CONTENT)
  async def delete_leg(mission_id: str, leg_id: str):
      """Delete leg and all associated routes and POIs."""
      mission = load_mission_v2(mission_id)

      if not mission:
          raise HTTPException(status_code=404, detail="Mission not found")

      leg = next((l for l in mission.legs if l.id == leg_id), None)

      if not leg:
          raise HTTPException(status_code=404, detail="Leg not found")

      # Delete associated route
      if leg.route_id:
          delete_route(leg.route_id)
          logger.info(f"Deleted route {leg.route_id} for leg {leg_id}")

      # Delete associated POIs
      delete_leg_pois(mission_id, leg_id)
      logger.info(f"Deleted POIs for leg {leg_id}")

      # Remove leg from mission
      mission.legs = [l for l in mission.legs if l.id != leg_id]

      # Save updated mission
      save_mission_v2(mission)

      logger.info(f"Deleted leg {leg_id} from mission {mission_id}")
  ```

- [ ] Save the file

### 6.3: Add helper function to delete leg POIs

- [ ] In routes_v2.py or a separate utils file:

  ```python
  def delete_leg_pois(mission_id: str, leg_id: str) -> None:
      """Delete all POIs associated with a leg."""
      # Load POI manager
      # Filter POIs by leg_id metadata
      # Delete matching POIs
      pass
  ```

- [ ] Save the file

### 6.4: Add transaction/rollback support

- [ ] Wrap deletion logic in try/except:

  ```python
  @router.delete("/{mission_id}")
  async def delete_mission(mission_id: str):
      try:
          # Deletion logic here
          pass
      except Exception as e:
          logger.error(f"Failed to delete mission {mission_id}: {e}")
          # Attempt rollback if possible
          raise HTTPException(
              status_code=500,
              detail="Failed to delete mission. Some data may remain."
          )
  ```

- [ ] Save the file

### 6.5: Test mission cascade delete

- [ ] Create test mission with 2 legs
- [ ] Add routes to both legs
- [ ] Add POIs to both legs
- [ ] Delete mission:

  ```bash
  curl -X DELETE http://localhost:8000/api/v2/missions/test-cascade
  ```

- [ ] Verify mission directory deleted
- [ ] Verify routes deleted
- [ ] Verify POIs deleted
- [ ] Expected: All associated data removed

### 6.6: Test leg cascade delete

- [ ] Create test mission with 2 legs
- [ ] Add route and POIs to first leg
- [ ] Delete first leg:

  ```bash
  curl -X DELETE http://localhost:8000/api/v2/missions/test-mission/legs/leg-1
  ```

- [ ] Verify leg removed from mission
- [ ] Verify route deleted
- [ ] Verify POIs deleted
- [ ] Expected: Second leg still intact

### 6.7: Add frontend confirmation dialog for mission delete

- [ ] Open `frontend/mission-planner/src/pages/MissionDetailPage.tsx` or wherever delete is triggered
- [ ] Update delete handler to show confirmation:

  ```typescript
  const handleDeleteMission = async () => {
    const legCount = mission.legs.length;
    const confirmed = window.confirm(
      `Are you sure you want to delete this mission?\n\n` +
      `This will permanently delete:\n` +
      `- ${legCount} leg(s)\n` +
      `- All associated routes\n` +
      `- All associated POIs\n\n` +
      `This action cannot be undone.`
    );

    if (confirmed) {
      await deleteMission.mutateAsync(mission.id);
      navigate('/missions');
    }
  };
  ```

- [ ] Save the file

### 6.8: Add frontend confirmation dialog for leg delete

- [ ] In MissionDetailPage, update leg delete handler:

  ```typescript
  const handleDeleteLeg = async (leg: MissionLeg) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete leg "${leg.name}"?\n\n` +
      `This will permanently delete:\n` +
      `- The leg configuration\n` +
      `- Associated route (${leg.route_id})\n` +
      `- All associated POIs\n\n` +
      `This action cannot be undone.`
    );

    if (confirmed) {
      await deleteLeg.mutateAsync({ missionId: mission.id, legId: leg.id });
    }
  };
  ```

- [ ] Save the file

### 6.9: Create custom confirmation dialog component (optional)

- [ ] Create `frontend/mission-planner/src/components/common/DeleteConfirmDialog.tsx`
- [ ] Build reusable confirmation dialog with checkbox:

  ```typescript
  interface DeleteConfirmDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    itemsToDelete: string[];
    onConfirm: () => void;
  }

  export function DeleteConfirmDialog({ ... }: DeleteConfirmDialogProps) {
    const [confirmed, setConfirmed] = useState(false);

    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div>
            <p>This will permanently delete:</p>
            <ul>
              {itemsToDelete.map((item, idx) => (
                <li key={idx}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              checked={confirmed}
              onCheckedChange={setConfirmed}
            />
            <label>I understand this action cannot be undone</label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!confirmed}
              onClick={onConfirm}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }
  ```

- [ ] Save the file

### 6.10: Commit cascade deletion implementation

- [ ] Stage all deletion-related files
- [ ] Commit:

  ```bash
  git commit -m "feat: implement cascade deletion for missions and legs

  - Update DELETE mission endpoint to cascade delete all legs
  - Update DELETE leg endpoint to cascade delete routes and POIs
  - Add helper function for deleting leg POIs
  - Add transaction/rollback support for safe deletion
  - Add frontend confirmation dialogs with detailed warnings
  - Show exactly what will be deleted before confirming
  - Test cascade deletion for missions and legs

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 6.5"
  ```

- [ ] Push changes

---

## Final Phase 6.5 Verification

- [ ] Review all Phase 6.5 exit criteria from PLAN.md
- [ ] Test each feature end-to-end:
  - [ ] Navigation from leg detail back to mission detail
  - [ ] X-Band transitions show as markers on map
  - [ ] Map loads correctly after page refresh
  - [ ] AAR segments visible on map
  - [ ] Ka/Ku outages visible on map
  - [ ] Satellite manager accessible and functional
  - [ ] Leg activation works and shows indicator
  - [ ] Export includes all per-leg files
  - [ ] Export includes all mission-level files
  - [ ] Mission cascade delete removes all data
  - [ ] Leg cascade delete removes routes/POIs
- [ ] Fix any bugs found during testing
- [ ] Update PLAN.md status to "Phase 6.5 Complete"
- [ ] Update HANDOFF.md with Phase 6.5 summary
- [ ] Ready for Phase 7 (Testing & Documentation)
