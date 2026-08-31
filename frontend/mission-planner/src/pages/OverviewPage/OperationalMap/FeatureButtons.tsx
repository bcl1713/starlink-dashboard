import type { OperationalFeature } from './operational-map-types';

export function FeatureButtons({
  features,
  onSelect,
}: {
  readonly features: readonly OperationalFeature[];
  readonly onSelect: (id: string) => void;
}) {
  return (
    <div className="operational-map__panel">
      {features.map((feature) => (
        <button
          className="operational-map__feature-button"
          key={feature.id}
          onClick={() => onSelect(feature.id)}
          type="button"
        >
          {feature.label}
        </button>
      ))}
    </div>
  );
}
