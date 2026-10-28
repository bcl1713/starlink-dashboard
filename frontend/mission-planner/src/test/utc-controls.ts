import { fireEvent, screen } from '@testing-library/react';
/** Enter an explicit Zulu calendar date, 24-hour hour and minute. */
export function enterZulu(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(`${label} date (Zulu)`), {
    target: { value: value.slice(0, 10) },
  });
  fireEvent.change(screen.getByLabelText(`${label} hour (Zulu)`), {
    target: { value: value.slice(11, 13) },
  });
  fireEvent.change(screen.getByLabelText(`${label} minute (Zulu)`), {
    target: { value: value.slice(14, 16) },
  });
}
