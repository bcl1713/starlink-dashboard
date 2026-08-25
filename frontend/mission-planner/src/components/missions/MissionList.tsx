import { useLayoutEffect, useState } from 'react';
import { useMissionsPage, useDeleteMission } from '../../hooks/api/useMissions';
import { MissionCard } from './MissionCard';
import { Button } from '../ui/button';
import { MISSIONS_PAGE_SIZE } from '../../services/missions';

interface MissionListProps {
  onSelectMission: (id: string) => void;
  onCreateNew: () => void;
  onImport: () => void;
  onExport: (id: string, name: string) => void;
}

export function MissionList({
  onSelectMission,
  onCreateNew,
  onImport,
  onExport,
}: MissionListProps) {
  const [page, setPage] = useState(1);
  const {
    data: missionPage,
    isLoading,
    error,
  } = useMissionsPage(MISSIONS_PAGE_SIZE, (page - 1) * MISSIONS_PAGE_SIZE);
  const deleteMission = useDeleteMission();
  const missions = missionPage?.missions;
  const total = missionPage?.total ?? 0;
  const totalPages = Math.ceil(total / MISSIONS_PAGE_SIZE);
  const lastValidPage = Math.max(totalPages, 1);

  useLayoutEffect(() => {
    // Query results can shrink after a delete; correct before the empty page paints.
    if (!missionPage || page <= lastValidPage) return;

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(lastValidPage);
  }, [lastValidPage, missionPage, page]);

  if (isLoading)
    return (
      <div className="app-page">
        <div className="rounded-xl border bg-card p-8 text-center text-muted-foreground">
          Loading missions...
        </div>
      </div>
    );
  if (error)
    return (
      <div className="app-page">
        <div className="status-critical rounded-xl border p-4" role="alert">
          Error loading missions: {(error as Error).message}
        </div>
      </div>
    );

  return (
    <div className="app-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Missions</h1>
          <p className="page-description">
            Configure mission legs, route data, and operational communications.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={onImport}>
            Import Mission
          </Button>
          <Button onClick={onCreateNew}>Create New Mission</Button>
        </div>
      </div>

      {missions?.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center text-muted-foreground">
          <p className="font-medium text-foreground">No missions yet</p>
          <p className="mt-1 text-sm">
            Create your first mission to begin planning its route and legs.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {missions?.map((mission) => (
            <MissionCard
              key={mission.id}
              mission={mission}
              onSelect={onSelectMission}
              onDelete={(id) => deleteMission.mutate(id)}
              onExport={onExport}
            />
          ))}
        </div>
      )}

      {total > MISSIONS_PAGE_SIZE && (
        <nav
          aria-label="Mission list pagination"
          className="mt-6 flex flex-wrap items-center justify-between gap-3"
        >
          <Button
            variant="outline"
            onClick={() =>
              setPage((currentPage) => Math.max(currentPage - 1, 1))
            }
            disabled={page === 1}
            aria-label="Previous page"
          >
            Previous
          </Button>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span aria-live="polite">
              Page {page} of {totalPages}
            </span>
            <label className="flex items-center gap-2">
              <span className="sr-only">Page</span>
              <select
                aria-label="Page"
                className="rounded-md border border-input bg-background px-2 py-1 text-foreground"
                value={page}
                onChange={(event) => setPage(Number(event.target.value))}
              >
                {Array.from(
                  { length: totalPages },
                  (_, index) => index + 1
                ).map((pageNumber) => (
                  <option key={pageNumber} value={pageNumber}>
                    Page {pageNumber}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Button
            variant="outline"
            onClick={() =>
              setPage((currentPage) => Math.min(currentPage + 1, lastValidPage))
            }
            disabled={page === totalPages}
            aria-label="Next page"
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
