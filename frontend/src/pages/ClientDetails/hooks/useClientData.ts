import { useState, useEffect, useCallback } from 'react';
import { ClientItem, getClient } from '../../../lib/api';

export const useClientData = (clientId?: string) => {
  const [client, setClient] = useState<ClientItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchClient = useCallback(async () => {
    if (!clientId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const clientData = await getClient(parseInt(clientId));
      setClient(clientData);
    } catch (e: any) {
      setError(`שגיאה בטעינת לקוח: ${e?.response?.data?.detail || e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    fetchClient();
  }, [fetchClient]);

  return {
    client,
    loading,
    error,
    refreshClient: fetchClient,
  };
};
