import React, { useEffect, useState } from "react";
import { listClients, createClient, ClientItem } from "../lib/api";

export default function Clients() {
  const [items, setItems] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    id_number_raw: "",
    full_name: "",
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
      if (!form.id_number_raw) throw new Error('חובה למלא ת"ז');
      await createClient({
        id_number_raw: form.id_number_raw.trim(),
        full_name: form.full_name || null,
        email: form.email || null,
        phone: form.phone || null,
      });
      setForm({ id_number_raw: "", full_name: "", email: "", phone: "" });
      setMsg("✅ לקוח נשמר");
      refresh();
    } catch (e: any) {
      setMsg("❌ כשל בשמירה: " + (e?.message || e));
    }
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2>לקוחות</h2>

      <section style={{ display: "grid", gap: 8, maxWidth: 520 }}>
        <h3>פתיחת לקוח חדש</h3>
        <form onSubmit={onCreate} style={{ display: "grid", gap: 8 }}>
          <input placeholder='ת"ז (למשל 123456782)'
                 value={form.id_number_raw}
                 onChange={(e) => setForm({ ...form, id_number_raw: e.target.value })}
                 style={{ padding: 8 }} />
          <input placeholder="שם מלא (אופציונלי)"
                 value={form.full_name}
                 onChange={(e) => setForm({ ...form, full_name: e.target.value })}
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
                <th style={th}>שם</th>
                <th style={th}>Email</th>
                <th style={th}>טלפון</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c, i) => (
                <tr key={`${c.id}-${i}`}>
                  <td style={td}>{c.id ?? ""}</td>
                  <td style={td}>{c.id_number_raw}</td>
                  <td style={td}>{c.full_name ?? ""}</td>
                  <td style={td}>{c.email ?? ""}</td>
                  <td style={td}>{c.phone ?? ""}</td>
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
