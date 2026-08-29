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

```bash
npx playwright test
```
