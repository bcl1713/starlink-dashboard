/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OperationalClockSettingsForm } from './OperationalClockSettingsForm';
afterEach(() => {
  cleanup();
});
describe('OperationalClockSettingsForm', () => {
  it('renders editable label and timezone fields for all four clocks', () => {
    render(
      <OperationalClockSettingsForm
        clocks={[
          { label: 'Zulu / UTC', time_zone: 'UTC' },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          { label: 'Omaha, NE', time_zone: 'America/Chicago' },
          { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
        ]}
        isSaving={false}
        onSave={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Clock 1 label')).not.toBeNull();
    expect(screen.getByLabelText('Clock 1 timezone')).not.toBeNull();
    expect(screen.getByLabelText('Clock 4 label')).not.toBeNull();
    expect(screen.getByLabelText('Clock 4 timezone')).not.toBeNull();
  });
  it('updates a clock label while editing', () => {
    render(
      <OperationalClockSettingsForm
        clocks={[
          { label: 'Zulu / UTC', time_zone: 'UTC' },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          { label: 'Omaha, NE', time_zone: 'America/Chicago' },
          { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
        ]}
        isSaving={false}
        onSave={vi.fn()}
      />
    );
    const labelInput = screen.getByLabelText(
      'Clock 1 label'
    ) as HTMLInputElement;
    fireEvent.change(labelInput, {
      target: { value: 'Zulu Custom' },
    });
    expect(labelInput.value).toBe('Zulu Custom');
  });
  it('submits the current edited clock collection', () => {
    const onSave = vi.fn();
    render(
      <OperationalClockSettingsForm
        clocks={[
          { label: 'Zulu / UTC', time_zone: 'UTC' },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          { label: 'Omaha, NE', time_zone: 'America/Chicago' },
          { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
        ]}
        isSaving={false}
        onSave={onSave}
      />
    );
    const labelInput = screen.getByLabelText(
      'Clock 3 label'
    ) as HTMLInputElement;
    const timezoneInput = screen.getByLabelText(
      'Clock 3 timezone'
    ) as HTMLInputElement;
    const form = labelInput.closest('form') as HTMLFormElement;
    fireEvent.change(labelInput, {
      target: { value: 'Andrews AFB, MD' },
    });
    fireEvent.change(timezoneInput, {
      target: { value: 'America/New_York' },
    });
    const submitEvent = new Event('submit', {
      bubbles: true,
      cancelable: true,
    });
    fireEvent(form, submitEvent);
    expect(submitEvent.defaultPrevented).toBe(true);
    expect(onSave).toHaveBeenCalledWith({
      clocks: [
        { label: 'Zulu / UTC', time_zone: 'UTC' },
        { label: 'Washington, DC', time_zone: 'America/New_York' },
        { label: 'Andrews AFB, MD', time_zone: 'America/New_York' },
        { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
      ],
    });
  });
  it('has a visible save control', () => {
    const onSave = vi.fn();
    render(
      <OperationalClockSettingsForm
        clocks={[
          { label: 'Zulu / UTC', time_zone: 'UTC' },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          { label: 'Omaha, NE', time_zone: 'America/Chicago' },
          { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
        ]}
        isSaving={false}
        onSave={onSave}
      />
    );
    expect(
      screen.getByRole('button', {
        name: 'Save operational clocks',
      })
    ).not.toBeNull();
  });
  it('disables saving while the request is pending', () => {
    const onSave = vi.fn();
    render(
      <OperationalClockSettingsForm
        clocks={[
          { label: 'Zulu / UTC', time_zone: 'UTC' },
          {
            label: 'Washington, DC',
            time_zone: 'America/New_York',
          },
          { label: 'Omaha, NE', time_zone: 'America/Chicago' },
          { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
        ]}
        isSaving={true}
        onSave={onSave}
      />
    );
    const saveButton = screen.getByRole('button', {
      name: 'Saving...',
    }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });
});
