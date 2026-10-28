import { createContext, useContext } from 'react';
import { Color } from 'three';

// Opt-in only. Ordinary Overview keeps bloom disabled; temporary debug mode opts in.
export const OverviewBloomMode = createContext(false);
export const useOverviewBloom = () => useContext(OverviewBloomMode);
export interface BloomEmission {
  cities: number;
  cityColor: string;
  lines: number;
  particles: number;
  pois: number;
  aircraft: number;
}
export const DEFAULT_EMISSION: BloomEmission = {
  cities: 20,
  cityColor: '#ffb15c',
  lines: 4,
  particles: 4,
  pois: 8,
  aircraft: 4,
};
export const OverviewBloomEmission =
  createContext<BloomEmission>(DEFAULT_EMISSION);
export const OverviewBloomCityIsolation = createContext(false);
export const useOverviewCityIsolation = () =>
  useContext(OverviewBloomCityIsolation);
export const useOverviewBloomEmission = () => useContext(OverviewBloomEmission);
export function resolveCityEmission(bloom: boolean, emission: BloomEmission) {
  return bloom
    ? { intensity: emission.cities, color: new Color(emission.cityColor) }
    : { intensity: 0.35, color: new Color().setRGB(0.92, 0.96, 1) };
}
export interface CityEmissionUniforms {
  cityEmissionIntensity: { value: number };
  citySurfaceScale: { value: number };
  cityEmissionColor: { value: Color };
}
export function updateCityEmissionUniforms(
  uniforms: CityEmissionUniforms,
  bloom: boolean,
  emission: BloomEmission,
  isolateCities = false
) {
  const resolved = resolveCityEmission(bloom, emission);
  uniforms.citySurfaceScale.value = bloom && isolateCities ? 0 : 1;
  uniforms.cityEmissionIntensity.value = resolved.intensity;
  uniforms.cityEmissionColor.value.copy(resolved.color);
}
