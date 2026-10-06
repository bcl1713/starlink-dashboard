import type { WeatherLayerView } from './weather-state';
import './OverviewWeather.css';
const labels = {
  off: '',
  loading: 'Loading precipitation',
  current: 'Current precipitation',
  stale: 'Stale precipitation',
  unavailable: 'Weather unavailable',
};
export function OverviewWeatherStatus({
  weather,
}: {
  weather: WeatherLayerView;
}) {
  if (!weather.configuredEnabled) return null;
  return (
    <section className="overview-weather-status" aria-label="Weather status">
      <p className="overview-weather-status__state" role="status">
        {labels[weather.state]}
      </p>
      {weather.frameTimeMs !== null && (
        <p>
          <time dateTime={new Date(weather.frameTimeMs).toISOString()}>
            {new Date(weather.frameTimeMs).toISOString().slice(11, 16)} UTC
          </time>{' '}
          · {Math.floor((weather.ageMs ?? 0) / 60000)} min old
        </p>
      )}
      <p className="overview-weather-legend">
        <span>
          <i className="overview-weather-legend__radar" aria-hidden="true" />
          Precipitation
        </span>
        <span>
          <i
            className="overview-weather-legend__uncovered"
            aria-hidden="true"
          />
          No radar coverage
        </span>
      </p>
      <p>
        Weather data by{' '}
        <a
          href="https://www.rainviewer.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          RainViewer
        </a>
      </p>
    </section>
  );
}
