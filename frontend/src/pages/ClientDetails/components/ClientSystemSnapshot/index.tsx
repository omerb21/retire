import React from 'react';
import SystemSnapshot from '../../../../components/SystemSnapshot';

interface ClientSystemSnapshotProps {
  clientId: number;
  onSnapshotRestored: () => void;
}

export const ClientSystemSnapshot: React.FC<ClientSystemSnapshotProps> = ({ 
  clientId, 
  onSnapshotRestored 
}) => {
  return (
    <div className="client-system-snapshot-container">
      <h3 className="client-system-snapshot-title">
        🔄 שמירה ושחזור מצב מערכת
      </h3>
      <SystemSnapshot 
        clientId={clientId} 
        onSnapshotRestored={onSnapshotRestored}
      />
    </div>
  );
};
