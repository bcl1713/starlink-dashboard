# Mission Planner

Frontend application for mission planning, route
management, and real-time Starlink telemetry monitoring.

## Tech Stack

- **React 19** + **TypeScript** + **Vite**
- **Tailwind CSS** + **shadcn/ui** (Radix primitives)
- **React-Leaflet** for map visualization
- **TanStack React Query** for server state
- **Zustand** for client state
- **React Router** for navigation
- **React Hook Form** + **Zod** for form validation
- **Axios** for API requests

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Type check and build
npm run build

# Lint
npm run lint
```

### API base contract

The Mission Planner always calls origin-relative `/api/...` endpoints. Do not
set `VITE_API_URL`: service methods already include `/api`, so setting it to
`/api` produces invalid `/api/api/...` requests. The Vite development server
and production Nginx image both proxy `/api/` to the backend. A simulation
deployment intentionally starts with an empty mission collection; it does not
seed a fixture automatically.

## Project Structure

```text
src/
  components/    # React components
    ui/          # shadcn/ui primitives
  hooks/
    api/         # React Query hooks
  services/      # Axios API service layers
  pages/         # Route page components
```

## Testing

- **Playwright** for E2E tests
- **Testing Library** for component tests

### E2E command ladder

Run these commands from `frontend/mission-planner`. Playwright owns the
production build through its configured `webServer.command`; do not run a
standalone `npm run build` immediately before a Playwright command.

```bash
# Confirm the Chromium E2E inventory before browser execution.
npx playwright test --list --project=chromium

# Exercise the focused same-origin fixture control.
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line

# Run the affected fixture-origin spec after a harness change.
npx playwright test tests/e2e/api-origin.spec.ts --project=chromium --reporter=line

# Run the final Chromium inventory once for the candidate commit.
npx playwright test --project=chromium --reporter=line
```

The owned cold focused invocation measured 56.71 seconds end-to-end on the
development host. The Playwright web-server startup budget is 120 seconds,
providing headroom above that healthy measurement. E2E runs use no retries and
retain Playwright traces for failures only (`trace: 'retain-on-failure'`), so a
single failed attempt keeps bounded diagnostic evidence without retrying.

```bash
npx playwright test
```
