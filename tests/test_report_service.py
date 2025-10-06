from app.services.report_service import ReportService

def test_report_service_compose_pdf_smoke():
    # Mock minimal data structures that match the expected format
    class MockClient:
        def __init__(self):
            self.full_name = "ישראל ישראלי"
            self.id_number = "123456789"
    
    class MockScenario:
        def __init__(self):
            self.id = 1
            self.name = "תרחיש 1"
            self.cashflow_projection = '{"annual_cashflow": [{"net_cashflow": 10000, "year": 2024}]}'
    
    client = MockClient()
    scenarios = [MockScenario()]
    summary = {
        "client_info": {
            "full_name": "ישראל ישראלי",
            "id_number": "123456789",
            "birth_date": "1980-01-01",
            "email": "test@example.com",
            "phone": "050-1234567",
            "address": "תל אביב"
        },
        "employment_info": [],
        "scenarios_summary": [{
            "name": "תרחיש 1",
            "created_at": "2024-01-01",
            "total_pension": 500000,
            "monthly_pension": 8000,
            "total_grants": 100000
        }],
        "report_metadata": {
            "generated_at": "2024-01-01 12:00:00"
        }
    }
    
    # Create proper chart data using the service methods
    cashflow_data = {"annual_cashflow": [{"net_cashflow": 10000, "year": 2024}]}
    chart_cashflow = ReportService.render_cashflow_chart(cashflow_data)
    chart_compare = ReportService.render_scenarios_compare_chart(scenarios)
    
    pdf_bytes = ReportService.compose_pdf(client, scenarios, summary, chart_cashflow, chart_compare)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 5_000  # מינימום סביר
