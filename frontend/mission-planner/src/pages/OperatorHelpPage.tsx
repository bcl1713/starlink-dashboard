import { Link, useSearchParams } from 'react-router-dom';

export function OperatorHelpPage() {
  const [params] = useSearchParams();
  const reference = params.get('doc') === 'quick-reference';
  const requestedSection = params.get('section') ?? 'context';
  const section = /^[a-z][a-z0-9-]{0,63}$/.test(requestedSection)
    ? requestedSection
    : 'context';
  const requestedReturn = params.get('returnTo') ?? '';
  const returnTo = /^\/operator(?:\?[^#]*)?$/.test(requestedReturn)
    ? requestedReturn
    : '/operator?workspace=1';
  const title = reference ? 'Operator quick reference' : 'Operator user guide';
  const resource = `/operator-help/${reference ? 'quick-reference' : 'guide'}.html`;
  const context = `returnTo=${encodeURIComponent(returnTo)}`;
  return (
    <main className="mx-auto flex min-h-[80vh] max-w-screen-2xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-4">
        <h1 className="mr-auto text-2xl font-semibold">{title}</h1>
        <Link
          className="inline-flex min-h-11 items-center rounded border px-3"
          to={returnTo}
        >
          Return to Operator
        </Link>
        <Link
          className="inline-flex min-h-11 items-center rounded border px-3"
          to={`/operator/help?${context}&doc=${reference ? 'guide' : 'quick-reference'}`}
        >
          {reference ? 'User guide' : 'Quick reference'}
        </Link>
        <a
          className="inline-flex min-h-11 items-center rounded border px-3"
          href={resource}
          target="_blank"
          rel="noreferrer"
        >
          Open for printing
        </a>
      </header>
      <p>
        Packaged on this installation. Your retained drafts and pending saves
        stay in Operator; reading Help does not submit or retry them.
      </p>
      <iframe
        title={title}
        src={`${resource}${reference ? '' : `#${section}`}`}
        className="min-h-[70vh] w-full flex-1 rounded border bg-white"
      />
    </main>
  );
}
