// UI JavaScript for Retirement Planning Operations

// Helper functions
const $ = id => document.getElementById(id);
const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IL', {
        style: 'currency',
        currency: 'ILS',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
};

// Tab Functionality
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // Deactivate all tabs and tab content
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        // Activate selected tab
        tab.classList.add('active');
        $(`${tab.dataset.tab}-tab`).classList.add('active');
    });
});

// Cashflow Form
$('cashflow-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const clientId = $('cf-client-id').value;
    const scenarioId = $('cf-scenario-id').value;
    const from = $('cf-from').value;
    const to = $('cf-to').value;
    const frequency = $('cf-frequency').value;
    const log = $('cashflow-log');
    
    log.innerHTML = '<div>Processing...</div>';
    
    try {
        const url = `/api/v1/clients/${clientId}/cashflow/generate?scenario_id=${scenarioId}`;
        const params = new URLSearchParams({
            from: from,
            to: to,
            frequency: frequency
        });
        
        log.innerHTML = `<div>REQUEST: GET ${url}?${params.toString()}</div>`;
        
        const response = await fetch(`${url}?${params.toString()}`);
        log.innerHTML += `<div>STATUS: ${response.status} ${response.statusText}</div>`;
        
        if (response.ok) {
            const data = await response.json();
            log.innerHTML += `<div>Received ${data.length} cashflow rows</div>`;
            
            // Display results
            $('cashflow-result').style.display = 'block';
            
            // Process and display data in table
            const tableBody = $('cashflow-table').querySelector('tbody');
            tableBody.innerHTML = '';
            
            data.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.month || item.year}</td>
                    <td>${formatCurrency(item.income)}</td>
                    <td>${formatCurrency(item.deductions)}</td>
                    <td>${formatCurrency(item.net)}</td>
                `;
                tableBody.appendChild(row);
            });
            
            // Summary info
            const summary = $('cashflow-summary');
            const firstMonth = data[0]?.month || data[0]?.year || 'N/A';
            const lastMonth = data[data.length - 1]?.month || data[data.length - 1]?.year || 'N/A';
            summary.innerHTML = `<p>Cashflow data from ${firstMonth} to ${lastMonth}, ${data.length} periods.</p>`;
            
            // Create chart
            renderCashflowChart(data);
        } else {
            const errorData = await response.text();
            log.innerHTML += `<div style="color: red;">Error: ${errorData}</div>`;
        }
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

// Compare Form
$('compare-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const clientId = $('comp-client-id').value;
    const scenarioIds = $('comp-scenario-ids').value.split(',').map(s => Number(s.trim())).filter(n => n > 0);
    const from = $('comp-from').value;
    const to = $('comp-to').value;
    const frequency = $('comp-frequency').value;
    const log = $('compare-log');
    
    if (scenarioIds.length === 0) {
        log.innerHTML = '<div style="color: red;">Error: Please enter at least one valid scenario ID</div>';
        return;
    }
    
    log.innerHTML = '<div>Processing...</div>';
    
    try {
        const url = `/api/v1/clients/${clientId}/scenarios/compare`;
        const body = {
            scenarios: scenarioIds,
            from: from,
            to: to,
            frequency: frequency
        };
        
        log.innerHTML = `<div>REQUEST: POST ${url}</div><div>BODY: ${JSON.stringify(body)}</div>`;
        
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        
        log.innerHTML += `<div>STATUS: ${response.status} ${response.statusText}</div>`;
        
        if (response.ok) {
            const data = await response.json();
            log.innerHTML += `<div>Received comparison data</div>`;
            
            // Display results
            $('compare-result').style.display = 'block';
            
            // Process and display yearly totals in table
            const tableBody = $('yearly-totals-table').querySelector('tbody');
            tableBody.innerHTML = '';
            
            if (data.yearly) {
                Object.entries(data.yearly).forEach(([scenarioId, years]) => {
                    Object.entries(years).forEach(([year, values]) => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${year}</td>
                            <td>${scenarioId}</td>
                            <td>${formatCurrency(values.income)}</td>
                            <td>${formatCurrency(values.deductions)}</td>
                            <td>${formatCurrency(values.net)}</td>
                        `;
                        tableBody.appendChild(row);
                    });
                });
            }
            
            // Create comparison chart
            renderCompareChart(data);
        } else {
            const errorData = await response.text();
            log.innerHTML += `<div style="color: red;">Error: ${errorData}</div>`;
        }
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

// Case Detection Form
$('case-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const clientId = $('case-client-id').value;
    const log = $('case-log');
    const caseResult = $('case-result');
    
    log.innerHTML = '<div>Processing...</div>';
    caseResult.style.display = 'none';
    $('integration-actions').style.display = 'none';
    
    try {
        const url = `/api/v1/clients/${clientId}/case/detect`;
        
        log.innerHTML = `<div>REQUEST: GET ${url}</div>`;
        
        const response = await fetch(url);
        log.innerHTML += `<div>STATUS: ${response.status} ${response.statusText}</div>`;
        
        if (response.ok) {
            const data = await response.json();
            log.innerHTML += `<div>RESPONSE: ${JSON.stringify(data, null, 2)}</div>`;
            
            // Store case data for integration tests
            window.detectedCase = {
                client_id: clientId,
                case_id: data.result.case_id,
                case_name: data.result.case_name
            };
            
            // Display result
            caseResult.style.display = 'block';
            caseResult.className = `case-detection-result case-${data.result.case_id}`;
            
            let reasonsHtml = '';
            if (data.result.reasons && data.result.reasons.length > 0) {
                reasonsHtml = '<ul class="reasons-list">';
                data.result.reasons.forEach(reason => {
                    reasonsHtml += `<li>${formatReason(reason)}</li>`;
                });
                reasonsHtml += '</ul>';
            }
            
            caseResult.innerHTML = `
                <h4>Detected Case: ${data.result.case_name} (ID: ${data.result.case_id})</h4>
                <p>Client ID: ${data.result.client_id}</p>
                <p>Detected at: ${new Date(data.result.detected_at).toLocaleString()}</p>
                <h5>Detection Reasons:</h5>
                ${reasonsHtml}
            `;
            
            // Show integration buttons
            $('integration-actions').style.display = 'block';
        } else {
            const errorData = await response.text();
            log.innerHTML += `<div style="color: red;">Error: ${errorData}</div>`;
        }
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

// Integration Test Buttons
$('test-cashflow').addEventListener('click', async () => {
    if (!window.detectedCase) {
        $('case-log').innerHTML += '<div style="color: red;">Please detect a case first</div>';
        return;
    }
    
    const clientId = window.detectedCase.client_id;
    const caseId = window.detectedCase.case_id;
    const log = $('case-log');
    
    try {
        const url = `/api/v1/clients/${clientId}/cashflow/generate`;
        const params = new URLSearchParams({
            scenario_id: 24,
            from: '2025-01',
            to: '2025-12',
            frequency: 'monthly',
            case_id: caseId
        });
        
        log.innerHTML += `<div>INTEGRATION TEST - CASHFLOW</div>`;
        log.innerHTML += `<div>REQUEST: GET ${url}?${params.toString()}</div>`;
        
        const response = await fetch(`${url}?${params.toString()}`);
        log.innerHTML += `<div>STATUS: ${response.status} ${response.statusText}</div>`;
        
        if (response.ok) {
            const data = await response.json();
            log.innerHTML += `<div>Cashflow Integration Test: Success (${data.length} rows)</div>`;
            
            // Switch to Cashflow tab to show results
            document.querySelector('.tab[data-tab="cashflow"]').click();
            
            // Update the form values
            $('cf-client-id').value = clientId;
            $('cf-scenario-id').value = 24;
            $('cf-from').value = '2025-01';
            $('cf-to').value = '2025-12';
            
            // Trigger form submission
            $('cashflow-form').dispatchEvent(new Event('submit'));
        } else {
            const errorData = await response.text();
            log.innerHTML += `<div style="color: red;">Error: ${errorData}</div>`;
        }
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

$('test-compare').addEventListener('click', async () => {
    if (!window.detectedCase) {
        $('case-log').innerHTML += '<div style="color: red;">Please detect a case first</div>';
        return;
    }
    
    const clientId = window.detectedCase.client_id;
    const caseId = window.detectedCase.case_id;
    const log = $('case-log');
    
    try {
        const url = `/api/v1/clients/${clientId}/scenarios/compare`;
        const body = {
            scenarios: [24],
            from: '2025-01',
            to: '2025-12',
            frequency: 'monthly',
            case_id: caseId
        };
        
        log.innerHTML += `<div>INTEGRATION TEST - COMPARE</div>`;
        log.innerHTML += `<div>REQUEST: POST ${url}</div><div>BODY: ${JSON.stringify(body)}</div>`;
        
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        
        log.innerHTML += `<div>STATUS: ${response.status} ${response.statusText}</div>`;
        
        if (response.ok) {
            const data = await response.json();
            log.innerHTML += `<div>Compare Integration Test: Success</div>`;
            
            // Switch to Compare tab to show results
            document.querySelector('.tab[data-tab="compare"]').click();
            
            // Update the form values
            $('comp-client-id').value = clientId;
            $('comp-scenario-ids').value = '24';
            $('comp-from').value = '2025-01';
            $('comp-to').value = '2025-12';
            
            // Trigger form submission
            $('compare-form').dispatchEvent(new Event('submit'));
        } else {
            const errorData = await response.text();
            log.innerHTML += `<div style="color: red;">Error: ${errorData}</div>`;
        }
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

$('test-report').addEventListener('click', async () => {
    if (!window.detectedCase) {
        $('case-log').innerHTML += '<div style="color: red;">Please detect a case first</div>';
        return;
    }
    
    const clientId = window.detectedCase.client_id;
    const caseId = window.detectedCase.case_id;
    const log = $('case-log');
    
    try {
        const url = `/api/v1/clients/${clientId}/scenarios/24/report?case_id=${caseId}`;
        
        log.innerHTML += `<div>INTEGRATION TEST - REPORT</div>`;
        log.innerHTML += `<div>REQUEST: GET ${url}</div>`;
        
        log.innerHTML += `<div>Opening report in new tab...</div>`;
        window.open(url, '_blank');
    } catch (error) {
        log.innerHTML += `<div style="color: red;">Error: ${error.message}</div>`;
    }
});

// Chart rendering functions
function renderCashflowChart(data) {
    const ctx = $('cashflow-chart').getContext('2d');
    
    // Destroy previous chart if exists
    if (window.cashflowChart) {
        window.cashflowChart.destroy();
    }
    
    const labels = data.map(item => item.month || item.year);
    const incomeData = data.map(item => item.income);
    const deductionsData = data.map(item => item.deductions);
    const netData = data.map(item => item.net);
    
    window.cashflowChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Income',
                    data: incomeData,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Deductions',
                    data: deductionsData,
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Net',
                    data: netData,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderCompareChart(data) {
    const ctx = $('compare-chart').getContext('2d');
    
    // Destroy previous chart if exists
    if (window.compareChart) {
        window.compareChart.destroy();
    }
    
    // Extract data for chart
    const datasets = [];
    const scenarioColors = {
        // Pre-defined colors for scenarios
        '24': { color: 'rgba(54, 162, 235, 0.5)', border: 'rgba(54, 162, 235, 1)' },
        '25': { color: 'rgba(255, 99, 132, 0.5)', border: 'rgba(255, 99, 132, 1)' },
        '26': { color: 'rgba(75, 192, 192, 0.5)', border: 'rgba(75, 192, 192, 1)' },
        '27': { color: 'rgba(255, 159, 64, 0.5)', border: 'rgba(255, 159, 64, 1)' }
    };
    
    // Generate datasets for each scenario
    let labels = [];
    
    if (data.monthly) {
        Object.entries(data.monthly).forEach(([scenarioId, months]) => {
            const scenarioData = [];
            
            // Collect all months
            Object.entries(months).forEach(([month, values]) => {
                if (!labels.includes(month)) {
                    labels.push(month);
                }
            });
            
            // Sort labels
            labels.sort();
            
            // Fill data points
            labels.forEach(month => {
                scenarioData.push(months[month]?.net || 0);
            });
            
            const colorInfo = scenarioColors[scenarioId] || {
                color: `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 0.5)`,
                border: `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 1)`
            };
            
            datasets.push({
                label: `Scenario ${scenarioId}`,
                data: scenarioData,
                backgroundColor: colorInfo.color,
                borderColor: colorInfo.border,
                borderWidth: 1
            });
        });
    } else if (data.yearly) {
        Object.entries(data.yearly).forEach(([scenarioId, years]) => {
            const scenarioData = [];
            
            // Collect all years
            Object.entries(years).forEach(([year, values]) => {
                if (!labels.includes(year)) {
                    labels.push(year);
                }
            });
            
            // Sort labels
            labels.sort();
            
            // Fill data points
            labels.forEach(year => {
                scenarioData.push(years[year]?.net || 0);
            });
            
            const colorInfo = scenarioColors[scenarioId] || {
                color: `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 0.5)`,
                border: `rgba(${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, ${Math.floor(Math.random() * 255)}, 1)`
            };
            
            datasets.push({
                label: `Scenario ${scenarioId}`,
                data: scenarioData,
                backgroundColor: colorInfo.color,
                borderColor: colorInfo.border,
                borderWidth: 1
            });
        });
    }
    
    window.compareChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Helper function to format case detection reasons
function formatReason(reason) {
    const reasonMap = {
        'has_current_employer': 'Client has a current employer',
        'no_current_employer': 'Client has no current employer',
        'has_business_income': 'Client has business income (self-employed)',
        'past_retirement_age': 'Client is past retirement age',
        'no_planned_leave': 'No planned leave detected',
        'planned_leave_detected_or_default': 'Planned leave or termination detected',
        'no_business_income': 'No business income detected'
    };
    
    return reasonMap[reason] || reason;
}
