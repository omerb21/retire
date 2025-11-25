/**
 * System Snapshot Component
 * כפתורי שמירה ואיפוס מצב מערכת
 */
import React, { useState } from 'react';
import { Button, Box, Typography, Alert, Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import RestoreIcon from '@mui/icons-material/Restore';
import InfoIcon from '@mui/icons-material/Info';
import { API_BASE } from '../lib/api';
import {
  loadPensionDataFromStorage,
  savePensionDataToStorage,
  removePensionDataFromStorage,
  loadConvertedAccountsFromStorage,
  saveConvertedAccountsToStorage,
  removeConvertedAccountsFromStorage,
} from '../pages/PensionPortfolio/services/pensionPortfolioStorageService';
import {
  loadSnapshotRawFromStorage,
  saveSnapshotRawToStorage,
} from '../services/snapshotStorageService';

interface SystemSnapshotProps {
  clientId: number;
  onSnapshotRestored?: () => void;
}

interface SnapshotData {
  client_id: number;
  snapshot_name: string;
  created_at: string;
  data: any;
  pension_portfolio?: any[]; // נתוני התיק הפנסיוני
  converted_accounts?: any[]; // חשבונות שהומרו
}

const SystemSnapshot: React.FC<SystemSnapshotProps> = ({ clientId, onSnapshotRestored }) => {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info', text: string } | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState<SnapshotData | null>(null);

  // טעינת snapshot שמור מ-localStorage
  React.useEffect(() => {
    const stored = loadSnapshotRawFromStorage(clientId);
    if (stored) {
      try {
        setSavedSnapshot(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse saved snapshot', e);
      }
    }
  }, [clientId]);

  const handleSaveSnapshot = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          snapshot_name: `שמירה ידנית ${new Date().toLocaleString('he-IL')}`
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'שגיאה בשמירת המצב');
      }

      const data = await response.json();
      
      const pensionPortfolio = loadPensionDataFromStorage(String(clientId)) || [];
      const convertedAccountsSet = loadConvertedAccountsFromStorage(String(clientId));
      const convertedAccounts = Array.from(convertedAccountsSet);
      
      const snapshotData = {
        ...data.snapshot,
        pension_portfolio: pensionPortfolio,
        converted_accounts: convertedAccounts,
      };

      saveSnapshotRawToStorage(clientId, JSON.stringify(snapshotData));
      setSavedSnapshot(snapshotData);

      setMessage({
        type: 'success',
        text: `✅ ${data.message} - ${data.total_items} פריטים + תיק פנסיוני`
      });

    } catch (error: any) {
      console.error('Save snapshot error:', error);
      setMessage({
        type: 'error',
        text: `❌ שגיאה: ${error.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRestoreSnapshot = async () => {
    if (!savedSnapshot) {
      setMessage({
        type: 'error',
        text: '❌ אין snapshot שמור. אנא שמור מצב תחילה.'
      });
      return;
    }

    setLoading(true);
    setMessage(null);
    setConfirmDialogOpen(false);

    try {
      const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/restore`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(savedSnapshot)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'שגיאה בשחזור המצב');
      }

      const data = await response.json();

      setMessage({
        type: 'success',
        text: `✅ ${data.message}`
      });

      // שחזור נתוני PensionPortfolio מה-snapshot
      if (savedSnapshot.pension_portfolio && Array.isArray(savedSnapshot.pension_portfolio)) {
        savePensionDataToStorage(String(clientId), savedSnapshot.pension_portfolio as any[]);
        console.log(`✅ Restored ${savedSnapshot.pension_portfolio.length} pension accounts to localStorage`);
        console.log('Sample account:', savedSnapshot.pension_portfolio[0]);
      } else {
        removePensionDataFromStorage(String(clientId));
        console.log('⚠️ No pension portfolio data in snapshot');
      }

      if (savedSnapshot.converted_accounts) {
        const convertedSet = new Set<string>(
          (Array.isArray(savedSnapshot.converted_accounts)
            ? savedSnapshot.converted_accounts
            : [savedSnapshot.converted_accounts]
          ).map((id: any) => String(id))
        );
        saveConvertedAccountsToStorage(String(clientId), convertedSet);
      } else {
        removeConvertedAccountsFromStorage(String(clientId));
      }

      // קריאה לפונקציית callback אם קיימת
      if (onSnapshotRestored) {
        onSnapshotRestored();
      }

      // רענון הדף מנוהל ע"י הקומפוננטה העוטפת (callback) כדי לא לשבור את ה-SPA

    } catch (error: any) {
      console.error('Restore snapshot error:', error);
      setMessage({
        type: 'error',
        text: `❌ שגיאה: ${error.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  const openConfirmDialog = () => {
    if (!savedSnapshot) {
      setMessage({
        type: 'error',
        text: '❌ אין snapshot שמור. אנא שמור מצב תחילה.'
      });
      return;
    }
    setConfirmDialogOpen(true);
  };

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleString('he-IL');
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      {/* כפתור שמירה */}
      <Button
        variant="contained"
        color="primary"
        startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
        onClick={handleSaveSnapshot}
        disabled={loading}
      >
        💾 שמור מצב
      </Button>

      {/* כפתור איפוס */}
      <Button
        variant="contained"
        color="warning"
        startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <RestoreIcon />}
        onClick={openConfirmDialog}
        disabled={loading || !savedSnapshot}
      >
        ♻️ שחזר מצב
      </Button>

      {/* מידע על snapshot שמור */}
      {savedSnapshot && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <InfoIcon color="info" fontSize="small" />
          <Typography variant="caption" color="text.secondary">
            נשמר: {formatDate(savedSnapshot.created_at)}
          </Typography>
        </Box>
      )}

      {/* הודעות */}
      {message && (
        <Alert 
          severity={message.type} 
          sx={{ flex: '1 1 100%' }}
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      {/* דיאלוג אישור */}
      <Dialog open={confirmDialogOpen} onClose={() => setConfirmDialogOpen(false)}>
        <DialogTitle>⚠️ אישור שחזור מצב</DialogTitle>
        <DialogContent>
          <Typography>
            פעולה זו תמחק את כל הנתונים הנוכחיים ותשחזר את המצב השמור מתאריך:
          </Typography>
          <Typography variant="h6" sx={{ mt: 2, color: 'primary.main' }}>
            {savedSnapshot && formatDate(savedSnapshot.created_at)}
          </Typography>
          <Typography variant="body2" color="error" sx={{ mt: 2 }}>
            ⚠️ אזהרה: פעולה זו בלתי הפיכה! כל השינויים שבוצעו מאז השמירה ימחקו.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)} color="inherit">
            ביטול
          </Button>
          <Button onClick={handleRestoreSnapshot} variant="contained" color="warning" autoFocus>
            אשר שחזור
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SystemSnapshot;
