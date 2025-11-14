/**
 * useCapitalAssets Hook
 * =====================
 * Custom hook for managing capital assets CRUD operations
 */

import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { CapitalAsset } from '../types/capitalAsset';

export function useCapitalAssets(clientId: string | undefined) {
  const [assets, setAssets] = useState<CapitalAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  async function loadAssets() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const data = await apiFetch<CapitalAsset[]>(`/clients/${clientId}/capital-assets/`);
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

  async function deleteAsset(assetId: number) {
    console.log('🔴 handleDelete called with assetId:', assetId);
    if (!clientId) {
      console.log('❌ No clientId, returning');
      return;
    }
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את נכס ההון?")) {
      console.log('❌ User cancelled deletion');
      return;
    }

    console.log('✅ Starting deletion process...');
    try {
      // קבלת פרטי הנכס מהרשימה המקומית
      const asset = assets.find(a => a.id === assetId);
      
      // מחיקת הנכס והחזרת מידע על שחזור
      const deleteResponse = await apiFetch(`/clients/${clientId}/capital-assets/${assetId}`, {
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
        
        // עדכון localStorage - החזרת היתרה לטבלה
        const storageKey = `pensionData_${clientId}`;
        const storedData = localStorage.getItem(storageKey);
        
        console.log(`🔍 Storage key: ${storageKey}`);
        console.log(`🔍 Stored data exists: ${!!storedData}`);
        
        if (storedData && asset) {
          try {
            const pensionData = JSON.parse(storedData);
            console.log(`🔍 Parsed pension data (${pensionData.length} accounts):`, pensionData);
            
            // חיפוש החשבון לפי מספר חשבון
            const accountIndex = pensionData.findIndex((acc: any) => 
              acc.מספר_חשבון === accountNumber
            );
            
            console.log(`🔍 Looking for account: ${accountNumber}`);
            console.log(`🔍 Account found at index: ${accountIndex}`);
            
            if (accountIndex !== -1) {
              // החזרת היתרה לשדות הספציפיים שהומרו
              const account = pensionData[accountIndex];
              
              console.log(`🔍 Account before restore:`, account);
              console.log(`🔍 Specific amounts to restore:`, deleteResponse.restoration.specific_amounts);
              
              // אם יש specific_amounts, נחזיר לשדות הספציפיים
              if (deleteResponse.restoration.specific_amounts && 
                  Object.keys(deleteResponse.restoration.specific_amounts).length > 0) {
                Object.entries(deleteResponse.restoration.specific_amounts).forEach(([field, amount]: [string, any]) => {
                  if (account.hasOwnProperty(field)) {
                    account[field] = (parseFloat(account[field]) || 0) + parseFloat(amount);
                    console.log(`✅ Restored ₪${amount} to ${field}`);
                  }
                });
              } else {
                // אם אין specific_amounts, נחזיר לתגמולים (ברירת מחדל)
                account.תגמולים = (parseFloat(account.תגמולים) || 0) + balanceToRestore;
                console.log(`✅ Restored ₪${balanceToRestore} to תגמולים (default)`);
              }

              // עדכון יתרה כללית בתיק הפנסיוני
              const restoreAmount = Number(balanceToRestore) || 0;
              if (restoreAmount > 0) {
                account.יתרה = (Number(account.יתרה) || 0) + restoreAmount;
              }
              
              console.log(`🔍 Account after restore:`, account);
              localStorage.setItem(storageKey, JSON.stringify(pensionData));
              console.log('✅ Updated pension portfolio in localStorage');
              
              // הפעלת אירוע כדי לעדכן את הטבלה
              window.dispatchEvent(new Event('storage'));
              console.log('✅ Dispatched storage event to refresh table');
            } else {
              console.warn(`⚠️ Account ${accountNumber} not found in pension portfolio`);
              console.warn(`🔍 Available accounts:`, pensionData.map((acc: any) => acc.מספר_חשבון));
            }
          } catch (e) {
            console.error('❌ Error restoring balance to localStorage:', e);
          }
        } else {
          console.warn(`⚠️ No stored data or asset info. storedData=${!!storedData}, asset=${!!asset}`);
        }
      }
      
      // Reload assets after deletion
      await loadAssets();
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
      
      // מחיקת כל הנכסים אחד אחד
      for (const asset of assets) {
        if (asset.id) {
          await apiFetch(`/clients/${clientId}/capital-assets/${asset.id}`, {
            method: 'DELETE'
          });
        }
      }
      
      // רענון הרשימה
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
