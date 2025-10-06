import pytest
import os
import json
from pathlib import Path
from app.utils.calculation_log import log_calc, get_recent_logs, clear_logs


class TestCalculationLog:
    """Test calculation logging functionality"""
    
    def setup_method(self):
        """Clear logs before each test"""
        clear_logs()
    
    def teardown_method(self):
        """Clear logs after each test"""
        clear_logs()
    
    def test_log_calc_basic(self):
        """Test basic calculation logging"""
        event = "test_calculation"
        payload = {"client_id": 1, "scenario_id": 24}
        result = {"status": "success", "value": 100.0}
        
        log_calc(event, payload, result)
        
        # Verify log was written
        logs = get_recent_logs(1)
        assert len(logs) == 1
        
        log_entry = logs[0]
        assert log_entry["event"] == event
        assert log_entry["payload"] == payload
        assert log_entry["result"] == result
        assert "timestamp" in log_entry
    
    def test_log_calc_with_debug(self):
        """Test calculation logging with debug info"""
        # Set DEBUG_CALC environment variable
        os.environ["DEBUG_CALC"] = "1"
        
        try:
            event = "test_debug_calculation"
            payload = {"client_id": 1}
            debug_info = {"formulas": {"net": "inflow - outflow"}, "parameters": {"rate": 0.05}}
            
            log_calc(event, payload, None, debug_info)
            
            logs = get_recent_logs(1)
            assert len(logs) == 1
            
            log_entry = logs[0]
            assert log_entry["event"] == event
            assert "debug" in log_entry
            assert log_entry["debug"] == debug_info
        finally:
            # Clean up environment variable
            if "DEBUG_CALC" in os.environ:
                del os.environ["DEBUG_CALC"]
    
    def test_log_calc_without_debug(self):
        """Test that debug info is not logged when DEBUG_CALC is not set"""
        # Ensure DEBUG_CALC is not set
        if "DEBUG_CALC" in os.environ:
            del os.environ["DEBUG_CALC"]
        
        event = "test_no_debug"
        payload = {"client_id": 1}
        debug_info = {"should_not_appear": True}
        
        log_calc(event, payload, None, debug_info)
        
        logs = get_recent_logs(1)
        assert len(logs) == 1
        
        log_entry = logs[0]
        assert "debug" not in log_entry
    
    def test_log_calc_large_result_summary(self):
        """Test that large results are summarized"""
        event = "test_large_result"
        payload = {"client_id": 1}
        large_result = [{"month": i, "value": i * 100} for i in range(20)]  # > 10 items
        
        log_calc(event, payload, large_result)
        
        logs = get_recent_logs(1)
        assert len(logs) == 1
        
        log_entry = logs[0]
        assert "result" not in log_entry  # Full result not logged
        assert "result_summary" in log_entry
        
        summary = log_entry["result_summary"]
        assert summary["type"] == "list"
        assert summary["length"] == 20
        assert summary["first_item"] == large_result[0]
        assert summary["last_item"] == large_result[-1]
    
    def test_log_calc_scenario_comparison_result(self):
        """Test scenario comparison result summarization"""
        event = "compare_scenarios"
        payload = {"client_id": 1, "scenario_ids": [24, 25]}
        result = {
            "scenarios": {
                "24": {"monthly": [], "yearly": {}},
                "25": {"monthly": [], "yearly": {}}
            },
            "meta": {"client_id": 1, "from": "2025-01", "to": "2025-12"}
        }
        
        log_calc(event, payload, result)
        
        logs = get_recent_logs(1)
        assert len(logs) == 1
        
        log_entry = logs[0]
        assert "result_summary" in log_entry
        
        summary = log_entry["result_summary"]
        assert summary["type"] == "scenario_comparison"
        assert summary["scenario_count"] == 2
        assert summary["meta"] == result["meta"]
    
    def test_get_recent_logs_limit(self):
        """Test getting recent logs with limit"""
        # Log multiple entries
        for i in range(5):
            log_calc(f"test_event_{i}", {"index": i}, {"result": i})
        
        # Get limited logs
        logs = get_recent_logs(3)
        assert len(logs) == 3
        
        # Should get the last 3 entries
        assert logs[0]["payload"]["index"] == 2
        assert logs[1]["payload"]["index"] == 3
        assert logs[2]["payload"]["index"] == 4
    
    def test_logs_directory_creation(self):
        """Test that logs directory is created automatically"""
        # Remove logs directory if it exists
        logs_dir = Path("logs")
        if logs_dir.exists():
            import shutil
            shutil.rmtree(logs_dir)
        
        # Log something - should create directory
        log_calc("test_dir_creation", {"test": True}, None)
        
        # Verify directory was created
        assert logs_dir.exists()
        assert logs_dir.is_dir()
        
        # Verify log file was created
        log_file = logs_dir / "calculation.log"
        assert log_file.exists()
    
    def test_log_calc_error_handling(self):
        """Test that logging errors don't break the application"""
        # This test ensures that even if logging fails, the main application continues
        # We can't easily simulate a logging failure, but we can test the error handling structure
        
        # Test with invalid JSON-serializable data
        import datetime
        event = "test_error_handling"
        payload = {"date": datetime.datetime.now()}  # datetime objects need special handling
        
        # This should not raise an exception
        log_calc(event, payload, None)
        
        # Verify something was logged (the default=str should handle datetime)
        logs = get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["event"] == event
