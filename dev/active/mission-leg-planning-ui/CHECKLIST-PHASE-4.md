# Checklist: Phase 4 - Core UI Components

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Phase:** 4 - Core UI Components (Mission & Leg Management)
**Status:** In Progress

> This checklist covers building the mission list view, mission creation wizard,
> leg management UI, route upload, and POI management components.

---

## Phase 4 Overview

**Goal:** Build mission list view, mission creation wizard, and leg management UI. Implement route upload and POI management per leg.

**Exit Criteria:**
- Mission list view displays all missions with summary stats
- Mission creation wizard allows adding missions with multiple legs
- Each leg can have a route (KML upload) assigned
- POI management per leg functional
- Basic map visualization shows routes

---

## 4.1: Setup API Client Service

### 4.1.1: Create API client configuration

- [ ] Create `frontend/mission-planner/src/services/api-client.ts`
- [ ] Add axios instance with base URL configuration:
  ```typescript
  import axios from 'axios';

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Response interceptor for error handling
  apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
      console.error('API Error:', error.response?.data || error.message);
      return Promise.reject(error);
    }
  );
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Axios client configured with base URL and interceptors

---

## 4.2: Define TypeScript Types

### 4.2.1: Create Mission types

- [ ] Create `frontend/mission-planner/src/types/mission.ts`
- [ ] Add Mission and MissionLeg interfaces:
  ```typescript
  export interface Mission {
    id: string;
    name: string;
    description?: string;
    legs: MissionLeg[];
    created_at: string;
    updated_at: string;
    metadata: Record<string, unknown>;
  }

  export interface MissionLeg {
    id: string;
    name: string;
    route_id?: string;
    description?: string;
    created_at: string;
    updated_at: string;
  }

  export interface CreateMissionRequest {
    id: string;
    name: string;
    description?: string;
    legs?: MissionLeg[];
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Type definitions match backend models

---

## 4.3: Create Mission API Service

### 4.3.1: Implement missions service

- [ ] Create `frontend/mission-planner/src/services/missions.ts`
- [ ] Add CRUD functions:
  ```typescript
  import { apiClient } from './api-client';
  import { Mission, CreateMissionRequest } from '../types/mission';

  export const missionsApi = {
    list: async () => {
      const response = await apiClient.get<Mission[]>('/api/v2/missions');
      return response.data;
    },

    get: async (id: string) => {
      const response = await apiClient.get<Mission>(`/api/v2/missions/${id}`);
      return response.data;
    },

    create: async (mission: CreateMissionRequest) => {
      const response = await apiClient.post<Mission>('/api/v2/missions', mission);
      return response.data;
    },

    delete: async (id: string) => {
      await apiClient.delete(`/api/v2/missions/${id}`);
    },
  };
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: API service with type-safe functions

---

## 4.4: Create React Query Hooks

### 4.4.1: Create useMissions hook

- [ ] Create `frontend/mission-planner/src/hooks/api/useMissions.ts`
- [ ] Implement query and mutation hooks:
  ```typescript
  import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
  import { missionsApi } from '../../services/missions';
  import type { Mission, CreateMissionRequest } from '../../types/mission';

  export function useMissions() {
    return useQuery({
      queryKey: ['missions'],
      queryFn: missionsApi.list,
    });
  }

  export function useMission(id: string) {
    return useQuery({
      queryKey: ['missions', id],
      queryFn: () => missionsApi.get(id),
      enabled: !!id,
    });
  }

  export function useCreateMission() {
    const queryClient = useQueryClient();

    return useMutation({
      mutationFn: (mission: CreateMissionRequest) => missionsApi.create(mission),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['missions'] });
      },
    });
  }

  export function useDeleteMission() {
    const queryClient = useQueryClient();

    return useMutation({
      mutationFn: (id: string) => missionsApi.delete(id),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['missions'] });
      },
    });
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: React Query hooks for missions

---

## 4.5: Install ShadCN UI Components

### 4.5.1: Install required UI components

- [ ] Install Button component:
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner install
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner list @radix-ui/react-slot
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add button
  ```
- [ ] Install Card component:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add card
  ```
- [ ] Install Dialog component:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add dialog
  ```
- [ ] Install Input component:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add input
  ```
- [ ] Install Label component:
  ```bash
  npx --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner shadcn@latest add label
  ```
- [ ] Expected: UI components installed in `src/components/ui/`

---

## 4.6: Create Mission List Component

### 4.6.1: Create MissionCard component

- [ ] Create `frontend/mission-planner/src/components/missions/MissionCard.tsx`
- [ ] Implement card to display mission summary:
  ```typescript
  import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card';
  import { Button } from '../ui/button';
  import type { Mission } from '../../types/mission';

  interface MissionCardProps {
    mission: Mission;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
  }

  export function MissionCard({ mission, onSelect, onDelete }: MissionCardProps) {
    return (
      <Card className="cursor-pointer hover:shadow-lg transition-shadow">
        <CardHeader onClick={() => onSelect(mission.id)}>
          <CardTitle>{mission.name}</CardTitle>
          <CardDescription>{mission.description || 'No description'}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">
              {mission.legs.length} leg{mission.legs.length !== 1 ? 's' : ''}
            </span>
            <Button
              variant="destructive"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(mission.id);
              }}
            >
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Reusable mission card component

### 4.6.2: Create MissionList component

- [ ] Create `frontend/mission-planner/src/components/missions/MissionList.tsx`
- [ ] Implement list view with loading/error states:
  ```typescript
  import { useMissions, useDeleteMission } from '../../hooks/api/useMissions';
  import { MissionCard } from './MissionCard';
  import { Button } from '../ui/button';

  interface MissionListProps {
    onSelectMission: (id: string) => void;
    onCreateNew: () => void;
  }

  export function MissionList({ onSelectMission, onCreateNew }: MissionListProps) {
    const { data: missions, isLoading, error } = useMissions();
    const deleteMission = useDeleteMission();

    if (isLoading) return <div>Loading missions...</div>;
    if (error) return <div>Error loading missions: {error.message}</div>;

    return (
      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Missions</h1>
          <Button onClick={onCreateNew}>Create New Mission</Button>
        </div>

        {missions?.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            No missions yet. Create your first mission to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {missions?.map((mission) => (
              <MissionCard
                key={mission.id}
                mission={mission}
                onSelect={onSelectMission}
                onDelete={(id) => deleteMission.mutate(id)}
              />
            ))}
          </div>
        )}
      </div>
    );
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Mission list with create/delete actions

---

## 4.7: Create Mission Creation Dialog

### 4.7.1: Create CreateMissionDialog component

- [ ] Create `frontend/mission-planner/src/components/missions/CreateMissionDialog.tsx`
- [ ] Implement dialog with form:
  ```typescript
  import { useState } from 'react';
  import { useCreateMission } from '../../hooks/api/useMissions';
  import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
  import { Button } from '../ui/button';
  import { Input } from '../ui/input';
  import { Label } from '../ui/label';

  interface CreateMissionDialogProps {
    open: boolean;
    onClose: () => void;
  }

  export function CreateMissionDialog({ open, onClose }: CreateMissionDialogProps) {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const createMission = useCreateMission();

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();

      if (!name.trim()) return;

      const id = name.toLowerCase().replace(/\s+/g, '-');

      await createMission.mutateAsync({
        id,
        name,
        description: description || undefined,
        legs: [],
      });

      setName('');
      setDescription('');
      onClose();
    };

    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Mission</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Mission Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Operation Falcon"
                required
              />
            </div>
            <div>
              <Label htmlFor="description">Description (optional)</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Multi-leg transcontinental mission"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMission.isPending}>
                {createMission.isPending ? 'Creating...' : 'Create Mission'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    );
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Dialog for creating missions

---

## 4.8: Setup Routing

### 4.8.1: Create router configuration

- [ ] Install React Router DOM (if not already):
  ```bash
  npm --prefix /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner list react-router-dom
  ```
- [ ] Create `frontend/mission-planner/src/App.tsx`:
  ```typescript
  import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
  import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
  import { MissionsPage } from './pages/MissionsPage';

  const queryClient = new QueryClient();

  function App() {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/missions" element={<MissionsPage />} />
            <Route path="/" element={<Navigate to="/missions" replace />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );
  }

  export default App;
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Router with QueryClient provider

### 4.8.2: Create MissionsPage

- [ ] Create `frontend/mission-planner/src/pages/MissionsPage.tsx`
- [ ] Implement page with list and dialog:
  ```typescript
  import { useState } from 'react';
  import { MissionList } from '../components/missions/MissionList';
  import { CreateMissionDialog } from '../components/missions/CreateMissionDialog';

  export function MissionsPage() {
    const [createDialogOpen, setCreateDialogOpen] = useState(false);

    const handleSelectMission = (id: string) => {
      console.log('Selected mission:', id);
      // TODO: Navigate to mission detail view
    };

    return (
      <div className="min-h-screen bg-gray-50">
        <MissionList
          onSelectMission={handleSelectMission}
          onCreateNew={() => setCreateDialogOpen(true)}
        />
        <CreateMissionDialog
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
        />
      </div>
    );
  }
  ```
- [ ] Save file (verify < 350 lines)
- [ ] Expected: Page component connecting list and dialog

---

## 4.9: Update Main Entry Point

### 4.9.1: Update main.tsx

- [ ] Open `frontend/mission-planner/src/main.tsx`
- [ ] Update to import global CSS and render App:
  ```typescript
  import React from 'react';
  import ReactDOM from 'react-dom/client';
  import App from './App.tsx';
  import './index.css';

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  ```
- [ ] Save file
- [ ] Expected: Entry point configured

### 4.9.2: Update index.css for Tailwind

- [ ] Open `frontend/mission-planner/src/index.css`
- [ ] Add Tailwind directives:
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  ```
- [ ] Save file
- [ ] Expected: Tailwind CSS loaded

---

## 4.10: Test Frontend in Development Mode

### 4.10.1: Start dev server

- [ ] Start Vite dev server:
  ```bash
  cd /home/brian/Projects/starlink-dashboard-dev/frontend/mission-planner && npm run dev
  ```
- [ ] Expected: Dev server running on http://localhost:5173

### 4.10.2: Verify in browser

- [ ] Open http://localhost:5173/missions in browser
- [ ] Verify mission list page loads
- [ ] Click "Create New Mission" button
- [ ] Fill in mission details and submit
- [ ] Expected: Mission created and appears in list

---

## 4.11: Commit Phase 4 Core Setup

- [ ] Stage all changes:
  ```bash
  git add frontend/mission-planner/src/
  ```
- [ ] Commit:
  ```bash
  git commit -m "feat: implement core mission UI components

  - Add API client service and TypeScript types
  - Create React Query hooks for missions
  - Implement MissionCard and MissionList components
  - Add CreateMissionDialog with form
  - Setup routing with React Router
  - Configure Tailwind CSS and ShadCN components

  Ref: dev/active/mission-leg-planning-ui/PLAN.md Phase 4"
  ```
- [ ] Push:
  ```bash
  git push origin feat/mission-leg-planning-ui
  ```
- [ ] Expected: Core mission UI committed

---

## Status

- [ ] All Phase 4 tasks completed
- [ ] Dev server runs without errors
- [ ] Mission CRUD operations work end-to-end
