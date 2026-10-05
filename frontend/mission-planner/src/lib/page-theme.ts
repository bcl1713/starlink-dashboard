import { createContext, useContext } from 'react';

// React context follows portaled controls; CSS inheritance alone does not.
export const PageThemeContext = createContext('');

export function usePageTheme() {
  return useContext(PageThemeContext);
}
