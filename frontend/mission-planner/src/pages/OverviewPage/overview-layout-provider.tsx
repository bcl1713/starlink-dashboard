import { useContext, type ReactNode } from 'react';

import {
  OverviewLayoutContext,
  useOverviewLayoutMode,
} from './overview-layout';

export function OverviewLayoutProvider({
  children,
}: {
  readonly children: ReactNode;
}) {
  const sharedMode = useContext(OverviewLayoutContext);
  const localMode = useOverviewLayoutMode();
  const mode = sharedMode ?? localMode;

  return (
    <OverviewLayoutContext.Provider value={mode}>
      {children}
    </OverviewLayoutContext.Provider>
  );
}
