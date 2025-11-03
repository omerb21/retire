/**
 * useGrants Hook - Manage grants state and operations
 * Hook לניהול מצב ופעולות על מענקים
 */

import { useState, useEffect } from 'react';
import { Grant, GrantDetails, GrantFormData } from '../types/grant.types';
import { GrantService } from '../services/grantService';
import { calculateGrantDetails } from '../utils/grantCalculations';

export function useGrants(clientId: string | undefined) {
  const [grants, setGrants] = useState<Grant[]>([]);
  const [grantDetails, setGrantDetails] = useState<{ [key: number]: GrantDetails }>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load grants from server
   */
  const loadGrants = async () => {
    if (!clientId) return;

    try {
      setLoading(true);
      setError(null);
      
      const grantsData = await GrantService.fetchGrants(clientId);
      setGrants(grantsData);
      
      // Calculate details for each grant
      for (const grant of grantsData) {
        if (grant.id) {
          const details = await calculateGrantDetails(grant);
          if (details) {
            setGrantDetails(prev => ({ ...prev, [grant.id!]: details }));
          }
        }
      }
    } catch (err: any) {
      console.error('Error loading grants:', err);
      setError(err.message || 'שגיאה בטעינת המענקים');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Create a new grant
   */
  const createGrant = async (grantData: GrantFormData): Promise<boolean> => {
    if (!clientId) return false;

    try {
      setLoading(true);
      setError(null);
      
      await GrantService.createGrant(clientId, grantData);
      await loadGrants(); // Reload grants
      
      return true;
    } catch (err: any) {
      console.error('Error creating grant:', err);
      setError(err.message || 'שגיאה בהוספת מענק');
      return false;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Delete a grant
   */
  const deleteGrant = async (grantId: number): Promise<boolean> => {
    if (!clientId) return false;

    if (!confirm('האם אתה בטוח שברצונך למחוק את המענק?')) {
      return false;
    }

    try {
      setLoading(true);
      setError(null);
      
      await GrantService.deleteGrant(clientId, grantId);
      await loadGrants(); // Reload grants
      
      return true;
    } catch (err: any) {
      console.error('Error deleting grant:', err);
      setError(err.message || 'שגיאה במחיקת מענק');
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Load grants on mount
  useEffect(() => {
    loadGrants();
  }, [clientId]);

  return {
    grants,
    grantDetails,
    loading,
    error,
    createGrant,
    deleteGrant,
    reloadGrants: loadGrants
  };
}
