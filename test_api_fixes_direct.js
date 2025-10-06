// Test script to verify our API fixes for pension funds, fixation, and scenarios

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
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  console.log(`Calling ${init?.method || 'GET'} ${url}`);
  
  if (init?.body) {
    console.log('Request body:', init.body);
  }
  
  const res = await fetch(url, {
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
    throw new Error(`${res.status} ${message}`);
  }

  const result = looksJson ? await res.json() : await res.text();
  console.log('Response:', result);
  return result;
}

// 1. Test Pension Fund Creation
async function testPensionFundCreation(clientId) {
  console.log("\n=== Testing Pension Fund Creation ===");
  
  // Align date to first of month
  const startDate = new Date();
  startDate.setDate(1);
  const formattedDate = startDate.toISOString().split('T')[0];
  
  // Test calculated mode
  console.log("\nTesting calculated mode pension fund creation...");
  const calculatedPayload = {
    client_id: Number(clientId),
    fund_name: "Test Calculated Fund",
    input_mode: "calculated",
    balance: 100000,
    annuity_factor: 220,
    pension_start_date: formattedDate,
    indexation_method: "none"
  };
  
  try {
    const calculatedResult = await apiFetch(`/clients/${clientId}/pension-funds`, {
      method: "POST",
      body: JSON.stringify(calculatedPayload)
    });
    console.log("✅ Calculated mode pension fund created successfully!");
    console.log("Fund ID:", calculatedResult.id);
  } catch (error) {
    console.error("❌ Calculated mode pension fund creation failed:", error.message);
  }
  
  // Test manual mode
  console.log("\nTesting manual mode pension fund creation...");
  const manualPayload = {
    client_id: Number(clientId),
    fund_name: "Test Manual Fund",
    input_mode: "manual",
    pension_amount: 5000,
    pension_start_date: formattedDate,
    indexation_method: "fixed",
    fixed_index_rate: 0.02
  };
  
  try {
    const manualResult = await apiFetch(`/clients/${clientId}/pension-funds`, {
      method: "POST",
      body: JSON.stringify(manualPayload)
    });
    console.log("✅ Manual mode pension fund created successfully!");
    console.log("Fund ID:", manualResult.id);
  } catch (error) {
    console.error("❌ Manual mode pension fund creation failed:", error.message);
  }
}

// 2. Test Fixation Compute
async function testFixationCompute(clientId) {
  console.log("\n=== Testing Fixation Compute ===");
  
  try {
    console.log(`Calling fixation compute endpoint: /fixation/${clientId}/compute`);
    const fixationResult = await apiFetch(`/fixation/${clientId}/compute`, {
      method: "POST"
    });
    
    console.log("✅ Fixation compute successful!");
    
    if (fixationResult.summary) {
      console.log("Summary:");
      console.log("  Total Pension:", fixationResult.summary.total_pension);
      console.log("  Total Grants:", fixationResult.summary.total_grants);
      console.log("  Net Amount:", fixationResult.summary.net_amount);
    }
  } catch (error) {
    console.error("❌ Fixation compute failed:", error.message);
  }
}

// 3. Test Scenarios Integration
async function testScenariosIntegration(clientId) {
  console.log("\n=== Testing Scenarios Integration ===");
  
  // Create a scenario
  console.log("\nCreating a new scenario...");
  const scenarioPayload = {
    scenario_name: `Test Scenario ${new Date().toISOString().slice(0, 16)}`,
    planned_termination_date: null,
    monthly_expenses: 10000,
    apply_tax_planning: false,
    apply_capitalization: false,
    apply_exemption_shield: false
  };
  
  try {
    const scenarioResult = await apiFetch(`/clients/${clientId}/scenarios`, {
      method: "POST",
      body: JSON.stringify(scenarioPayload)
    });
    
    console.log("✅ Scenario created successfully!");
    console.log("Scenario ID:", scenarioResult.scenario_id);
    
    // List scenarios
    console.log("\nListing all scenarios...");
    const scenariosList = await apiFetch(`/clients/${clientId}/scenarios`);
    
    console.log(`Found ${scenariosList.length} scenarios`);
    
    if (scenariosList.length > 0) {
      const scenarioId = scenarioResult.scenario_id || scenariosList[0].id;
      
      // Integrate all
      console.log(`\nIntegrating all with scenario_id=${scenarioId}...`);
      const integrateResult = await apiFetch(`/clients/${clientId}/cashflow/integrate-all?scenario_id=${scenarioId}`, {
        method: "POST"
      });
      
      console.log("✅ Integration successful!");
      console.log(`Received ${integrateResult.length} cashflow entries`);
      
      if (integrateResult.length > 0) {
        console.log("First few entries:", integrateResult.slice(0, 3));
      }
    }
  } catch (error) {
    console.error("❌ Scenarios integration failed:", error.message);
  }
}

async function main() {
  try {
    const clientId = 1; // Change this if needed
    
    // Test all fixes
    await testPensionFundCreation(clientId);
    await testFixationCompute(clientId);
    await testScenariosIntegration(clientId);
    
    console.log("\n✅ All tests completed!");
  } catch (error) {
    console.error("❌ Test failed:", error.message);
  }
}

main();
