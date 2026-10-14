/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { PermittedSatellites } from './PermittedSatellites';
import { defaultSatelliteSelection } from '../../services/planning';
import type { PlanningSatelliteOptions } from '../../types/planning';
const options: PlanningSatelliteOptions = {
  satellites: [
    {
      id: 'X-good',
      label: 'X good',
      transport: 'X',
      eligible: true,
      latitude: 0,
      longitude: 10,
    },
    {
      id: 'X-bad',
      label: 'X bad',
      transport: 'X',
      eligible: false,
      error: { code: 'missing', message: 'Position missing' },
    },
    { id: 'Ka', label: 'Ka', transport: 'Ka', eligible: false },
  ],
};
afterEach(cleanup);
function Form() {
  const [value, setValue] = useState(defaultSatelliteSelection(options));
  return (
    <>
      <PermittedSatellites
        options={options}
        value={value}
        onChange={setValue}
      />
      <output>{JSON.stringify(value)}</output>
    </>
  );
}
it('preselects only eligible X, requires access, and resets binding on set changes', () => {
  render(<Form />);
  expect(screen.getByLabelText('X good')).toBeChecked();
  expect(screen.getByLabelText('X bad')).toBeDisabled();
  expect(screen.queryByLabelText('Ka')).toBeNull();
  expect(screen.getByLabelText(/confirm service access/i)).not.toBeChecked();
  fireEvent.click(screen.getByLabelText(/confirm service access/i));
  expect(screen.getByLabelText(/confirm service access/i)).toBeChecked();
  fireEvent.click(screen.getByLabelText('X good'));
  expect(screen.getByLabelText(/confirm service access/i)).not.toBeChecked();
  expect(screen.getByRole('alert')).toHaveTextContent(/select/i);
});
it('persists the operational Starshield toggle independently of catalog display', () => {
  render(<Form />);
  expect(
    screen.getByLabelText('Starshield enabled for this plan')
  ).toBeChecked();
  fireEvent.click(screen.getByLabelText('Starshield enabled for this plan'));
  expect(screen.getByRole('status')).toHaveTextContent(
    '"starshield_enabled":false'
  );
});
