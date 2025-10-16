import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { formatDateToDDMMYY, formatDateInput, convertDDMMYYToISO, convertISOToDDMMYY, validateDDMMYY } from '../utils/dateUtils';
import { listClients, createClient, ClientItem } from "../lib/api";

// פונקציה לחישוב תאריך קצבה לפי תאריך לידה ומגדר
function calculatePensionStartDate(client: ClientItem) {
  if (!client.birth_date) return "";
  
  try {
    const birthDate = new Date(client.birth_date);
    const retirementAge = client.gender?.toLowerCase() === "female" ? 62 : 67;
    
    // חישוב תאריך הפרישה
    const retirementDate = new Date(birthDate);
    retirementDate.setFullYear(birthDate.getFullYear() + retirementAge);
    
    // החזרת התאריך בפורמט YYYY-MM-DD
    return formatDateToDDMMYY(retirementDate);
  } catch (error) {
    console.error("Error calculating pension start date:", error);
    return "";
  }
}

export default function Clients() {
  const [items, setItems] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    id_number: "",
    first_name: "",
    last_name: "",
    birth_date: "", // שדה ריק - המשתמש ימלא
    gender: "male", // Default to male
    email: "",
    phone: "",
    address_street: "",
    address_city: "",
    address_postal_code: "",
    pension_start_date: "",
    tax_credit_points: 0,
    marital_status: "", // שדה חדש - מצב משפחתי
  });
  const [msg, setMsg] = useState<string>("");
  const [editingClient, setEditingClient] = useState<ClientItem | null>(null);
  const [editForm, setEditForm] = useState({
    id_number: "",
    first_name: "",
    last_name: "",
    birth_date: "",
    gender: "male",
    email: "",
    phone: "",
    address_street: "",
    address_city: "",
    address_postal_code: "",
    pension_start_date: "",
    tax_credit_points: 0,
    marital_status: "" // שדה חדש - מצב משפחתי
  });

  async function refresh() {
    setLoading(true);
    setMsg("");
    try {
      // נסיון לטעון את הלקוחות עם טיפול בשגיאות משופר
      try {
        const data = await listClients();
        console.log("Clients loaded successfully:", data);
        setItems(data || []);
        setMsg(`✅ טעינה הצליחה! נמצאו ${data?.length || 0} לקוחות`);
      } catch (apiError: any) {
        console.error("Error with listClients API:", apiError);
        
        // נסיון ישיר לשרת עם טיפול בשגיאות מפורט יותר
        try {
          const testResponse = await fetch('/api/v1/clients');
          console.log("Direct fetch status:", testResponse.status);
          
          if (!testResponse.ok) {
            throw new Error(`שגיאת HTTP: ${testResponse.status} ${testResponse.statusText}`);
          }
          
          // נסיון לקרוא את התגובה כ-JSON עם טיפול בשגיאות
          try {
            const testData = await testResponse.text();
            console.log("Raw response:", testData);
            
            if (testData) {
              try {
                const jsonData = JSON.parse(testData);
                console.log("Parsed JSON data:", jsonData);
                setItems(jsonData || []);
                setMsg(`✅ טעינה הצליחה! נמצאו ${jsonData?.length || 0} לקוחות`);
              } catch (jsonError) {
                console.error("JSON parsing error:", jsonError);
                setMsg(`שגיאה בפענוח תגובת השרת: תגובה לא תקינה`);
              }
            } else {
              setMsg("שגיאה: התקבלה תגובה ריקה מהשרת");
            }
          } catch (textError) {
            console.error("Error reading response text:", textError);
            setMsg("שגיאה בקריאת תגובת השרת");
          }
        } catch (fetchError: any) {
          console.error("Direct fetch error:", fetchError);
          setMsg("שגיאת חיבור לשרת: " + (fetchError?.message || fetchError));
        }
      }
    } catch (e: any) {
      console.error("Unhandled error in refresh:", e);
      setMsg("שגיאה כללית בטעינת לקוחות: " + (e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function deleteClient(clientId: number) {
    if (!confirm("האם אתה בטוח שברצונך למחוק לקוח זה?")) {
      return;
    }
    
    try {
      setMsg("");
      const response = await fetch(`/api/v1/clients/${clientId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      setMsg("✅ לקוח נמחק בהצלחה");
      refresh();
    } catch (e: any) {
      console.error("Delete error:", e);
      setMsg(`❌ שגיאה במחיקת לקוח: ${e.message}`);
    }
  }

  function startEdit(client: ClientItem) {
    setEditingClient(client);
    setEditForm({
      id_number: client.id_number || "",
      first_name: client.first_name || "",
      last_name: client.last_name || "",
      birth_date: client.birth_date ? convertISOToDDMMYY(client.birth_date) : "",
      gender: client.gender || "male",
      email: client.email || "",
      phone: client.phone || "",
      address_street: (client as any).address_street || "",
      address_city: (client as any).address_city || "",
      address_postal_code: (client as any).address_postal_code || "",
      pension_start_date: "", // שדה לא בשימוש - יחושב אוטומטית לפי גיל פרישה
      tax_credit_points: (client as any).tax_credit_points || 0,
      marital_status: (client as any).marital_status || ""
    });
  }

  function cancelEdit() {
    setEditingClient(null);
    setEditForm({
      id_number: "",
      first_name: "",
      last_name: "",
      birth_date: "",
      gender: "male",
      email: "",
      phone: "",
      address_street: "",
      address_city: "",
      address_postal_code: "",
      pension_start_date: "",
      tax_credit_points: 0,
      marital_status: ""
    });
  }

  async function saveEdit() {
    if (!editingClient) return;
    
    try {
      setMsg("");
      
      // Basic validation
      if (!editForm.id_number) throw new Error('חובה למלא ת"ז');
      if (!editForm.first_name) throw new Error('חובה למלא שם פרטי');
      if (!editForm.last_name) throw new Error('חובה למלא שם משפחה');
      if (!editForm.birth_date) throw new Error('חובה למלא תאריך לידה');
      
      // Convert birth_date from DD/MM/YYYY to ISO format
      const birthDateISO = convertDDMMYYToISO(editForm.birth_date);
      if (!birthDateISO) {
        throw new Error('תאריך לידה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }
      
      const response = await fetch(`/api/v1/clients/${editingClient.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id_number: editForm.id_number.trim(),
          first_name: editForm.first_name.trim(),
          last_name: editForm.last_name.trim(),
          birth_date: birthDateISO,
          gender: editForm.gender,
          email: editForm.email || null,
          phone: editForm.phone || null,
          address_street: editForm.address_street || null,
          address_city: editForm.address_city || null,
          address_postal_code: editForm.address_postal_code || null,
          pension_start_date: null, // שדה לא בשימוש - יחושב אוטומטית לפי גיל פרישה
          tax_credit_points: editForm.tax_credit_points || 0,
          marital_status: editForm.marital_status || null
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      setMsg("✅ פרטי לקוח עודכנו בהצלחה");
      cancelEdit();
      refresh();
    } catch (e: any) {
      console.error("Update error:", e);
      setMsg("❌ כשל בעדכון לקוח: " + (e?.message || e));
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      // Basic field validation
      if (!form.id_number) throw new Error('חובה למלא ת"ז');
      if (!form.first_name) throw new Error('חובה למלא שם פרטי');
      if (!form.last_name) throw new Error('חובה למלא שם משפחה');
      if (!form.birth_date) throw new Error('חובה למלא תאריך לידה');
      
      // Convert birth_date from DD/MM/YYYY to ISO format
      const birthDateISO = convertDDMMYYToISO(form.birth_date);
      if (!birthDateISO) {
        throw new Error('תאריך לידה לא תקין - יש להזין בפורמט DD/MM/YYYY');
      }
      
      // Birth date validation (age between 18-120)
      const birthDate = new Date(birthDateISO);
      const today = new Date();
      
      // Calculate min and max birth dates
      const minBirthDate = new Date();
      minBirthDate.setFullYear(today.getFullYear() - 120); // 120 years ago
      
      const maxBirthDate = new Date();
      maxBirthDate.setFullYear(today.getFullYear() - 18); // 18 years ago
      
      if (birthDate > maxBirthDate) {
        throw new Error('תאריך לידה לא הגיוני - גיל חייב להיות לפחות 18');
      }
      
      if (birthDate < minBirthDate) {
        throw new Error('תאריך לידה לא הגיוני - גיל מקסימלי הוא 120');
      }
      
      // Log the form data being sent
      console.log('Sending client data:', form);
      
      // Send the client data to the API
      await createClient({
        id_number: form.id_number.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        birth_date: birthDateISO,
        gender: form.gender,
        email: form.email || null,
        phone: form.phone || null,
        address_street: form.address_street || null,
        address_city: form.address_city || null,
        address_postal_code: form.address_postal_code || null,
        pension_start_date: null, // שדה לא בשימוש - יחושב אוטומטית לפי גיל פרישה
        tax_credit_points: form.tax_credit_points || 0,
        marital_status: form.marital_status || null,
      });
      
      // Reset form after successful submission
      setForm({
        id_number: "",
        first_name: "",
        last_name: "",
        birth_date: "", // Clear birth date field
        gender: "male", // Reset to default
        email: "",
        phone: "",
        address_street: "",
        address_city: "",
        address_postal_code: "",
        pension_start_date: "",
        tax_credit_points: 0,
        marital_status: "", // איפוס מצב משפחתי
      });
      
      setMsg("✅ לקוח נשמר");
      refresh();
    } catch (e: any) {
      setMsg("❌ כשל בשמירה: " + (e?.message || e));
    }
  }

  // Removed handleClientClick function - using React Router Link instead

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h2 className="card-title">ניהול לקוחות</h2>
            <p className="card-subtitle">צפייה וניהול של כל הלקוחות במערכת</p>
          </div>
        </div>

      {/* Container for three columns */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, alignItems: "start" }}>
        
        {/* Column 1: פתיחת לקוח חדש */}
        <section>
          <h3 style={{ marginBottom: '1rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>פתיחת לקוח חדש</h3>
          <form onSubmit={onCreate} className="grid" style={{ gap: '1rem' }}>
            <input 
              placeholder='ת"ז (למשל 123456782)'
              value={form.id_number}
              onChange={(e) => setForm({ ...form, id_number: e.target.value })}
              className="form-input" 
            />
            <input 
              placeholder="שם פרטי"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              className="form-input" 
            />
            <input 
              placeholder="שם משפחה"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              className="form-input" 
            />
            <input 
              type="text"
              placeholder="תאריך לידה (DD/MM/YYYY)"
              value={form.birth_date}
              onChange={(e) => {
                const formatted = formatDateInput(e.target.value);
                setForm({ ...form, birth_date: formatted });
              }}
              className="form-input"
              maxLength={10} 
            />
            <select 
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value })}
              className="form-select"
            >
              <option value="male">זכר</option>
              <option value="female">נקבה</option>
            </select>
            <input 
              placeholder="Email (אופציונלי)"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="form-input" 
            />
            <input 
              placeholder="טלפון (אופציונלי)"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="form-input" 
            />
            
            <button type="submit" className="btn btn-success" style={{ marginTop: '0.5rem' }}>
              שמור לקוח
            </button>
          </form>
        </section>

        {/* Column 2: כתובת */}
        <section>
          <h3 style={{ marginBottom: '1rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>כתובת</h3>
          <div className="grid" style={{ gap: '1rem' }}>
            <input 
              placeholder="רחוב (אופציונלי)"
              value={form.address_street}
              onChange={(e) => setForm({ ...form, address_street: e.target.value })}
              className="form-input" 
            />
            <input 
              placeholder="עיר (אופציונלי)"
              value={form.address_city}
              onChange={(e) => setForm({ ...form, address_city: e.target.value })}
              className="form-input" 
            />
            <input 
              placeholder="מיקוד (אופציונלי)"
              value={form.address_postal_code}
              onChange={(e) => setForm({ ...form, address_postal_code: e.target.value })}
              className="form-input" 
            />
          </div>
        </section>

        {/* Column 3: נתונים נוספים */}
        <section>
          <h3 style={{ marginBottom: '1rem', color: 'var(--gray-700)', fontSize: '1.25rem' }}>נתונים נוספים</h3>
          <div className="grid" style={{ gap: '1rem' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">מצב משפחתי:</label>
              <select
                value={form.marital_status}
                onChange={(e) => setForm({ ...form, marital_status: e.target.value })}
                className="form-select"
              >
                <option value="">בחר מצב משפחתי</option>
                <option value="single">רווק/ה</option>
                <option value="married">נשוי/ה</option>
                <option value="divorced">גרוש/ה</option>
                <option value="widowed">אלמן/ה</option>
              </select>
            </div>
            
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">נקודות זיכוי:</label>
              <input 
                type="number"
                placeholder="נקודות זיכוי"
                value={form.tax_credit_points}
                onChange={(e) => setForm({ ...form, tax_credit_points: parseFloat(e.target.value) || 0 })}
                min="0"
                step="0.01"
                className="form-input" 
              />
            </div>
          </div>
        </section>
      </div>

      {msg && (
        <div className={msg.includes('✅') ? 'alert alert-success' : 'alert alert-error'}>
          {msg}
        </div>
      )}

      <div className="modern-card" style={{ marginTop: '2rem' }}>
        <div className="card-header">
          <h3 className="card-title">רשימת לקוחות</h3>
        </div>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
            <div className="spinner"></div>
          </div>
        ) : items.length === 0 ? (
          <div className="alert alert-info">אין לקוחות במערכת</div>
        ) : (
          <table className="modern-table">
            <thead>
              <tr>
                <th>#</th>
                <th>ת"ז</th>
                <th>שם פרטי</th>
                <th>שם משפחה</th>
                <th>תאריך לידה</th>
                <th>מין</th>
                <th>Email</th>
                <th>פעולות</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c, i) => (
                <tr key={`${c.id}-${i}`}>
                  <td style={td}>{c.id ?? ""}</td>
                  <td style={td}>{c.id_number ?? ""}</td>
                  <td style={td}>
                    <Link to={`/clients/${c.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                      {c.first_name ?? ""}
                    </Link>
                  </td>
                  <td style={td}>
                    <Link to={`/clients/${c.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                      {c.last_name ?? ""}
                    </Link>
                  </td>
                  <td style={td}>{c.birth_date ? formatDateToDDMMYY(new Date(c.birth_date)) : ""}</td>
                  <td style={td}>{c.gender === "male" ? "זכר" : "נקבה"}</td>
                  <td style={td}>{c.email ?? ""}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                      <Link 
                        to={`/clients/${c.id}`}
                        className="btn btn-primary"
                        style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                      >
                        פתח
                      </Link>
                      <button
                        onClick={() => startEdit(c)}
                        className="btn btn-secondary"
                        style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                      >
                        ערוך
                      </button>
                      <button
                        onClick={() => deleteClient(c.id!)}
                        className="btn btn-danger"
                        style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                      >
                        מחק
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editingClient && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: "white",
            padding: "20px",
            borderRadius: "8px",
            minWidth: "400px",
            maxWidth: "500px",
            direction: "rtl"
          }}>
            <h3>עריכת פרטי לקוח</h3>
            <div style={{ display: "grid", gap: "12px" }}>
              <input 
                placeholder='ת"ז'
                value={editForm.id_number}
                onChange={(e) => setEditForm({ ...editForm, id_number: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                placeholder="שם פרטי"
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                placeholder="שם משפחה"
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                type="text"
                placeholder="DD/MM/YYYY"
                value={editForm.birth_date}
                onChange={(e) => {
                  const formatted = formatDateInput(e.target.value);
                  setEditForm({ ...editForm, birth_date: formatted });
                }}
                style={{ padding: 8 }}
                maxLength={10} 
              />
              <select 
                value={editForm.gender}
                onChange={(e) => setEditForm({ ...editForm, gender: e.target.value })}
                style={{ padding: 8 }}
              >
                <option value="male">זכר</option>
                <option value="female">נקבה</option>
              </select>
              <input 
                placeholder="Email (אופציונלי)"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                placeholder="טלפון (אופציונלי)"
                value={editForm.phone}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                style={{ padding: 8 }} 
              />
              <h4 style={{ marginTop: 16, marginBottom: 8 }}>כתובת</h4>
              <input 
                placeholder="רחוב (אופציונלי)"
                value={editForm.address_street}
                onChange={(e) => setEditForm({ ...editForm, address_street: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                placeholder="עיר (אופציונלי)"
                value={editForm.address_city}
                onChange={(e) => setEditForm({ ...editForm, address_city: e.target.value })}
                style={{ padding: 8 }} 
              />
              <input 
                placeholder="מיקוד (אופציונלי)"
                value={editForm.address_postal_code}
                onChange={(e) => setEditForm({ ...editForm, address_postal_code: e.target.value })}
                style={{ padding: 8 }} 
              />
              
              <h4 style={{ marginTop: 16, marginBottom: 8 }}>נתונים נוספים</h4>
              
              <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
                <label style={{ marginLeft: 8, minWidth: 100 }}>מצב משפחתי:</label>
                <select
                  value={editForm.marital_status}
                  onChange={(e) => setEditForm({ ...editForm, marital_status: e.target.value })}
                  style={{ padding: 8, flexGrow: 1 }}
                >
                  <option value="">בחר מצב משפחתי</option>
                  <option value="single">רווק/ה</option>
                  <option value="married">נשוי/ה</option>
                  <option value="divorced">גרוש/ה</option>
                  <option value="widowed">אלמן/ה</option>
                </select>
              </div>
              
              {/* שדה תאריך התחלת קצבה הוסר לפי דרישה */}
              
              <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
                <label style={{ marginLeft: 8 }}>נקודות זיכוי:</label>
                <input 
                  type="number"
                  placeholder="נקודות זיכוי"
                  value={editForm.tax_credit_points}
                  onChange={(e) => setEditForm({ ...editForm, tax_credit_points: parseFloat(e.target.value) || 0 })}
                  min="0"
                  step="0.01"
                  style={{ padding: 8, flexGrow: 1 }} 
                />
              </div>
              
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: 16 }}>
                <button 
                  onClick={cancelEdit}
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "#6c757d",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer"
                  }}
                >
                  ביטול
                </button>
                <button 
                  onClick={saveEdit}
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "#28a745",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer"
                  }}
                >
                  שמור
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

const th: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 };
const td: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #f0f0f0", padding: 8 };
