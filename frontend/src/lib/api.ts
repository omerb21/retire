const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

function extractMessage(body: any): string | undefined {
  if (!body) return;
  if (typeof body === "string") return body;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    // FastAPI 422 validation shape
    return body.detail.map((d: any) => d.msg || d?.loc?.join(".")).join("; ");
  }
}

async function parseJsonSafe(res: Response) {
  try {
    return await res.clone().json(); // משתמשים ב-clone כדי לא "לשרוף" את ה־body המקורי
  } catch {
    return null;
  }
}

async function parseTextSafe(res: Response) {
  try {
    return await res.clone().text();
  } catch {
    return "";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // ↓ שינוי קריטי שמפסיק הרבה "Failed to fetch"
    credentials: "omit",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  const ct = res.headers.get("content-type") ?? "";
  const isJson = ct.includes("application/json");

  if (!res.ok) {
    const msg = isJson
      ? await res.clone().json().then((b) =>
          typeof b?.detail === "string"
            ? b.detail
            : Array.isArray(b?.detail)
            ? b.detail.map((d: any) => d.msg || d?.loc?.join(".")).join("; ")
            : JSON.stringify(b)
        ).catch(() => "")
      : await res.clone().text().catch(() => "");
    throw new Error(msg || `HTTP ${res.status}`);
  }

  // Handle 204 No Content responses
  if (res.status === 204) {
    return null as T;
  }
  
  return (isJson ? await res.json() : await res.text()) as T;
}

// Helper function to check if error is network-related
function isNetworkError(e: unknown) {
  return e instanceof TypeError && e.message === 'Failed to fetch';
}

export type ClientItem = {
  id?: number;
  id_number: string;
  id_number_raw?: string;
  full_name: string | null;
  first_name?: string | null;
  last_name?: string | null;
  birth_date?: string | null;
  gender?: string | null;
  email?: string | null;
  phone?: string | null;
  pension_start_date?: string | null;
};

export type Paged<T> = { items: T[]; total: number; page: number; page_size: number };

export type ClientCreate = {
  first_name: string;
  last_name: string;
  id_number: string;   // מחרוזת!
  birth_date: string;  // "YYYY-MM-DD"
  gender?: string;      // "male" or "female"
  email?: string | null;
  phone?: string | null;
  address_street?: string | null;
  address_city?: string | null;
  address_postal_code?: string | null;
  pension_start_date?: string | null;
  tax_credit_points?: number | null;
  marital_status?: string | null;
  
  // Tax-related fields
  num_children?: number | null;
  is_new_immigrant?: boolean | null;
  is_veteran?: boolean | null;
  is_disabled?: boolean | null;
  disability_percentage?: number | null;
  is_student?: boolean | null;
  reserve_duty_days?: number | null;
  
  // Income and deductions
  annual_salary?: number | null;
  pension_contributions?: number | null;
  study_fund_contributions?: number | null;
  insurance_premiums?: number | null;
  charitable_donations?: number | null;
  
  // Additional fields
  spouse_income?: number | null;
  immigration_date?: string | null;
  military_discharge_date?: string | null;
};

export async function listClients(params?: { limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set("limit", String(params.limit));
  if (params?.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  const response = await apiFetch<ClientItem[]>(`/clients${qs ? `?${qs}` : ""}`);
  return response;
}

// Helper for valid Israeli ID - EXACT match to backend implementation
function normalizeAndValidateIsraeliId(id: string | null | undefined): {valid: boolean; normalized: string} {
  // Check if input is null or undefined
  if (id === null || id === undefined) {
    return {valid: false, normalized: ""};
  }
  
  // Convert to string if needed
  const idStr = String(id);
  
  // Remove non-digits and trim
  const normalized = idStr.replace(/\D/g, '').trim();
  
  // Check if empty
  if (!normalized) {
    return {valid: false, normalized};
  }
  
  // Zero-pad to 9 digits
  const paddedId = normalized.padStart(9, '0');
  
  // No hardcoded test IDs - rely on proper validation algorithm
  
  // Verify length - MUST be 9 digits
  if (paddedId.length !== 9) {
    return {valid: false, normalized: paddedId};
  }
  
  // Calculate checksum using Israeli algorithm - EXACT match to backend
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    let digit = parseInt(paddedId[i], 10);
    // Even positions (0, 2, 4, 6, 8) get weight 1
    if (i % 2 === 0) {
      sum += digit;
    } 
    // Odd positions (1, 3, 5, 7) get weight 2
    else {
      digit *= 2;
      // If result > 9, sum the digits (equivalent to subtracting 9)
      sum += digit > 9 ? digit - 9 : digit;
    }
  }
  
  return {valid: sum % 10 === 0, normalized: paddedId};
}

export async function createClient(payload: ClientCreate) {
  try {
    // Validate ID before sending to backend
    const idValidation = normalizeAndValidateIsraeliId(payload.id_number);
    
    if (!idValidation.valid) {
      throw new Error("תעודת זהות אינה תקינה");
    }
    
    // Send the original payload with id_number_raw for backend compatibility
    const p = {
      ...payload,
      id_number_raw: payload.id_number // Send original ID as id_number_raw
    };
    
    // Log the payload being sent to verify it contains user input
    console.log('Sending client payload:', p);
    
    return apiFetch<ClientItem>("/clients", {
      method: "POST",
      body: JSON.stringify(p),
    });
  } catch (error) {
    console.error("Error in createClient:", error);
    throw error;
  }
}

export async function getClient(id: number) {
  return apiFetch<ClientItem>(`/clients/${id}`);
}

export const clientApi = {
  create: createClient,
  get: getClient,
  list: listClients
};

export function handleApiError(error: any): string {
  if (error instanceof Error) {
    return error.message;
  }
  return 'שגיאה לא ידועה';
}
