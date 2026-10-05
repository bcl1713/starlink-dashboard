import type { RefObject } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { AdsbContactView } from './overview-adsb-state';
import './OverviewAdsb.css';
export function OverviewAdsbDetails({
  contact,
  onClose,
  returnFocusRef,
  portalContainer,
}: {
  contact: AdsbContactView | null;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLElement | null>;
  portalContainer: HTMLElement | null;
}) {
  const unavailable = 'Unavailable';
  const values = contact
    ? [
        ['Hex', contact.hex],
        ['Callsign', contact.callsign || unavailable],
        ['Registration', contact.registration || unavailable],
        ['Aircraft type', contact.aircraft_type || unavailable],
        [
          'Military',
          contact.military === null
            ? unavailable
            : contact.military
              ? 'Yes'
              : 'No',
        ],
        ['Latitude', `${contact.latitude}°`],
        ['Longitude', `${contact.longitude}°`],
        [
          'Altitude',
          contact.altitude
            ? `${contact.altitude.value} ft (${contact.altitude.source})`
            : unavailable,
        ],
        [
          'Ground speed',
          contact.ground_speed_knots === null
            ? unavailable
            : `${contact.ground_speed_knots} knots`,
        ],
        [
          'Track',
          contact.track_degrees === null
            ? unavailable
            : `${contact.track_degrees}°`,
        ],
        ['Position age', `${contact.position_age_seconds.toFixed(1)} seconds`],
        ['Status', contact.freshness === 'stale' ? '◷ Stale' : 'Current'],
        [
          'Position observed',
          new Date(contact.position_observed_at_ms).toISOString(),
        ],
        ['Acquired', new Date(contact.acquired_at_ms).toISOString()],
      ]
    : [];
  return (
    <Dialog.Root
      open={contact !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal container={portalContainer}>
        <Dialog.Overlay className="adsb-details-overlay" />
        <Dialog.Content
          className="adsb-details"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            (returnFocusRef.current?.isConnected
              ? returnFocusRef.current
              : portalContainer
            )?.focus();
          }}
        >
          <Dialog.Title>Aircraft {contact?.label}</Dialog.Title>
          <Dialog.Description>
            ADS-B observation · read-only details
          </Dialog.Description>
          <dl>
            {values.map(([name, value]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <Dialog.Close className="adsb-details-close">Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
