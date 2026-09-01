import { AppNavigation } from './AppNavigation';
import { AppRoutes } from './AppRoutes';

export function AppShell() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <AppNavigation />
      <main id="main-content" tabIndex={-1}>
        <AppRoutes />
      </main>
    </>
  );
}
