/**
 * System Snapshot Component
 * כפתורי שמירה ואיפוס מצב מערכת
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Button, Box, Typography, Alert, Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress, TextField } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import RestoreIcon from '@mui/icons-material/Restore';
import InfoIcon from '@mui/icons-material/Info';
import { API_BASE, getClient, handleApiError, publicChatApi } from '../lib/api';
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
  const [tokenLoading, setTokenLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info', text: string } | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState<SnapshotData | null>(null);
  const [clientIdNumber, setClientIdNumber] = useState<string | null>(null);
  const [tokenBalance, setTokenBalance] = useState<number | null>(null);
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [tokensToAdd, setTokensToAdd] = useState<string>('1000');

  function ensureSystemAccessPassword(): string | null {
    const existing = window.localStorage.getItem('systemAccessPassword');
    if (existing) {
      return existing;
    }

    const entered = window.prompt('נדרשת סיסמת מערכת כדי לטעון טוקנים. הזן סיסמת מערכת:');
    const trimmed = (entered || '').trim();
    if (!trimmed) {
      return null;
    }
    window.localStorage.setItem('systemAccessPassword', trimmed);
    return trimmed;
  }

  // טעינת snapshot שמור מ-localStorage
  useEffect(() => {
    const stored = loadSnapshotRawFromStorage(clientId);
    if (stored) {
      try {
        setSavedSnapshot(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse saved snapshot', e);
      }
    }
  }, [clientId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const client = await getClient(clientId);
        if (!active) return;
        setClientIdNumber(client?.id_number || null);
        setTokenBalance(
          typeof client?.public_chat_token_balance === 'number'
            ? client.public_chat_token_balance
            : null
        );
      } catch (e) {
        if (!active) return;
        console.warn('Failed to fetch client for token management', e);
        setClientIdNumber(null);
        setTokenBalance(null);
      }
    })();

    return () => {
      active = false;
    };
  }, [clientId]);

  async function refreshClientTokenBalance(): Promise<number | null> {
    try {
      const client = await getClient(clientId);
      setClientIdNumber(client?.id_number || null);
      const balance =
        typeof client?.public_chat_token_balance === 'number' ? client.public_chat_token_balance : null;
      setTokenBalance(balance);
      return balance;
    } catch (e) {
      console.warn('Failed to refresh client token balance', e);
      setTokenBalance(null);
      return null;
    }
  }

  async function ensurePublicChatSession(): Promise<{ sessionKey: string; tokenBalance: number } | null> {
    if (!clientIdNumber) {
      setMessage({ type: 'error', text: '❌ לא נמצאה תעודת זהות ללקוח. לא ניתן לטעון קרדיט צ׳אט.' });
      return null;
    }

    try {
      const started = await publicChatApi.start(clientIdNumber);
      const key = started.session_key;
      setSessionKey(key);
      await refreshClientTokenBalance();
      return { sessionKey: key, tokenBalance: started.token_balance };
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${handleApiError(err)}` });
      return null;
    }
  }

  function parsePositiveInt(input: string): number {
    const cleaned = (input || '').replace(/[\s,]/g, '');
    const value = Number.parseInt(cleaned, 10);
    if (!Number.isFinite(value) || Number.isNaN(value) || value <= 0) {
      return 0;
    }
    return value;
  }

  const handleTopUpTokens = async () => {
    if (!ensureSystemAccessPassword()) {
      setMessage({ type: 'error', text: '❌ טעינת טוקנים דורשת סיסמת מערכת.' });
      return;
    }

    const tokens = parsePositiveInt(tokensToAdd);
    if (!tokens) {
      setMessage({ type: 'error', text: '❌ יש להזין מספר טוקנים חיובי (מספר שלם).' });
      return;
    }

    setTokenLoading(true);
    setMessage(null);
    try {
      const existing = sessionKey ? { sessionKey, tokenBalance: tokenBalance ?? 0 } : await ensurePublicChatSession();
      if (!existing) {
        return;
      }

      const res = await publicChatApi.topUp(existing.sessionKey, tokens);
      const refreshedBalance = await refreshClientTokenBalance();
      const displayBalance =
        typeof refreshedBalance === 'number' ? refreshedBalance : res.token_balance;
      setMessage({ type: 'success', text: `✅ נטענו ${tokens.toLocaleString()} טוקנים. יתרה חדשה: ${displayBalance.toLocaleString()}` });
    } catch (err) {
      setMessage({ type: 'error', text: `❌ ${handleApiError(err)}` });
    } finally {
      setTokenLoading(false);
    }
  };

  const handleRefreshTokens = async () => {
    setTokenLoading(true);
    setMessage(null);
    try {
      const s = await ensurePublicChatSession();
      if (s) {
        const balance = await refreshClientTokenBalance();
        if (typeof balance === 'number') {
          setMessage({ type: 'info', text: `ℹ️ יתרת קרדיט נוכחית: ${balance.toLocaleString()}` });
        } else {
          setMessage({ type: 'info', text: `ℹ️ יתרת קרדיט נוכחית: ${s.tokenBalance.toLocaleString()}` });
        }
      }
    } finally {
      setTokenLoading(false);
    }
  };

  const handleSaveSnapshot = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (systemPassword) {
        (headers as any)['X-System-Password'] = systemPassword;
      }

      const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/save`, {
        method: 'POST',
        headers,
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

      if (Array.isArray(pensionPortfolio) && pensionPortfolio.length > 0) {
        const portfolioRes = await fetch(`${API_BASE}/clients/${clientId}/pension-portfolio/save`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ pension_portfolio: pensionPortfolio })
        });

        if (!portfolioRes.ok) {
          const error = await portfolioRes.json().catch(() => null);
          throw new Error(error?.detail || 'שגיאה בשמירת תיק פנסיוני');
        }
      }
      
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
      const systemPassword = window.localStorage.getItem('systemAccessPassword');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (systemPassword) {
        (headers as any)['X-System-Password'] = systemPassword;
      }

      const doRestore = async (payload: any) => {
        const response = await fetch(`${API_BASE}/clients/${clientId}/snapshot/restore`, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const error = await response.json().catch(() => null);
          const detail = (error as any)?.detail || 'שגיאה בשחזור המצב';
          const err: any = new Error(String(detail));
          err.__http_status = response.status;
          throw err;
        }

        return response;
      };

      let response: Response;
      try {
        response = await doRestore(savedSnapshot);
      } catch (e: any) {
        const msg = String(e?.message || 'שגיאה בשחזור המצב');
        const statusCode = Number(e?.__http_status || 0);
        const looksIncomplete =
          msg.includes('snapshot נראה לא שלם') ||
          msg.includes('ישוחזרו') ||
          msg.includes('כדי למנוע מחיקה');

        if (statusCode === 422 && looksIncomplete) {
          const okForce = window.confirm(
            `${msg}\n\nהאם לשחזר בכל זאת? פעולה זו עלולה למחוק נתונים אם ה-snapshot באמת חלקי.`
          );
          if (!okForce) {
            throw e;
          }
          response = await doRestore({ ...(savedSnapshot as any), force_restore: true });
        } else {
          throw e;
        }
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

        if (savedSnapshot.pension_portfolio.length > 0) {
          const portfolioRes = await fetch(`${API_BASE}/clients/${clientId}/pension-portfolio/save`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ pension_portfolio: savedSnapshot.pension_portfolio })
          });

          if (!portfolioRes.ok) {
            const error = await portfolioRes.json().catch(() => null);
            throw new Error(error?.detail || 'שגיאה בשמירת תיק פנסיוני');
          }
        }
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
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button
          variant="contained"
          color="warning"
          startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <RestoreIcon />}
          onClick={openConfirmDialog}
          disabled={loading || !savedSnapshot}
        >
          ♻️ שחזר מצב
        </Button>
        {savedSnapshot && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <InfoIcon color="info" fontSize="small" />
            <Typography variant="caption" color="text.secondary">
              נשמר: {formatDate(savedSnapshot.created_at)}
            </Typography>
          </Box>
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          label="טעינת טוקנים"
          value={tokensToAdd}
          onChange={(e) => setTokensToAdd(e.target.value)}
          disabled={tokenLoading}
          size="small"
          inputProps={{ inputMode: 'numeric' }}
        />
        <Button
          variant="contained"
          color="success"
          onClick={handleTopUpTokens}
          disabled={tokenLoading}
          startIcon={tokenLoading ? <CircularProgress size={18} color="inherit" /> : undefined}
        >
          ➕ טען
        </Button>
        <Button
          variant="outlined"
          color="success"
          onClick={handleRefreshTokens}
          disabled={tokenLoading}
        >
          רענן
        </Button>
        <Typography variant="caption" color="text.secondary">
          יתרה: {tokenBalance != null ? tokenBalance.toLocaleString() : '—'}
        </Typography>
      </Box>

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
