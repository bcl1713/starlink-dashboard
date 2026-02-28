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
