/** Display aliases never alter stored identifiers or original historical notes. */
export function transportLabel(value: string | null | undefined) {
  return value
    ? ({
        Ka: 'Ka Commercial',
        KA: 'Ka Commercial',
        ka: 'Ka Commercial',
        X: 'X-Band',
        'X-band': 'X-Band',
        Ku: 'Starshield',
        Starlink: 'Starshield',
        Starshield: 'Starshield',
      }[value] ?? value)
    : 'Unknown';
}
