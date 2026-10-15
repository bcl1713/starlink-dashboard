/** Exceptions stay outside the layer key and planning-only card. */
export function OverviewMapStatus({
  messages,
}: {
  messages: readonly string[];
}) {
  if (!messages.length) return null;
  return (
    <section className="overview-map-status" aria-label="Map status">
      <div role="status">
        {messages.map((message) => (
          <p key={message}>
            {message}
            {message.includes('link warning') && (
              <span className="overview-visually-hidden">
                {' '}
                · existing configured forbidden-azimuth rule
              </span>
            )}
          </p>
        ))}
      </div>
    </section>
  );
}
