const millisecondsPerMinute = 60_000;

export function millisecondsUntilNextMinute(date: Date): number {
  const millisecondsIntoMinute = date.getTime() % millisecondsPerMinute;

  return millisecondsPerMinute - millisecondsIntoMinute;
}
