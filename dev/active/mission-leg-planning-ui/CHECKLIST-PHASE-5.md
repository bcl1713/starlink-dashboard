# Checklist: Phase 5 - Satellite & AAR Configuration UI

**Branch:** `feat/mission-leg-planning-ui` **Folder:**
`dev/active/mission-leg-planning-ui/` **Phase:** 5 - Satellite & AAR
Configuration UI **Status:** Not Started

> This checklist covers implementing satellite transition configuration (X-Band
> manual, Ka outages, Ku outages) and AAR segment definition UI with map
> visualization.

---

## Phase 5 Overview

**Goal:** Implement satellite transition configuration (X-Band manual, Ka
outages, Ku outages) and AAR segment definition UI with map visualization.

**Exit Criteria:**

- X-Band configuration: starting satellite selector + transition table
- Ka outage windows configurable
- Ku/Starlink outage windows configurable
- AAR segment editor: waypoint-based start/end selection
- Map shows transition points and AAR segments visually
- Form validation ensures data integrity

---

## 5.1: Add Satellite Configuration Types

### 5.1.1: Create satellite types

- [x] Create `frontend/mission-planner/src/types/satellite.ts`
- [x] Add satellite configuration interfaces:

  ```typescript
  export interface XBandTransition {
    waypoint_index: number;
    waypoint_name: string;
    from_satellite: string;
    to_satellite: string;
    timestamp?: string;
  }

  export interface KaOutage {
    start_waypoint_index: number;
    end_waypoint_index: number;
    start_waypoint_name: string;
    end_waypoint_name: string;
    reason?: string;
  }

  export interface KuOutage {
    start_waypoint_index: number;
    end_waypoint_index: number;
    start_waypoint_name: string;
    end_waypoint_name: string;
    reason?: string;
  }

  export interface SatelliteConfig {
    xband_starting_satellite?: string;
    xband_transitions: XBandTransition[];
    ka_outages: KaOutage[];
    ku_outages: KuOutage[];
  }
  ```

- [x] Save file (verify < 350 lines)
- [x] Expected: Type definitions for satellite configuration

---

## 5.2: Add AAR Configuration Types

### 5.2.1: Create AAR types

- [x] Create `frontend/mission-planner/src/types/aar.ts`
- [x] Add AAR segment interface:

  ```typescript
  export interface AARSegment {
    id: string;
    name: string;
    start_waypoint_index: number;
    end_waypoint_index: number;
    start_waypoint_name: string;
    end_waypoint_name: string;
    altitude_feet?: number;
    notes?: string;
  }

  export interface AARConfig {
    segments: AARSegment[];
  }
  ```

- [x] Save file (verify < 350 lines)
- [x] Expected: Type definitions for AAR configuration

---

## 5.3: Update MissionLeg Type

### 5.3.1: Extend MissionLeg with satellite and AAR config

- [x] Open `frontend/mission-planner/src/types/mission.ts`
- [x] Import satellite and AAR types:

  ```typescript
  import { SatelliteConfig } from "./satellite";
  import { AARConfig } from "./aar";
  ```

- [x] Add fields to MissionLeg interface:

  ```typescript
  export interface MissionLeg {
    id: string;
    name: string;
    route_id?: string;
    description?: string;
    satellite_config?: SatelliteConfig;
    aar_config?: AARConfig;
    created_at: string;
    updated_at: string;
  }
  ```

- [x] Save file (verify < 350 lines)
- [x] Expected: MissionLeg supports satellite and AAR configuration

---

## 5.4: Create X-Band Configuration Component

### 5.4.1: Install additional UI components

- [x] Install Select component:

  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add select
  ```

- [x] Install Table component:

  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add table
  ```

- [x] Expected: Select and Table components available

### 5.4.2: Create XBandConfig component

- [x] Create
      `frontend/mission-planner/src/components/satellites/XBandConfig.tsx`
- [x] Implement X-Band starting satellite selector and transition table:

  ```typescript
  import { useState } from 'react';
  import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
  import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
  import { Button } from '../ui/button';
  import { Input } from '../ui/input';
  import type { XBandTransition } from '../../types/satellite';

  interface XBandConfigProps {
    startingSatellite?: string;
    transitions: XBandTransition[];
    onStartingSatelliteChange: (satellite: string) => void;
    onTransitionsChange: (transitions: XBandTransition[]) => void;
    availableSatellites: string[];
  }

  export function XBandConfig({
    startingSatellite,
    transitions,
    onStartingSatelliteChange,
    onTransitionsChange,
    availableSatellites,
  }: XBandConfigProps) {
    const [newTransition, setNewTransition] = useState<Partial<XBandTransition>>({});

    const handleAddTransition = () => {
      if (newTransition.waypoint_index !== undefined && newTransition.to_satellite) {
        onTransitionsChange([
          ...transitions,
          {
            waypoint_index: newTransition.waypoint_index,
            waypoint_name: newTransition.waypoint_name || '',
            from_satellite: transitions[transitions.length - 1]?.to_satellite || startingSatellite || '',
            to_satellite: newTransition.to_satellite,
          },
        ]);
        setNewTransition({});
      }
    };

    const handleRemoveTransition = (index: number) => {
      onTransitionsChange(transitions.filter((_, i) => i !== index));
    };

    return (
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium">Starting Satellite</label>
          <Select value={startingSatellite} onValueChange={onStartingSatelliteChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select starting satellite" />
            </SelectTrigger>
            <SelectContent>
              {availableSatellites.map((sat) => (
                <SelectItem key={sat} value={sat}>
                  {sat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <h3 className="text-sm font-medium mb-2">Transitions</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Waypoint Index</TableHead>
                <TableHead>Waypoint Name</TableHead>
                <TableHead>From Satellite</TableHead>
                <TableHead>To Satellite</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transitions.map((transition, index) => (
                <TableRow key={index}>
                  <TableCell>{transition.waypoint_index}</TableCell>
                  <TableCell>{transition.waypoint_name}</TableCell>
                  <TableCell>{transition.from_satellite}</TableCell>
                  <TableCell>{transition.to_satellite}</TableCell>
                  <TableCell>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRemoveTransition(index)}
                    >
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell>
                  <Input
                    type="number"
                    placeholder="Index"
                    value={newTransition.waypoint_index ?? ''}
                    onChange={(e) =>
                      setNewTransition({
                        ...newTransition,
                        waypoint_index: parseInt(e.target.value),
                      })
                    }
                  />
                </TableCell>
                <TableCell>
                  <Input
                    placeholder="Name"
                    value={newTransition.waypoint_name ?? ''}
                    onChange={(e) =>
                      setNewTransition({ ...newTransition, waypoint_name: e.target.value })
                    }
                  />
                </TableCell>
                <TableCell>
                  {transitions[transitions.length - 1]?.to_satellite || startingSatellite || 'N/A'}
                </TableCell>
                <TableCell>
                  <Select
                    value={newTransition.to_satellite}
                    onValueChange={(value) =>
                      setNewTransition({ ...newTransition, to_satellite: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="To satellite" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableSatellites.map((sat) => (
                        <SelectItem key={sat} value={sat}>
                          {sat}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Button onClick={handleAddTransition}>Add</Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </div>
    );
  }
  ```

- [x] Save file (verify < 350 lines)
- [x] Expected: X-Band configuration component with starting satellite and
      transitions

---

## 5.5: Create Ka Outage Configuration Component

### 5.5.1: Create KaOutageConfig component

- [x] Create
      `frontend/mission-planner/src/components/satellites/KaOutageConfig.tsx`
- [x] Implement Ka outage windows editor (similar pattern to X-Band transitions)
- [x] Save file (verify < 350 lines)
- [x] Expected: Ka outage configuration component

---

## 5.6: Create Ku/Starlink Outage Configuration Component

### 5.6.1: Create KuOutageConfig component

- [x] Create
      `frontend/mission-planner/src/components/satellites/KuOutageConfig.tsx`
- [x] Implement Ku/Starlink outage windows editor
- [x] Save file (verify < 350 lines)
- [x] Expected: Ku outage configuration component

---

## 5.7: Create AAR Segment Editor Component

### 5.7.1: Create AARSegmentEditor component

- [x] Create `frontend/mission-planner/src/components/aar/AARSegmentEditor.tsx`
- [x] Implement AAR segment editor with waypoint selection
- [x] Save file (verify < 350 lines)
- [x] Expected: AAR segment editor component

---

## 5.8: Create Leg Detail/Editor Page

### 5.8.1: Create LegDetailPage component

- [x] Create `frontend/mission-planner/src/pages/LegDetailPage.tsx`
- [x] Implement page layout with tabs for different config sections
- [x] Integrate X-Band, Ka, Ku, and AAR components
- [x] Save file (verify < 350 lines)
- [x] Expected: Leg detail page with all configuration sections

### 5.8.2: Add route to App.tsx

- [x] Open `frontend/mission-planner/src/App.tsx`
- [x] Add route for leg detail page:

  ```typescript
  <Route path="/missions/:missionId/legs/:legId" element={<LegDetailPage />} />
  ```

- [x] Save file
- [x] Expected: Leg detail page accessible via routing

---

## 5.9: Add Map Visualization (Optional for Phase 5)

### 5.9.1: Install Leaflet dependencies

- [ ] Verify Leaflet is installed:

  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner list leaflet react-leaflet
  ```

- [ ] If not installed, add:

  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner install leaflet react-leaflet
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner install -D @types/leaflet
  ```

- [ ] Expected: Leaflet ready for use

### 5.9.2: Create basic RouteMap component

- [ ] Create `frontend/mission-planner/src/components/common/RouteMap.tsx`
- [ ] Implement basic Leaflet map showing route
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Map component ready for route visualization

---

## 5.10: Test Phase 5 Components

### 5.10.1: Manual testing in browser

- [ ] Start dev server:

  ```bash
  cd /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner && npm run dev
  ```

- [ ] Navigate to mission detail page
- [ ] Test X-Band configuration:
  - [ ] Select starting satellite
  - [ ] Add transition at waypoint
  - [ ] Remove transition
- [ ] Test Ka outage configuration
- [ ] Test Ku outage configuration
- [ ] Test AAR segment editor
- [ ] Expected: All configuration UIs functional

---

## 5.11: Commit Phase 5 Changes

- [ ] Stage all changes:

  ```bash
  git add frontend/mission-planner/src/
  ```

- [ ] Commit:

  ```bash
  git commit -m "feat: implement satellite and AAR configuration UI

  - Add satellite configuration types (X-Band, Ka, Ku)
  - Add AAR segment types
  - Create XBandConfig component with transition table
  - Create KaOutageConfig and KuOutageConfig components
  - Create AARSegmentEditor component
  - Add LegDetailPage with all configuration sections
  - Add basic RouteMap component for visualization

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 5"
  ```

- [ ] Push:

  ```bash
  git push origin feat/mission-leg-planning-ui
  ```

- [ ] Expected: Phase 5 committed and pushed

---

## Status

- [ ] All Phase 5 tasks completed
- [ ] Satellite configuration UIs functional
- [ ] AAR segment editor operational
- [ ] Map visualization shows routes (basic)
