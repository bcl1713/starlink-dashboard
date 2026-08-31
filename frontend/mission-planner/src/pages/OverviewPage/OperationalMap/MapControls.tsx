import type { RefObject } from 'react';

export function MapControls({
  activationButtonRef,
  measurementText,
  mobileActive,
  mobileLocked,
  onActivateMobile,
  onAddCenter,
  onClearMeasure,
  onDisableMobile,
  onFit,
  onZoomIn,
  onZoomOut,
}: {
  readonly activationButtonRef: RefObject<HTMLButtonElement | null>;
  readonly measurementText: string;
  readonly mobileActive: boolean;
  readonly mobileLocked: boolean;
  readonly onActivateMobile: () => void;
  readonly onAddCenter: () => void;
  readonly onClearMeasure: () => void;
  readonly onDisableMobile: () => void;
  readonly onFit: () => void;
  readonly onZoomIn: () => void;
  readonly onZoomOut: () => void;
}) {
  return (
    <div className="operational-map__panel operational-map__controls">
      <button
        className="operational-map__button"
        onClick={onZoomIn}
        type="button"
      >
        +
      </button>
      <button
        className="operational-map__button"
        onClick={onZoomOut}
        type="button"
      >
        -
      </button>
      <button className="operational-map__button" onClick={onFit} type="button">
        Fit to available layers
      </button>
      <button
        className="operational-map__button"
        onClick={onAddCenter}
        type="button"
      >
        Add map-center point
      </button>
      <button
        className="operational-map__button"
        onClick={onClearMeasure}
        type="button"
      >
        Clear measurement
      </button>
      {mobileLocked ? (
        <button
          ref={activationButtonRef}
          className="operational-map__button"
          onClick={mobileActive ? onDisableMobile : onActivateMobile}
          type="button"
        >
          {mobileActive ? 'Return to page scrolling' : 'Enable map interaction'}
        </button>
      ) : null}
      <span>{measurementText}</span>
    </div>
  );
}
