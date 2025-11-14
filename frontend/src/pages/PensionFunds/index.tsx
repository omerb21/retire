import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { PensionFund, Commutation } from './types';
import { calculateOriginalBalance } from './utils';
import { 
  loadPensionFunds, 
  loadClientData, 
  computePensionFund,
  deletePensionFund,
  deleteCommutation,
  updatePensionFund,
  updateClientPensionStartDate
} from './api';
import { handleSubmitPensionFund, handleCommutationSubmitLogic } from './handlers';
import { PensionFundForm } from './components/PensionFundForm';
import { PensionFundList } from './components/PensionFundList';
import { CommutationForm } from './components/CommutationForm';
import { CommutationList } from './components/CommutationList';

export default function PensionFunds() {
  const { id: clientId } = useParams<{ id: string }>();
  const [funds, setFunds] = useState<PensionFund[]>([]);
  const [commutations, setCommutations] = useState<Commutation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [clientData, setClientData] = useState<any>(null);
  const [editingFundId, setEditingFundId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<PensionFund>>({
    fund_name: "",
    calculation_mode: "calculated",
    balance: 0,
    annuity_factor: 0,
    indexation_method: "none",
    indexation_rate: 0,
    deduction_file: "",
    pension_start_date: "",
    tax_treatment: "taxable",
  });
  const [commutationForm, setCommutationForm] = useState<Commutation>({
    pension_fund_id: undefined,
    exempt_amount: 0,
    commutation_date: "",
    commutation_type: "taxable",
  });

  // אוטומטית מעדכן את יחס המס של ההיוון כאשר בוחרים קצבה פטורה ממס
  useEffect(() => {
    if (commutationForm.pension_fund_id) {
      const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
      if (selectedFund?.tax_treatment === "exempt") {
        setCommutationForm(prev => ({ ...prev, commutation_type: "exempt" }));
      }
    }
  }, [commutationForm.pension_fund_id, funds]);

  async function loadFunds() {
    if (!clientId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const { funds: loadedFunds, commutations: loadedCommutations } = await loadPensionFunds(clientId);
      setFunds(loadedFunds);
      setCommutations(loadedCommutations);
    } catch (e: any) {
      setError(e?.message || e);
    } finally {
      setLoading(false);
    }
  }

  // טעינת נתוני לקוח
  useEffect(() => {
    if (clientId) {
      const fetchClientData = async () => {
        try {
          const data = await loadClientData(clientId);
          setClientData(data);
        } catch (error) {
          console.error("Error fetching client data:", error);
        }
      };
      
      fetchClientData();
      loadFunds();
    }
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      await handleSubmitPensionFund(clientId, form, editingFundId, funds, clientData);

      // איפוס הטופס
      setForm({
        fund_name: "",
        calculation_mode: "calculated",
        balance: 0,
        annuity_factor: 0,
        indexation_method: "none",
        indexation_rate: 0,
        deduction_file: "",
        pension_start_date: "",
      });
      
      setEditingFundId(null);
      await loadFunds();
    } catch (e: any) {
      setError(`שגיאה ביצירת קצבה: ${e?.message || e}`);
    }
  }

  async function handleCompute(fundId: number) {
    if (!clientId) return;

    try {
      const fund = funds.find(f => f.id === fundId);
      if (!fund) {
        throw new Error("קרן לא נמצאה");
      }
      
      const balance = fund.current_balance || fund.balance || 0;
      const factor = fund.annuity_factor || 0;
      
      if (balance <= 0 || factor <= 0) {
        throw new Error("יתרה ומקדם קצבה חייבים להיות חיוביים");
      }
      
      await computePensionFund(clientId, fundId);
      await loadFunds();
    } catch (e: any) {
      console.error('Compute error:', e);
      setError(`שגיאה בחישוב: ${e?.message || e}`);
    }
  }

  async function handleDeleteAll() {
    if (!clientId) return;
    
    const totalItems = funds.length + commutations.length;
    
    if (totalItems === 0) {
      alert("אין קצבאות או היוונים למחיקה");
      return;
    }
    
    if (!confirm(`האם אתה בטוח שברצונך למחוק את כל ${funds.length} הקצבאות ו-${commutations.length} ההיוונים? פעולה זו בלתי הפיכה!`)) {
      return;
    }

    try {
      setError("");
      
      for (const fund of funds) {
        if (fund.id) {
          await deletePensionFund(clientId, fund.id);
        }
      }
      
      for (const commutation of commutations) {
        if (commutation.id) {
          await deleteCommutation(clientId, commutation.id);
        }
      }
      
      await loadFunds();
      alert(`נמחקו ${funds.length} קצבאות ו-${commutations.length} היוונים בהצלחה`);
    } catch (e: any) {
      setError(`שגיאה במחיקה: ${e?.message || e}`);
    }
  }

  async function handleDelete(fundId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את הקצבה?")) {
      return;
    }

    try {
      const fund = funds.find(f => f.id === fundId);
      
      // מחיקת היוונים מקושרים
      const relatedCommutations = commutations.filter(c => c.pension_fund_id === fundId);
      if (relatedCommutations.length > 0) {
        console.log(`🗑️ Deleting ${relatedCommutations.length} commutations linked to pension fund ${fundId}`);
        for (const commutation of relatedCommutations) {
          if (commutation.id) {
            await deleteCommutation(clientId, commutation.id);
            console.log(`✅ Deleted commutation ${commutation.id}`);
          }
        }
      }
      
      const deleteResponse = await deletePensionFund(clientId, fundId);
      
      alert(`🔥 NEW CODE LOADED! Response: ${JSON.stringify(deleteResponse).substring(0, 200)}`);
      console.log('🗑️ Delete response:', JSON.stringify(deleteResponse, null, 2));
      console.log('🔍 Restoration object:', deleteResponse?.restoration);
      console.log('🔍 Restoration reason:', deleteResponse?.restoration?.reason);
      
      // שחזור יתרה לתיק פנסיוני
      if (deleteResponse?.restoration && deleteResponse.restoration.reason === 'pension_portfolio') {
        const accountNumber = deleteResponse.restoration.account_number;
        const balanceToRestore = deleteResponse.restoration.balance_to_restore;
        
        console.log(`📋 ✅ RESTORING ₪${balanceToRestore} to account ${accountNumber}`);
        
        const storageKey = `pensionData_${clientId}`;
        const storedData = localStorage.getItem(storageKey);
        
        console.log(`🔍 Storage key: ${storageKey}`);
        console.log(`🔍 Stored data exists: ${!!storedData}`);
        
        if (storedData && fund) {
          try {
            const pensionData = JSON.parse(storedData);
            console.log(`🔍 Parsed pension data (${pensionData.length} accounts):`, pensionData);
            
            const accountIndex = pensionData.findIndex((acc: any) => 
              acc.מספר_חשבון === accountNumber
            );
            
            console.log(`🔍 Looking for account: ${accountNumber}`);
            console.log(`🔍 Account found at index: ${accountIndex}`);
            
            if (accountIndex !== -1) {
              const account = pensionData[accountIndex];
              
              console.log(`🔍 Account before restore:`, account);
              console.log(`🔍 Specific amounts to restore:`, deleteResponse.restoration.specific_amounts);
              
              if (deleteResponse.restoration.specific_amounts && 
                  Object.keys(deleteResponse.restoration.specific_amounts).length > 0) {
                Object.entries(deleteResponse.restoration.specific_amounts).forEach(([field, amount]: [string, any]) => {
                  if (account.hasOwnProperty(field)) {
                    account[field] = (parseFloat(account[field]) || 0) + parseFloat(amount);
                    console.log(`✅ Restored ₪${amount} to ${field}`);
                  }
                });
              } else {
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
          console.warn(`⚠️ No stored data or fund info. storedData=${!!storedData}, fund=${!!fund}`);
        }
      }
      
      await loadFunds();
      
      // עדכון תאריך הקצבה הראשונה
      try {
        const updatedFunds = await loadPensionFunds(clientId);
        
        if (updatedFunds.funds && updatedFunds.funds.length > 0) {
          const sortedFunds = [...updatedFunds.funds].sort((a, b) => {
            const dateA = a.pension_start_date || a.start_date || '';
            const dateB = b.pension_start_date || b.start_date || '';
            return dateA.localeCompare(dateB);
          });
          
          const earliestDate = sortedFunds[0].pension_start_date || sortedFunds[0].start_date;
          
          if (earliestDate) {
            await updateClientPensionStartDate(clientId, earliestDate);
            console.log(`תאריך הקצבה הראשונה עודכן ל-${earliestDate}`);
          } else {
            console.error("לא נמצא תאריך קצבה תקין");
          }
        } else {
          await updateClientPensionStartDate(clientId, null);
          console.log("תאריך הקצבה הראשונה נוקה כי אין קצבאות");
        }
      } catch (updateError) {
        console.error("שגיאה בעדכון תאריך הקצבה הראשונה:", updateError);
      }
    } catch (e: any) {
      setError(`שגיאה במחיקת קצבה: ${e?.message || e}`);
    }
  }

  function handleEdit(fund: PensionFund) {
    setEditingFundId(fund.id || null);
    
    setForm({
      fund_name: fund.fund_name || "",
      calculation_mode: fund.input_mode || fund.calculation_mode || "calculated",
      balance: fund.balance || 0,
      annuity_factor: fund.annuity_factor || 0,
      monthly_amount: fund.pension_amount || fund.monthly_amount || 0,
      indexation_method: fund.indexation_method || "none",
      indexation_rate: fund.fixed_index_rate || fund.indexation_rate || 0,
      deduction_file: fund.deduction_file || "",
      pension_start_date: fund.pension_start_date || fund.start_date || "",
      tax_treatment: fund.tax_treatment || "taxable",
    });
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleCancelEdit() {
    setEditingFundId(null);
    setForm({
      fund_name: "",
      calculation_mode: "calculated",
      balance: 0,
      annuity_factor: 0,
      indexation_method: "none",
      indexation_rate: 0,
      deduction_file: "",
      pension_start_date: "",
      tax_treatment: "taxable",
    });
  }

  async function handleCommutationSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientId) return;

    setError("");
    
    try {
      const { shouldDeleteFund, fundBalance, createdAsset } = await handleCommutationSubmitLogic(
        clientId,
        commutationForm,
        funds
      );

      if (!shouldDeleteFund) {
        const selectedFund = funds.find(f => f.id === commutationForm.pension_fund_id);
        const newCommutableBalance = fundBalance - (commutationForm.exempt_amount || 0);
        const annuityFactor = selectedFund?.annuity_factor || 200;
        const newMonthlyAmount = Math.round(newCommutableBalance / annuityFactor);
        
        setFunds(funds.map(f => 
          f.id === commutationForm.pension_fund_id 
            ? { 
                ...f, 
                balance: newCommutableBalance,
                commutable_balance: newCommutableBalance,
                pension_amount: newMonthlyAmount,
                monthly: newMonthlyAmount 
              }
            : f
        ));
      }

      const newCommutation: Commutation = {
        id: (createdAsset as any).id,
        pension_fund_id: commutationForm.pension_fund_id,
        exempt_amount: commutationForm.exempt_amount,
        commutation_date: commutationForm.commutation_date,
        commutation_type: commutationForm.commutation_type,
      };
      
      setCommutations([...commutations, newCommutation]);
      await loadFunds();

      setCommutationForm({
        pension_fund_id: undefined,
        exempt_amount: 0,
        commutation_date: "",
        commutation_type: "taxable",
      });

      alert(`היוון נוצר בהצלחה!\n${shouldDeleteFund ? 'הקצבה נמחקה כולה' : `נותרה יתרה של ₪${(fundBalance - (commutationForm.exempt_amount || 0)).toLocaleString()}`}`);
    } catch (e: any) {
      setError(`שגיאה ביצירת היוון: ${e?.message || e}`);
    }
  }

  async function handleCommutationDelete(commutationId: number) {
    if (!clientId) return;
    
    if (!confirm("האם אתה בטוח שברצונך למחוק את ההיוון? היתרה תוחזר לקצבה.")) {
      return;
    }
    
    try {
      const commutationToDelete = commutations.find(c => c.id === commutationId);
      if (!commutationToDelete) {
        throw new Error("היוון לא נמצא");
      }
      
      const relatedFund = funds.find(f => f.id === commutationToDelete.pension_fund_id);
      if (!relatedFund) {
        throw new Error("הקצבה המקורית לא נמצאה");
      }
      
      const currentBalance = relatedFund.balance || 0;
      const commutationAmount = commutationToDelete.exempt_amount || 0;
      const newBalance = currentBalance + commutationAmount;
      
      const annuityFactor = relatedFund.annuity_factor || 200;
      const newMonthlyAmount = Math.round(newBalance / annuityFactor);
      
      await updatePensionFund(relatedFund.id!, {
        fund_name: relatedFund.fund_name,
        fund_type: relatedFund.fund_type,
        input_mode: relatedFund.input_mode,
        balance: newBalance,
        pension_amount: newMonthlyAmount,
        annuity_factor: annuityFactor,
        pension_start_date: relatedFund.pension_start_date,
        indexation_method: relatedFund.indexation_method || "none"
      });
      
      await deleteCommutation(clientId, commutationId);
      
      setCommutations(commutations.filter(c => c.id !== commutationId));
      
      setFunds(funds.map(f => 
        f.id === relatedFund.id 
          ? { 
              ...f, 
              balance: newBalance,
              commutable_balance: newBalance,
              pension_amount: newMonthlyAmount,
              monthly: newMonthlyAmount 
            }
          : f
      ));
      
      alert(`ההיוון נמחק בהצלחה!\nהיתרה הוחזרה לקצבה: ₪${newBalance.toLocaleString()}\nקצבה חודשית חדשה: ₪${newMonthlyAmount.toLocaleString()}`);
    } catch (e: any) {
      setError(`שגיאה במחיקת היוון: ${e?.message || e}`);
    }
  }

  if (loading) return <div>טוען קצבאות...</div>;

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h1 className="card-title">💰 קצבאות והיוונים</h1>
            <p className="card-subtitle">ניהול קצבאות פנסיוניות והיוונים פטורים ממס</p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={handleDeleteAll}
              className="btn"
              style={{ 
                backgroundColor: '#dc3545', 
                color: 'white',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
              disabled={funds.length === 0 && commutations.length === 0}
            >
              🗑️ מחק הכל
            </button>
            <Link to={`/clients/${clientId}`} className="btn btn-secondary">
              ← חזרה
            </Link>
          </div>
        </div>

        {error && (
          <div style={{ color: "red", marginBottom: 16, padding: 8, backgroundColor: "#fee" }}>
            {error}
          </div>
        )}

        {/* Create Forms - Side by Side */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: 32 }}>
          <PensionFundForm
            form={form}
            setForm={setForm}
            onSubmit={handleSubmit}
            editingFundId={editingFundId}
            onCancelEdit={handleCancelEdit}
            clientData={clientData}
          />

          <CommutationForm
            commutationForm={commutationForm}
            setCommutationForm={setCommutationForm}
            onSubmit={handleCommutationSubmit}
            funds={funds}
          />
        </div>

        {/* Main Content - Two Columns */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {/* Left Column - Pension Funds */}
          <section>
            <h3>רשימת קצבאות</h3>
            <PensionFundList
              funds={funds}
              onCompute={handleCompute}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          </section>

          {/* Right Column - Commutations List */}
          <section>
            <h3>רשימת היוונים</h3>
            <CommutationList
              commutations={commutations}
              funds={funds}
              onDelete={handleCommutationDelete}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
