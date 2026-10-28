import { createContext, useContext } from 'react';

// Opt-in only. Ordinary Overview never supplies this experiment context.
export const OverviewBloomMode = createContext(false);
export const useOverviewBloom = () => useContext(OverviewBloomMode);
