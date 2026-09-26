/** @vitest-environment jsdom */
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./pages/MissionsPage', () => ({
  MissionsPage: () => <main>Missions</main>,
}));
vi.mock('./pages/MissionDetailPage', () => ({
  MissionDetailPage: () => <main>Mission detail</main>,
}));
vi.mock('./pages/LegDetailPage', () => ({
  LegDetailPage: () => <main>Leg detail</main>,
}));
vi.mock('./pages/SatelliteManagerPage', () => ({
  default: () => <main>Satellites</main>,
}));
vi.mock('./pages/RouteManagerPage', () => ({
  RouteManagerPage: () => <main>Routes</main>,
}));
vi.mock('./pages/POIManagerPage', () => ({
  POIManagerPage: () => <main>POIs</main>,
}));
vi.mock('./pages/DataExportPage', () => ({
  DataExportPage: () => <main>Data export</main>,
}));
vi.mock('./pages/ConfigurationPage', () => ({
  ConfigurationPage: () => <main>Configuration</main>,
}));
vi.mock('./pages/OverviewPage', () => ({
  OverviewPage: () => <main>Overview</main>,
}));

import App from './App';

afterEach(() => {
  cleanup();
  Reflect.deleteProperty(document, 'fullscreenElement');
  window.history.replaceState({}, '', '/');
});

describe('App native fullscreen navigation', () => {
  it('hides primary navigation only after the document enters fullscreen and restores it on exit', () => {
    let fullscreenElement: Element | null = null;
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => fullscreenElement,
    });

    render(<App />);

    expect(
      screen.getByRole('navigation', { name: 'Primary navigation' })
    ).toBeTruthy();

    fullscreenElement = document.body;
    act(() => {
      document.dispatchEvent(new Event('fullscreenchange'));
    });

    expect(
      screen.getByRole('navigation', { name: 'Primary navigation' })
    ).toBeTruthy();

    fullscreenElement = document.documentElement;
    act(() => {
      document.dispatchEvent(new Event('fullscreenchange'));
    });

    expect(
      screen.queryByRole('navigation', { name: 'Primary navigation' })
    ).toBeNull();

    fullscreenElement = null;
    act(() => {
      document.dispatchEvent(new Event('fullscreenchange'));
    });

    expect(
      screen.getByRole('navigation', { name: 'Primary navigation' })
    ).toBeTruthy();
  });
});
