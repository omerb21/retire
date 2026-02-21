/**
 * useCapitalAssets Hook
 * =====================
 * Custom hook for managing capital assets CRUD operations
 */

import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { apiRoutes } from '../api/routes';
import { CapitalAsset } from '../types/capitalAsset';
import { restoreBalanceToPensionPortfolio } from '../pages/PensionPortfolio/services/pensionPortfolioStorageService';

export function useCapitalAssets(clientId: string | undefined) {
  const [assets, setAssets] = useState<CapitalAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  async function loadAssets() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<CapitalAsset[]>(apiRoutes.clients.capitalAssets(clientId));
      console.log("SERVER RESPONSE - Capital Assets:", JSON.stringify(data, null, 2));
      
      // בדיקה מפורטת של כל נכס
      if (data && data.length > 0) {
        data.forEach((asset, index) => {
          console.log(`ASSET ${index + 1} DETAILS:`);
          console.log(`  ID: ${asset.id}`);
          console.log(`  Name: ${asset.asset_name || asset.description || 'No name'}`);
          console.log(`  Type: ${asset.asset_type}`);
          console.log(`  Monthly Income: ${asset.monthly_income || 0}`);
          console.log(`  Current Value: ${asset.current_value || 0}`);
          console.log(`  Payment Date: ${asset.start_date || 'Not set'}`);
          console.log(`  conversion_source: ${(asset as any).conversion_source || 'NOT SET'}`);
          console.log(`  All Properties:`, asset);
        });
      } else {
        console.log("No assets returned from server");
      }
      
      setAssets(data || []);
    } catch (e: any) {
      console.error("Error loading assets:", e);
      setError(`שגיאה בטעינת נכסי הון: ${e?.message || e}`);
    } finally {
      setLoading(false);
    }
  }

  async function deleteAsset(
    assetId: number,
    options?: { skipConfirm?: boolean; skipReload?: boolean }
  ) {
    console.log('🔴 handleDelete called with assetId:', assetId);
    if (!clientId) {
      console.log('❌ No clientId, returning');
      return;
    }
    
    if (!options?.skipConfirm) {
      if (!confirm("האם אתה בטוח שברצונך למחוק את נכס ההון?")) {
        console.log('❌ User cancelled deletion');
        return;
      }
    }

    console.log('✅ Starting deletion process...');
    try {
      // קבלת פרטי הנכס מהרשימה המקומית
      const asset = assets.find(a => a.id === assetId);

      // חסימה של מחיקת נכס הון שנוצר מהיוון – יש למחוק ממסך הקצבאות
      const isCommutationAsset =
        asset &&
        (
          asset.asset_type === 'deposits' ||
          (asset.description && asset.description.includes('היוון')) ||
          (asset.remarks && asset.remarks.includes('COMMUTATION:')) ||
          ((asset as any).conversion_source && (asset as any).conversion_source.includes('"pension_commutation"'))
        );

      if (isCommutationAsset) {
        alert(
          'לא ניתן למחוק נכס הון שנוצר מהיוון מתוך מסך נכסי הון.\n' +
          'אנא מחק את ההיוון ממסך הקצבאות (טבלת ההיוונים), כדי שהקצבה תשוחזר כראוי.'
        );
        return;
      }

      // מחיקת הנכס והחזרת מידע על שחזור
      const deleteResponse = await apiFetch(apiRoutes.clients.capitalAssetById(clientId, assetId), {
        method: 'DELETE'
      }) as any;
      
      console.log('🗑️ Delete response:', JSON.stringify(deleteResponse, null, 2));
      console.log('🔍 Restoration object:', deleteResponse?.restoration);
      console.log('🔍 Restoration reason:', deleteResponse?.restoration?.reason);
      
      // בדיקה אם צריך לשחזר יתרה לתיק פנסיוני
      if (deleteResponse?.restoration && deleteResponse.restoration.reason === 'pension_portfolio') {
        const accountNumber = deleteResponse.restoration.account_number;
        const balanceToRestore = deleteResponse.restoration.balance_to_restore;
        
        console.log(`📋 ✅ RESTORING ₪${balanceToRestore} to account ${accountNumber}`);
        console.log('🔍 Specific amounts to restore:', deleteResponse.restoration.specific_amounts);
        
        restoreBalanceToPensionPortfolio(clientId, {
          account_number: accountNumber,
          balance_to_restore: balanceToRestore,
          specific_amounts: deleteResponse.restoration.specific_amounts,
        });
      }
      
      // Reload assets after deletion (unless part of bulk delete)
      if (!options?.skipReload) {
        await loadAssets();
      }
    } catch (e: any) {
      setError(`שגיאה במחיקת נכס הון: ${e?.message || e}`);
    }
  }

  async function deleteAllAssets() {
    if (!clientId) return;
    
    if (assets.length === 0) {
      alert("אין נכסי הון למחיקה");
      return;
    }
    
    if (!confirm(`האם אתה בטוח שברצונך למחוק את כל ${assets.length} נכסי ההון? פעולה זו בלתי הפיכה!`)) {
      return;
    }

    try {
      setError("");
      
      // מחיקת כל הנכסים אחד אחד, תוך שימוש בלוגיקת השחזור המלאה
      for (const asset of assets) {
        if (asset.id) {
          await deleteAsset(asset.id, { skipConfirm: true, skipReload: true });
        }
      }

      // רענון הרשימה פעם אחת בסיום
      await loadAssets();
      alert(`נמחקו ${assets.length} נכסי הון בהצלחה`);
    } catch (e: any) {
      setError(`שגיאה במחיקת נכסי הון: ${e?.message || e}`);
    }
  }

  useEffect(() => {
    loadAssets();
  }, [clientId]);

  return {
    assets,
    loading,
    error,
    setError,
    loadAssets,
    deleteAsset,
    deleteAllAssets
  };
}
