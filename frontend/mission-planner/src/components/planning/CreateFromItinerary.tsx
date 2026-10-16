import { ImportDialog } from '../itinerary-import/ImportDialog';
export function CreateFromItinerary(props: {
  open: boolean;
  onClose: () => void;
  onSuccess: (missionId: string) => void;
}) {
  return <ImportDialog {...props} />;
}
