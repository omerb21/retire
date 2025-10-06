/**
 * Test data for yearly totals verification
 * This file provides mock API responses for testing the yearly totals verification feature
 */

// Mock cashflow data with monthly rows
const MOCK_CASHFLOW_DATA = {
  rows: [
    // Scenario 1 - 2025 - Valid data (all months present, correct totals)
    { scenario_id: "1", date: "2025-01", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-02", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-03", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-04", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-05", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-06", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-07", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-08", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-09", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-10", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-11", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2025-12", inflow: 10000, outflow: 7000, net: 3000, additional_income_net: 500, capital_return_net: 200 },

    // Scenario 1 - 2026 - Missing months (only 10 months)
    { scenario_id: "1", date: "2026-01", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-02", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-03", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-04", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-05", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-06", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-07", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-08", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-09", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2026-10", inflow: 11000, outflow: 8000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    // Missing November and December

    // Scenario 1 - 2027 - Monthly net mismatch
    { scenario_id: "1", date: "2027-01", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-02", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-03", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-04", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-05", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-06", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-07", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-08", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-09", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-10", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    { scenario_id: "1", date: "2027-11", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },
    // Error in net calculation: inflow - outflow + add_income + capital_return should be 3700, not 3000
    { scenario_id: "1", date: "2027-12", inflow: 12000, outflow: 9000, net: 3000, additional_income_net: 500, capital_return_net: 200 },

    // Scenario 2 - 2025 - Invalid date format
    { scenario_id: "2", date: "2025-1", inflow: 15000, outflow: 10000, net: 5000, additional_income_net: 0, capital_return_net: 0 },
    { scenario_id: "2", date: "2025-02", inflow: 15000, outflow: 10000, net: 5000, additional_income_net: 0, capital_return_net: 0 },
    { scenario_id: "2", date: "2025-03", inflow: 15000, outflow: 10000, net: 5000, additional_income_net: 0, capital_return_net: 0 },
  ]
};

// Mock compare data with yearly totals
const MOCK_COMPARE_DATA = {
  yearly_totals: {
    "1": {
      "2025": {
        inflow: 120000,
        outflow: 84000,
        net: 36000,
        additional_income_net: 6000,
        capital_return_net: 2400
      },
      "2026": {
        inflow: 110000,
        outflow: 80000,
        net: 30000,
        additional_income_net: 5000,
        capital_return_net: 2000
      },
      "2027": {
        // Yearly total mismatch - should be 144000
        inflow: 140000, 
        outflow: 108000,
        net: 36000,
        additional_income_net: 6000,
        capital_return_net: 2400
      }
    },
    "2": {
      "2025": {
        inflow: 45000,
        outflow: 30000,
        net: 15000,
        additional_income_net: 0,
        capital_return_net: 0
      }
    }
  }
};

// Mock case detection status
const MOCK_CASE_DETECTION = {
  case: {
    id: "1",
    name: "No Current Employer"
  }
};

// Mock PDF generation status
const MOCK_PDF_STATUS = {
  status: 200,
  data: "%PDF-1.5\nSimulated PDF content for testing"
};

// Function to simulate API fetch responses
function mockApiFetch(endpoint) {
  return new Promise((resolve) => {
    setTimeout(() => {
      if (endpoint.includes('cashflow')) {
        resolve({
          ok: true,
          status: 200,
          data: MOCK_CASHFLOW_DATA
        });
      } else if (endpoint.includes('compare')) {
        resolve({
          ok: true,
          status: 200,
          data: MOCK_COMPARE_DATA
        });
      } else if (endpoint.includes('case/detect')) {
        resolve({
          ok: true, 
          status: 200,
          data: MOCK_CASE_DETECTION
        });
      } else if (endpoint.includes('report/pdf')) {
        resolve({
          ok: true,
          status: 200,
          data: MOCK_PDF_STATUS.data
        });
      } else {
        resolve({
          ok: false,
          status: 404,
          data: null
        });
      }
    }, 500); // Add delay to simulate API latency
  });
}
