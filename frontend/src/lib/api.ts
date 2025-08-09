const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE || "http://127.0.0.1:8000";

export type ClientItem = {
  id?: number;
  id_number_raw: string;
  full_name: string | null;
  first_name?: string | null;
  last_name?: string | null;
  birth_date?: string | null;
  email?: string | null;
  phone?: string | null;
};

type Paged<T> = { items: T[]; total?: number };

export async function listClients(): Promise<Paged<ClientItem>> {
  const r = await fetch(`${API_BASE}/api/v1/clients?limit=100&offset=0`);
  if (!r.ok) throw new Error(`listClients ${r.status}`);
  return r.json();
}

export async function createClient(payload: {
  id_number_raw: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
}): Promise<ClientItem> {
  const r = await fetch(`${API_BASE}/api/v1/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`createClient ${r.status}: ${t}`);
  }
  return r.json();
}
