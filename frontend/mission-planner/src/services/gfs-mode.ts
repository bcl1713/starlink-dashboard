export type GfsFlags = { winds: boolean; temperature: boolean };

/** Legacy simultaneous preferences consistently select wind on every display. */
export function resolveGfsFlags(flags: GfsFlags): GfsFlags {
  return { winds: flags.winds, temperature: !flags.winds && flags.temperature };
}
