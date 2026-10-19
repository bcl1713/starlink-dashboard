import { apiClient } from './api-client';
export interface CatalogItem {
  id: string;
  name: string;
  enabled: boolean;
  archived: boolean;
}
export interface TransportCatalog {
  schema_version: 1;
  version: number;
  services: CatalogItem[];
  transports: CatalogItem[];
}
export const readTransportCatalog = async () =>
  (await apiClient.get<TransportCatalog>('/api/v2/operator/transport-catalog'))
    .data;
export const saveTransportCatalog = async (catalog: TransportCatalog) =>
  (
    await apiClient.put<TransportCatalog>(
      '/api/v2/operator/transport-catalog',
      catalog
    )
  ).data;
