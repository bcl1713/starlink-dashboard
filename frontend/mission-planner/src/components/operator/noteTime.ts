import { instant } from './issueForms';
/** Capture once when the retained note draft is created, never on submission. */
export const createNoteTime = (now: string) => instant(now);
