export function sourceFor(url: URL): string {
  if (url.hostname === 'server.arcgisonline.com') return 'basemap';
  if (url.pathname === '/api/status') return 'telemetry';
  if (url.pathname === '/api/monitoring/history') return 'history';
  if (url.pathname === '/api/monitoring/ground-entry-point') {
    return 'groundEntryPoint';
  }
  if (url.pathname === '/api/pois/etas') {
    const category = url.searchParams.get('category');
    if (category === 'satellite') return 'satellites';
    if (category === 'mission-event') return 'missionEvents';
    return 'pois';
  }
  if (url.pathname.startsWith('/api/route/coordinates/')) return 'route';
  if (url.pathname === '/api/active-x-link') return 'activeLink';
  if (url.pathname.startsWith('/api/weather/radar/')) return 'radar';
  return 'unknown';
}
