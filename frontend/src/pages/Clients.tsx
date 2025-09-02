import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listClients, createClient, ClientItem } from "../lib/api";

export default function Clients() {
  const [items, setItems] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    id_number: "",
    first_name: "",
    last_name: "",
    birth_date: new Date().toISOString().split('T')[0], // Default to today
    email: "",
    phone: "",
  });
  const [msg, setMsg] = useState<string>("");

  async function refresh() {
    setLoading(true);
    setMsg("");
    try {
      const data = await listClients();
      setItems(data.items || []);
    } catch (e: any) {
      setMsg("שגיאה בטעינת לקוחות: " + (e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

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
        email: form.email || null,
        phone: form.phone || null,
      });
      
      // Reset form after successful submission
      setForm({
        id_number: "",
        first_name: "",
        last_name: "",
        birth_date: "", // Clear birth date field
        email: "",
        phone: "",
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
          <input placeholder="Email (אופציונלי)"
                 value={form.email}
                 onChange={(e) => setForm({ ...form, email: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="טלפון (אופציונלי)"
                 value={form.phone}
                 onChange={(e) => setForm({ ...form, phone: e.target.value })}
                 style={{ padding: 8 }} />
          <button type="submit" style={{ padding: "10px 14px" }}>שמור</button>
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
                <th style={th}>Email</th>
                <th style={th}>טלפון</th>
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
                  <td style={td}>{c.email ?? ""}</td>
                  <td style={td}>
                    <Link 
                      to={`/clients/${c.id}`}
                      style={{
                        padding: "4px 8px",
                        backgroundColor: "#f0f0f0",
                        borderRadius: "4px",
                        textDecoration: "none",
                        color: "#333",
                        fontSize: "0.9em"
                      }}
                    >
                      פתח
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

const th: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #ddd", padding: 8 };
const td: React.CSSProperties = { textAlign: "right", borderBottom: "1px solid #f0f0f0", padding: 8 };
