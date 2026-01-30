import { useState } from 'react';
import { useUploadRoute, useDownloadRoute } from '../hooks/api/useRoutes';
import { RouteList } from '../components/routes/RouteList';
import { RouteUploadDialog } from '../components/routes/RouteUploadDialog';
import { RouteDetailDialog } from '../components/routes/RouteDetailDialog';
import { Button } from '../components/ui/button';
import type { Route } from '../services/routes';

export function RouteManagerPage() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const uploadRoute = useUploadRoute();
  const downloadRoute = useDownloadRoute();

  const handleUpload = (file: File) => {
    uploadRoute.mutate(file);
  };

  const handleDownload = (route: Route) => {
    downloadRoute.mutate(route.id, {
      onSuccess: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${route.name}.kml`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      },
    });
  };

  const handleSelectRoute = (id: string) => {
    setSelectedRouteId(id);
    setDetailOpen(true);
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Route Manager</h1>
        <Button onClick={() => setUploadOpen(true)}>Upload Route</Button>
      </div>

      <RouteList
        onSelectRoute={handleSelectRoute}
        onDelete={() => {}}
        onDownload={handleDownload}
      />

      <RouteUploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUpload={handleUpload}
        isLoading={uploadRoute.isPending}
      />

      <RouteDetailDialog
        open={detailOpen}
        onOpenChange={setDetailOpen}
        routeId={selectedRouteId}
      />
    </div>
  );
}
