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
    <div style={{ 
      marginTop: '30px',
      marginBottom: '20px', 
      padding: '20px', 
      backgroundColor: '#f8f9fa', 
      borderRadius: '8px',
      border: '2px solid #dee2e6'
    }}>
      <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#495057' }}>
        🔄 שמירה ושחזור מצב מערכת
      </h3>
      <SystemSnapshot 
        clientId={clientId} 
        onSnapshotRestored={onSnapshotRestored}
      />
    </div>
  );
};
