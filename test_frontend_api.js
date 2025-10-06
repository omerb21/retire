// Simple test script to verify our fetch wrapper works correctly

const API_BASE = "http://localhost:8000/api/v1";

async function parseJsonSafe(res) {
  try {
    return await res.clone().json();
  } catch {
    return null;
  }
}

async function parseTextSafe(res) {
  try {
    return await res.clone().text();
  } catch {
    return "";
  }
}

function extractMessage(body) {
  if (!body) return;
  if (typeof body === "string") return body;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((d) => d.msg || d?.loc?.join(".")).join("; ");
  }
}

async function apiFetch(path, init = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  const contentType = res.headers.get("content-type") ?? "";
  const looksJson = contentType.includes("application/json");

  if (!res.ok) {
    const json = looksJson ? await parseJsonSafe(res) : null;
    const txt = !json ? await parseTextSafe(res) : undefined;
    const message = extractMessage(json) || txt || `HTTP ${res.status}`;
    throw new Error(message);
  }

  if (looksJson) return await res.json();
  return await res.text();
}

async function listClients() {
  return apiFetch("/clients?limit=10&offset=0");
}

async function createClient(payload) {
  const p = { ...payload, id_number: `${payload.id_number}`.trim() };
  return apiFetch("/clients", { method: "POST", body: JSON.stringify(p) });
}

async function main() {
  try {
    console.log("Testing client listing...");
    const listResult = await listClients();
    console.log("Client list success:", JSON.stringify(listResult, null, 2).slice(0, 300) + "...");

    console.log("\nTesting client creation...");
    const newClient = await createClient({
      first_name: "Test",
      last_name: "User",
      id_number: "123456789",
      birth_date: "1980-01-01",
      email: "test@example.com"
    });
    console.log("Client creation success:", newClient);
    
    console.log("\nAll tests passed!");
  } catch (error) {
    console.error("Test failed:", error.message);
  }
}

main();
