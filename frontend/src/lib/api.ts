function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim();
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

function sanitizeEnvUrl(value: string | undefined): string | undefined {
  if (!value) {
    return value;
  }

  const trimmed = value.trim();
  const hasDoubleQuotes = trimmed.startsWith('"') && trimmed.endsWith('"');
  const hasSingleQuotes = trimmed.startsWith("'") && trimmed.endsWith("'");

  if (hasDoubleQuotes || hasSingleQuotes) {
    return trimmed.slice(1, -1).trim();
  }

  return trimmed;
}

function upgradeToHttpsInSecureContext(url: string): string {
  const trimmed = url.trim();

  if (typeof window === "undefined") {
    return trimmed;
  }

  if (window.location.protocol !== "https:") {
    return trimmed;
  }

  if (trimmed.startsWith("//")) {
    return `https:${trimmed}`;
  }

  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "http:") {
      parsed.protocol = "https:";
      return parsed.toString();
    }
  } catch {
    // ignore invalid absolute URLs (e.g. relative URLs)
  }

  if (trimmed.toLowerCase().startsWith("http://")) {
    return `https://${trimmed.slice("http://".length)}`;
  }

  return trimmed;
}

const explicitApiBase = sanitizeEnvUrl(
  import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL
);

const apiBaseFromUrl = sanitizeEnvUrl(import.meta.env.VITE_API_URL)
  ? `${normalizeBaseUrl(sanitizeEnvUrl(import.meta.env.VITE_API_URL) as string)}/api/v1`
  : undefined;

export const API_BASE = normalizeBaseUrl(
  upgradeToHttpsInSecureContext(explicitApiBase ?? apiBaseFromUrl ?? "/api/v1")
);

const SYSTEM_ACCESS_STORAGE_KEY = "systemAccessPassword";

function getSystemAccessPassword(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(SYSTEM_ACCESS_STORAGE_KEY);
  } catch {
    return null;
  }
}

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
  try {
    const method = init?.method || 'GET';
    const isFormData = init?.body instanceof FormData;
    const customHeaders = init?.headers;
    const headers = new Headers(customHeaders as HeadersInit | undefined);

    if (!isFormData && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const systemPassword = getSystemAccessPassword();
    if (systemPassword && !headers.has("X-System-Password")) {
      headers.set("X-System-Password", systemPassword);
    }

    const res = await fetch(`${API_BASE}${path}`, {
      credentials: "omit",
      ...init,
      headers,
    });

    const ct = res.headers.get("content-type") ?? "";
    const isJson = ct.includes("application/json");

    if (!res.ok) {
      let errorMsg = "";
      
      try {
        if (isJson) {
          const errorBody = await res.clone().text();
          console.log(`Error response body: ${errorBody}`);
          
          try {
            const parsedBody = JSON.parse(errorBody);
            errorMsg = typeof parsedBody?.detail === "string"
              ? parsedBody.detail
              : Array.isArray(parsedBody?.detail)
              ? parsedBody.detail.map((d: any) => d.msg || d?.loc?.join(".")).join("; ")
              : JSON.stringify(parsedBody);
          } catch (jsonError) {
            console.error("Error parsing JSON error response:", jsonError);
            errorMsg = errorBody || `HTTP ${res.status} ${res.statusText}`;
          }
        } else {
          errorMsg = await res.clone().text().catch(() => "") || `HTTP ${res.status} ${res.statusText}`;
        }
      } catch (parseError) {
        console.error("Error parsing error response:", parseError);
        errorMsg = `HTTP ${res.status} ${res.statusText}`;
      }
      
      throw new Error(errorMsg || `HTTP ${res.status} ${res.statusText}`);
    }

    // Handle 204 No Content responses
    if (res.status === 204) {
      return null as T;
    }
    
    if (isJson) {
      try {
        // First get the raw text to debug any JSON parsing issues
        const rawText = await res.clone().text();
        console.log(`Raw response text (first 100 chars): ${rawText.substring(0, 100)}${rawText.length > 100 ? '...' : ''}`);
        
        // Then try to parse as JSON
        const data = await res.json() as T;
        
        // Note: Balance restoration is now handled in CapitalAssets.tsx and PensionFunds.tsx
        // to avoid double restoration. The restoration info is still returned in the response.
        
        return data;
      } catch (jsonError) {
        console.error("JSON parsing error:", jsonError);
        throw new Error(`Failed to parse JSON response: ${jsonError}`);
      }
    } else {
      return await res.text() as T;
    }
  } catch (fetchError) {
    console.error(`API Fetch error for ${path}:`, fetchError);
    throw fetchError;
  }
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
  public_chat_token_balance?: number | null;
  public_chat_tokens_spent?: number | null;
  public_chat_credit_initialized?: boolean | null;
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

export async function getClientPensionFunds(clientId: number) {
  return apiFetch<any[]>(`/clients/${clientId}/pension-funds`);
}

export const clientApi = {
  create: createClient,
  get: getClient,
  list: listClients,
  getPensionFunds: getClientPensionFunds
};

// ===== Scenarios API (used by Scenarios.tsx) =====

export type ScenarioDto = {
  id: number;
  client_id: number;
  name: string;
  description?: string | null;
  parameters?: string;
  cashflow_projection?: string | null;
  summary_results?: string | null;
  created_at: string;
};

export async function listScenarios(clientId: number) {
  return apiFetch<ScenarioDto[]>(`/clients/${clientId}/scenarios`);
}

export async function createScenario(clientId: number, payload: { name: string; description?: string }) {
  return apiFetch<ScenarioDto>(`/clients/${clientId}/scenarios`, {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? null,
    }),
  });
}

export const scenarioApi = {
  list: listScenarios,
  create: createScenario,
};

// ===== Calculation API (used by Scenarios.tsx -> Results.tsx) =====

export type CalculationRequestDto = {
  client_id: number;
  scenario_name?: string;
  save_scenario?: boolean;
  scenario_id?: number;
};

export type CalculationCashFlowItemDto = {
  year: number;
  month: number;
  gross_income: number;
  tax_amount: number;
  net_income: number;
  asset_balances: Record<string, number>;
};

export type CalculationSummaryDto = {
  total_gross: number;
  total_tax: number;
  total_net: number;
  final_balances: Record<string, number>;
};

export type CalculationResultDto = {
  client_id: number;
  scenario_name?: string;
  case_number: number;
  assumptions: any;
  cash_flow: CalculationCashFlowItemDto[];
  summary: CalculationSummaryDto;
};

export async function runCalculation(payload: CalculationRequestDto) {
  return apiFetch<CalculationResultDto>(`/calculation/run`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const calculationApi = {
  calculate: runCalculation,
};

// ===== Reports API (PDF export used in Results.tsx) =====

async function downloadBlob(path: string, init?: RequestInit) {
  const customHeaders = init?.headers;
  const headers = new Headers(customHeaders as HeadersInit | undefined);

  const systemPassword = getSystemAccessPassword();
  if (systemPassword && !headers.has("X-System-Password")) {
    headers.set("X-System-Password", systemPassword);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "omit",
    ...init,
    headers,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status} ${res.statusText}`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || "report.pdf";

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function exportReportPdf(clientId: number, scenarioIds: number[]) {
  if (!scenarioIds.length) {
    throw new Error("No scenarios selected for PDF export");
  }

  const body = {
    from: "2025-01",
    to: "2025-12",
    frequency: "monthly",
    scenarios: scenarioIds,
  };

  const firstScenarioId = scenarioIds[0];
  const qs = new URLSearchParams({ client_id: String(clientId) }).toString();
  await downloadBlob(`/scenarios/${firstScenarioId}/report/pdf?${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const reportsApi = {
  exportReportPdf,
};

// ===== LLM Pension Chat API =====

export type LlmChatMessageDto = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type LlmChatResponseDto = {
  reply: string;
};

export type LlmStatusDto = {
  provider: string | null;
  backend: string | null;
  model_name: string | null;
};

// סוג לחשבון פנסיוני מהתיק (לשליחה ל-LLM)
export type LlmPensionPortfolioAccount = {
  מספר_חשבון?: string;
  שם_תכנית?: string;
  חברה_מנהלת?: string;
  סוג_מוצר?: string;
  יתרה?: number;
  תאריך_התחלה?: string;
  פיצויים_מעסיק_נוכחי?: number;
  פיצויים_ממעסיקים_קודמים_רצף_קצבה?: number;
  תגמולי_עובד_עד_2000?: number;
  תגמולי_עובד_אחרי_2000?: number;
  תגמולי_מעביד_עד_2000?: number;
  תגמולי_מעביד_אחרי_2000?: number;
  תגמולים?: number;
  סך_תגמולים?: number;
  סך_פיצויים?: number;
  [key: string]: unknown;
};

export async function sendPensionChat(
  messages: LlmChatMessageDto[],
  clientId?: number,
  pensionPortfolio?: LlmPensionPortfolioAccount[],
): Promise<LlmChatResponseDto> {
  const body: any = { messages };
  if (typeof clientId === "number" && !Number.isNaN(clientId)) {
    body.client_id = clientId;
  }
  if (pensionPortfolio && pensionPortfolio.length > 0) {
    body.pension_portfolio = pensionPortfolio;
  }

  return apiFetch<LlmChatResponseDto>("/llm/pension-chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getLlmStatus(): Promise<LlmStatusDto> {
  return apiFetch<LlmStatusDto>("/llm/status");
}

export async function updateLlmProvider(
  provider: string,
  modelName?: string,
): Promise<LlmStatusDto> {
  const body: any = { provider };
  if (modelName && modelName.trim()) {
    body.model_name = modelName.trim();
  }

  return apiFetch<LlmStatusDto>("/llm/provider", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function* sendPensionChatStream(
  messages: LlmChatMessageDto[],
  clientId?: number,
  pensionPortfolio?: LlmPensionPortfolioAccount[],
): AsyncGenerator<string, void, unknown> {
  const body: any = { messages };
  if (typeof clientId === "number" && !Number.isNaN(clientId)) {
    body.client_id = clientId;
  }
  if (pensionPortfolio && pensionPortfolio.length > 0) {
    body.pension_portfolio = pensionPortfolio;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const password = localStorage.getItem("systemAccessPassword");
  if (password) {
    headers["X-System-Password"] = password;
  }

  const response = await fetch(`${API_BASE}/llm/pension-chat-stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`שגיאה בשרת: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("לא ניתן לקרוא את התשובה");
  }

  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    if (text) {
      yield text;
    }
  }
}

export const llmApi = {
  chat: sendPensionChat,
  chatStream: sendPensionChatStream,
  status: getLlmStatus,
  updateProvider: updateLlmProvider,
};

// ===== Public Chat API =====

export type PublicChatStartResponseDto = {
  session_key: string;
  client_id: number;
  client_name: string | null;
  token_balance: number;
  llm_provider?: string | null;
  llm_backend?: string | null;
  llm_model_name?: string | null;
};

export type PublicChatStatusDto = {
  session_key: string;
  client_id: number;
  client_name: string | null;
  token_balance: number;
  tokens_spent: number;
  is_active: boolean;
  llm_provider?: string | null;
  llm_backend?: string | null;
  llm_model_name?: string | null;
};

export type PublicChatMessageDto = {
  role: "user" | "assistant" | "system";
  content: string;
  estimated_tokens?: number;
};

export type PublicChatHistoryDto = {
  session_key: string;
  messages: PublicChatMessageDto[];
};

export type PublicChatSendMessageResponseDto = {
  reply: string;
  token_balance: number;
  tokens_spent: number;
  tokens_used: number;
  depleted: boolean;
};

export type PublicChatTopUpResponseDto = {
  session_key: string;
  token_balance: number;
  tokens_spent: number;
};

export async function startPublicChat(idNumber: string, initialTokens?: number) {
  const body: any = { id_number: idNumber };
  if (typeof initialTokens === "number" && !Number.isNaN(initialTokens)) {
    body.initial_tokens = initialTokens;
  }
  return apiFetch<PublicChatStartResponseDto>("/public-chat/start", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getPublicChatStatus(sessionKey: string) {
  return apiFetch<PublicChatStatusDto>(`/public-chat/sessions/${sessionKey}/status`);
}

export async function getPublicChatHistory(sessionKey: string) {
  return apiFetch<PublicChatHistoryDto>(`/public-chat/sessions/${sessionKey}/history`);
}

export async function sendPublicChatMessage(sessionKey: string, content: string) {
  return apiFetch<PublicChatSendMessageResponseDto>(`/public-chat/sessions/${sessionKey}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function topUpPublicChat(sessionKey: string, tokens: number) {
  return apiFetch<PublicChatTopUpResponseDto>("/public-chat/topup", {
    method: "POST",
    body: JSON.stringify({ session_key: sessionKey, tokens }),
  });
}

export const publicChatApi = {
  start: startPublicChat,
  status: getPublicChatStatus,
  history: getPublicChatHistory,
  sendMessage: sendPublicChatMessage,
  topUp: topUpPublicChat,
};

export function handleApiError(error: any): string {
  if (error instanceof Error) {
    return error.message;
  }
  return 'שגיאה לא ידועה';
}
