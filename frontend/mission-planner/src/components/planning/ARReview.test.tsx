/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type {
  ExpectedLeg,
  ItineraryAR,
  RouteAnchor,
} from '../../types/planning';
vi.mock('../common/RouteMap', () => ({
  RouteMap: ({ anchoredARSpans }: { anchoredARSpans: unknown }) => (
    <output aria-label="Map spans">{JSON.stringify(anchoredARSpans)}</output>
  ),
}));
import { ARReview } from './ARReview';
const row: ItineraryAR = {
  id: 'ar',
  track: 'AR106',
  source_page: 2,
  source_row: 4,
  source_text: 'Rotated source 210 AR106',
  source_altitude: 210,
  entry_time: '2026-10-25T12:10:00Z',
  exit_time: '2026-10-25T12:20:00Z',
  source_time_precision: 'minute',
};
const leg: ExpectedLeg = {
  id: 'leg',
  ordinal: 1,
  departure_airport: 'AAA',
  arrival_airport: 'BBB',
  departure_time: '2026-10-25T12:00:00Z',
  arrival_time: '2026-10-25T13:00:00Z',
  ar_section_status: 'listed',
  ar_rows: [row],
};
afterEach(cleanup);
function Form({ initial = leg }: { initial?: ExpectedLeg }) {
  const [rows, setRows] = useState(initial.ar_rows ?? []);
  const [section, setSection] = useState(initial.ar_section_status ?? 'empty');
  const [none, setNone] = useState(false);
  return (
    <>
      <ARReview
        leg={initial}
        rows={rows}
        onChange={setRows}
        sectionStatus={section}
        onSectionStatusChange={setSection}
        noARsConfirmed={none}
        onNoARsConfirmedChange={setNone}
      />
      <output aria-label="Corrections">{JSON.stringify(rows)}</output>
    </>
  );
}
it('requires altitude units, corrects extracted values and retains rotated source evidence', () => {
  render(<Form />);
  expect(screen.getByText(/confirm altitude and units/i)).toBeVisible();
  expect(screen.getByLabelText('Confirm AR106')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Altitude units AR106'), {
    target: { value: 'flight_level' },
  });
  fireEvent.change(screen.getByLabelText('Track AR106'), {
    target: { value: 'AR107' },
  });
  expect(screen.getByLabelText('Corrections')).toHaveTextContent(
    '"confirmed_units":"flight_level"'
  );
  expect(screen.getByText('Rotated source 210 AR106')).toBeVisible();
  expect(screen.getByText(/Page 2, row 4/i)).toBeVisible();
});
it('requires explicit correction of unknown sections before no-AR confirmation', () => {
  render(
    <Form
      initial={{ ...leg, ar_rows: [], ar_section_status: 'unrecognized' }}
    />
  );
  expect(screen.getByRole('alert')).toHaveTextContent(/unrecognized/i);
  expect(screen.getByLabelText(/confirm no AR windows/i)).toBeDisabled();
  fireEvent.change(screen.getByLabelText('AR section correction'), {
    target: { value: 'empty' },
  });
  fireEvent.click(screen.getByLabelText(/confirm no AR windows/i));
  expect(screen.getByLabelText(/confirm no AR windows/i)).toBeChecked();
  fireEvent.click(screen.getByRole('button', { name: 'Add AR row' }));
  expect(screen.queryByLabelText(/confirm no AR windows/i)).toBeNull();
});
it('requires a note for exclusion and keeps original UTC source times visible', () => {
  render(<Form />);
  fireEvent.click(screen.getByLabelText('Exclude AR106'));
  expect(screen.getByText(/exclusion note required/i)).toBeVisible();
  fireEvent.change(screen.getByLabelText('Exclusion note AR106'), {
    target: { value: 'Not flown' },
  });
  expect(screen.getByLabelText('Corrections')).toHaveTextContent('Not flown');
  expect(screen.getByText(/Source UTC: 2026-10-25T12:10:00Z/)).toBeVisible();
});
it('selects ambiguous exact/interpolated occurrence candidates and highlights the actual curved span', () => {
  const start: RouteAnchor = {
    route_id: 'r',
    content_hash: 'h',
    segment_index: 0,
    fraction: 0,
    occurrence_id: 'exact:0',
    source_time: row.entry_time,
    latitude: 0,
    longitude: 10,
  };
  const end: RouteAnchor = {
    ...start,
    segment_index: 2,
    fraction: 0.5,
    occurrence_id: 'segment:2:0.5',
    source_time: row.exit_time,
    latitude: 2.5,
    longitude: 13,
  };
  const initial: ExpectedLeg = {
    ...leg,
    route: {
      route_id: 'r',
      content_hash: 'h',
      source_id: 's',
      filename: 'test.kml',
    },
  };
  function MatchingForm() {
    const [rows, setRows] = useState([
      {
        ...row,
        confirmed_units: 'flight_level' as const,
        match_status: 'ambiguous' as const,
      } as ItineraryAR,
    ]);
    return (
      <ARReview
        leg={initial}
        rows={rows}
        onChange={setRows}
        sectionStatus="listed"
        onSectionStatusChange={() => {}}
        noARsConfirmed={false}
        onNoARsConfirmedChange={() => {}}
        coordinates={[
          [0, 10],
          [1, 14],
          [2, 11],
          [3, 15],
        ]}
        candidates={[
          {
            ar_id: row.id,
            start_candidates: [start, { ...start, occurrence_id: 'other:0' }],
            end_candidates: [end],
          },
        ]}
      />
    );
  }
  render(<MatchingForm />);
  expect(screen.getByLabelText('Map spans')).toHaveTextContent('[]');
  fireEvent.change(screen.getByLabelText('Entry occurrence AR106'), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText('Exit occurrence AR106'), {
    target: { value: '0' },
  });
  expect(screen.getByText(/Matched entry: Exact/)).toBeVisible();
  expect(screen.getByText(/Matched exit: Interpolated/)).toBeVisible();
  expect(screen.getByLabelText('Map spans')).toHaveTextContent(
    '[[0,10],[1,14],[2,11],[2.5,13]]'
  );
  expect(screen.getByLabelText('Confirm AR106')).toBeEnabled();
});

it('maps an added row using explicit timed occurrences and rejects reversed span choices', () => {
  const binding = {
    route_id: 'r',
    content_hash: 'h',
    source_id: 's',
    filename: 'manual.kml',
  };
  const points = [
    {
      latitude: 1,
      longitude: 2,
      occurrence_id: 'visit:0',
      expected_arrival_time: row.entry_time,
    },
    {
      latitude: 3,
      longitude: 4,
      occurrence_id: 'visit:1',
      expected_arrival_time: row.exit_time,
    },
  ];
  function AddedForm() {
    const [rows, setRows] = useState<ItineraryAR[]>([
      { ...row, id: 'added', confirmed_units: 'feet' },
    ]);
    return (
      <ARReview
        leg={{ ...leg, ar_rows: [], route: binding }}
        rows={rows}
        onChange={setRows}
        sectionStatus="listed"
        onSectionStatusChange={() => {}}
        noARsConfirmed={false}
        onNoARsConfirmedChange={() => {}}
        routePoints={points}
      />
    );
  }
  render(<AddedForm />);
  expect(screen.getByLabelText('Confirm AR106')).toBeDisabled();
  expect(
    screen.getAllByRole('option', {
      name: /12:10:00Z.*1.00000, 2.00000.*visit:0/,
    })
  ).toHaveLength(2);
  fireEvent.change(screen.getByLabelText('Entry occurrence AR106'), {
    target: { value: '1' },
  });
  fireEvent.change(screen.getByLabelText('Exit occurrence AR106'), {
    target: { value: '0' },
  });
  expect(screen.getByLabelText('Confirm AR106')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Entry occurrence AR106'), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText('Exit occurrence AR106'), {
    target: { value: '1' },
  });
  expect(screen.getByLabelText('Confirm AR106')).toBeEnabled();
  fireEvent.click(screen.getByLabelText('Confirm AR106'));
  expect(screen.getByLabelText('Confirm AR106')).toBeChecked();
});
