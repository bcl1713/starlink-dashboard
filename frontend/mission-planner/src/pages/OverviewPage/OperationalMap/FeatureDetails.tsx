import type { OperationalFeature } from './operational-map-types';

export function FeatureDetails({
  feature,
  missing,
  onDismissMissing,
}: {
  readonly feature: OperationalFeature | null;
  readonly missing: boolean;
  readonly onDismissMissing: () => void;
}) {
  if (missing) {
    return (
      <section className="operational-map__panel" aria-label="Feature details">
        <p>Selected feature is no longer available</p>
        <button onClick={onDismissMissing} type="button">
          Dismiss
        </button>
      </section>
    );
  }
  if (!feature) return null;
  return (
    <section className="operational-map__panel" aria-label="Feature details">
      <h3>{feature.label}</h3>
      <dl>
        {feature.details.map((detail) => (
          <div key={detail.label}>
            <dt>{detail.label}</dt>
            <dd>{detail.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
