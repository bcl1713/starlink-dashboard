/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it } from 'vitest';
import { OperatorHelpPage } from './OperatorHelpPage';
afterEach(cleanup);
function open(query: string) {
  return render(
    <MemoryRouter initialEntries={[`/operator/help?${query}`]}>
      <OperatorHelpPage />
    </MemoryRouter>
  );
}
it('opens the packaged guide section and returns to the original operational context', () => {
  open(
    'section=conferences&returnTo=%2Foperator%3Fworkspace%3D1%26mission_id%3Dfictional%26view%3Dcommunications'
  );
  expect(screen.getByTitle('Operator user guide').getAttribute('src')).toBe(
    '/operator-help/guide.html#conferences'
  );
  expect(
    screen
      .getByRole('link', { name: 'Return to Operator' })
      .getAttribute('href')
  ).toBe('/operator?workspace=1&mission_id=fictional&view=communications');
});
it('offers the print quick reference and refuses external return paths or document names', () => {
  open('doc=quick-reference&returnTo=https%3A%2F%2Fexample.com');
  expect(
    screen.getByTitle('Operator quick reference').getAttribute('src')
  ).toBe('/operator-help/quick-reference.html');
  expect(
    screen
      .getByRole('link', { name: 'Return to Operator' })
      .getAttribute('href')
  ).toBe('/operator?workspace=1');
  cleanup();
  open('doc=https%3A%2F%2Fexample.com&section=javascript%3Aalert(1)');
  expect(screen.getByTitle('Operator user guide').getAttribute('src')).toBe(
    '/operator-help/guide.html#context'
  );
});
