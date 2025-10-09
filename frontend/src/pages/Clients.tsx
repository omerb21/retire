import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
    return retirementDate.toISOString().split('T')[0];
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
    birth_date: new Date().toISOString().split('T')[0], // Default to today
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
      // Test direct fetch first
      console.log("Testing direct fetch...");
      const testResponse = await fetch('/api/v1/clients');
      console.log("Direct fetch status:", testResponse.status);
      const testData = await testResponse.json();
      console.log("Direct fetch data:", testData);
      
      const data = await listClients();
      console.log("Clients loaded successfully:", data);
      setItems(data || []);
      setMsg(`✅ טעינה הצליחה! נמצאו ${data?.length || 0} לקוחות`);
    } catch (e: any) {
      console.error("Error loading clients:", e);
      setMsg("שגיאה בטעינת לקוחות: " + (e?.message || e));
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
    }
  }

  function startEdit(client: ClientItem) {
    setEditingClient(client);
    setEditForm({
      id_number: client.id_number || "",
      first_name: client.first_name || "",
      last_name: client.last_name || "",
      birth_date: client.birth_date || "",
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
      
      const response = await fetch(`/api/v1/clients/${editingClient.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id_number: editForm.id_number.trim(),
          first_name: editForm.first_name.trim(),
          last_name: editForm.last_name.trim(),
          birth_date: editForm.birth_date,
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
      
      // Birth date validation (age between 18-120)
      const birthDate = new Date(form.birth_date);
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
        birth_date: form.birth_date,
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
    <div style={{ display: "grid", gap: 16 }}>
      <h2>לקוחות</h2>

      <section style={{ display: "grid", gap: 8, maxWidth: 520 }}>
        <h3>פתיחת לקוח חדש</h3>
        <form onSubmit={onCreate} style={{ display: "grid", gap: 8 }}>
          <input placeholder='ת"ז (למשל 123456782)'
                 value={form.id_number}
                 onChange={(e) => setForm({ ...form, id_number: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="שם פרטי"
                 value={form.first_name}
                 onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="שם משפחה"
                 value={form.last_name}
                 onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                 style={{ padding: 8 }} />
          <input type="date"
                 placeholder="תאריך לידה"
                 value={form.birth_date}
                 onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
                 style={{ padding: 8 }} />
          <select value={form.gender}
                  onChange={(e) => setForm({ ...form, gender: e.target.value })}
                  style={{ padding: 8 }}>
            <option value="male">זכר</option>
            <option value="female">נקבה</option>
          </select>
          <input placeholder="Email (אופציונלי)"
                 value={form.email}
                 onChange={(e) => setForm({ ...form, email: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="טלפון (אופציונלי)"
                 value={form.phone}
                 onChange={(e) => setForm({ ...form, phone: e.target.value })}
                 style={{ padding: 8 }} />
          
          <h4 style={{ marginTop: 16, marginBottom: 8 }}>כתובת</h4>
          <input placeholder="רחוב (אופציונלי)"
                 value={form.address_street}
                 onChange={(e) => setForm({ ...form, address_street: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="עיר (אופציונלי)"
                 value={form.address_city}
                 onChange={(e) => setForm({ ...form, address_city: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="מיקוד (אופציונלי)"
                 value={form.address_postal_code}
                 onChange={(e) => setForm({ ...form, address_postal_code: e.target.value })}
                 style={{ padding: 8 }} />
          
          <h4 style={{ marginTop: 16, marginBottom: 8 }}>נתונים נוספים</h4>
          
          <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
            <label style={{ marginLeft: 8, minWidth: 100 }}>מצב משפחתי:</label>
            <select
              value={form.marital_status}
              onChange={(e) => setForm({ ...form, marital_status: e.target.value })}
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
            <input type="number"
                   placeholder="נקודות זיכוי"
                   value={form.tax_credit_points}
                   onChange={(e) => setForm({ ...form, tax_credit_points: parseFloat(e.target.value) || 0 })}
                   min="0"
                   step="0.1"
                   style={{ padding: 8, flexGrow: 1 }} />
          </div>
          
          <button type="submit" style={{ padding: "10px 14px", marginTop: 16 }}>שמור</button>
        </form>
      </section>

      {msg && <div>{msg}</div>}

      <section style={{ marginTop: 8 }}>
        <h3>רשימת לקוחות</h3>
        {loading ? (
          <div>טוען…</div>
        ) : items.length === 0 ? (
          <div>אין לקוחות</div>
        ) : (
          <table style={{ borderCollapse: "collapse", minWidth: 600, direction: "rtl" }}>
            <thead>
              <tr>
                <th style={th}>#</th>
                <th style={th}>ת"ז</th>
                <th style={th}>שם פרטי</th>
                <th style={th}>שם משפחה</th>
                <th style={th}>תאריך לידה</th>
                <th style={th}>מין</th>
                <th style={th}>Email</th>
                <th style={th}>תאריך קצבה</th>
                <th style={th}>פעולות</th>
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
                  <td style={td}>{c.birth_date ?? ""}</td>
                  <td style={td}>{c.gender === "male" ? "זכר" : "נקבה"}</td>
                  <td style={td}>{c.email ?? ""}</td>
                  <td style={td}>{c.pension_start_date || calculatePensionStartDate(c)}</td>
                  <td style={td}>
                    <Link 
                      to={`/clients/${c.id}`}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: "#f0f0f0",
                        borderRadius: "4px",
                        textDecoration: "none",
                        color: "#333",
                        fontSize: "0.9em",
                        marginLeft: "4px"
                      }}
                    >
                      פתח
                    </Link>
                    <button
                      onClick={() => startEdit(c)}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: "#007bff",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        fontSize: "0.9em",
                        cursor: "pointer",
                        marginLeft: "4px"
                      }}
                    >
                      ערוך
                    </button>
                    <button
                      onClick={() => deleteClient(c.id!)}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: "#ff4444",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        fontSize: "0.9em",
                        cursor: "pointer"
                      }}
                    >
                      מחק
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

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
                type="date"
                placeholder="תאריך לידה"
                value={editForm.birth_date}
                onChange={(e) => setEditForm({ ...editForm, birth_date: e.target.value })}
                style={{ padding: 8 }} 
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
                  step="0.1"
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
  );
}

const th: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 };
const td: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #f0f0f0", padding: 8 };
