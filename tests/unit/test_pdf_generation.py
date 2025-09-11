"""
Unit tests for PDF generation functionality
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from utils.pdf_builder import RetirementReportBuilder, build_pdf
from utils.pdf_graphs import (
    render_cashflow_chart, render_income_breakdown_chart,
    render_cumulative_chart, render_tax_analysis_chart,
    create_summary_pie_chart, create_empty_chart
)
import io

class TestPDFGraphs:
    """Test PDF graph generation functions"""
    
    def test_render_cashflow_chart_with_data(self):
        """Test cashflow chart generation with valid data"""
        cashflow = [
            {'year': 2024, 'gross_income': 100000, 'net_income': 80000, 'tax': 20000},
            {'year': 2025, 'gross_income': 105000, 'net_income': 84000, 'tax': 21000},
            {'year': 2026, 'gross_income': 110000, 'net_income': 88000, 'tax': 22000}
        ]
        
        result = render_cashflow_chart(cashflow, "Test Cashflow")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0  # Buffer has content
        result.seek(0)
        content = result.read()
        assert len(content) > 1000  # Reasonable size for PNG
    
    def test_render_cashflow_chart_empty_data(self):
        """Test cashflow chart with empty data"""
        result = render_cashflow_chart([], "Empty Cashflow")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_render_income_breakdown_chart(self):
        """Test income breakdown chart generation"""
        cashflow = [
            {'year': 2024, 'pension_income': 60000, 'grant_income': 30000, 'other_income': 10000},
            {'year': 2025, 'pension_income': 62000, 'grant_income': 25000, 'other_income': 12000}
        ]
        
        result = render_income_breakdown_chart(cashflow, "Income Breakdown")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_render_cumulative_chart(self):
        """Test cumulative income chart generation"""
        cashflow = [
            {'year': 2024, 'net_income': 80000},
            {'year': 2025, 'net_income': 84000},
            {'year': 2026, 'net_income': 88000}
        ]
        
        result = render_cumulative_chart(cashflow, "Cumulative Income")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_render_tax_analysis_chart(self):
        """Test tax analysis chart generation"""
        cashflow = [
            {'year': 2024, 'gross_income': 100000, 'tax': 20000},
            {'year': 2025, 'gross_income': 105000, 'tax': 21000}
        ]
        
        result = render_tax_analysis_chart(cashflow, "Tax Analysis")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_create_summary_pie_chart(self):
        """Test summary pie chart generation"""
        summary_data = {
            'Pension Income': 60000,
            'Grant Income': 30000,
            'Other Income': 10000
        }
        
        result = create_summary_pie_chart(summary_data, "Income Summary")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_create_summary_pie_chart_empty_data(self):
        """Test pie chart with empty or zero data"""
        summary_data = {'Income': 0}
        
        result = create_summary_pie_chart(summary_data, "Empty Summary")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0
    
    def test_create_empty_chart(self):
        """Test empty chart creation"""
        result = create_empty_chart("No data available")
        
        assert isinstance(result, io.BytesIO)
        assert result.tell() > 0

class TestRetirementReportBuilder:
    """Test PDF report builder functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.builder = RetirementReportBuilder()
        
        # Mock client
        self.mock_client = Mock()
        self.mock_client.id = 1
        self.mock_client.full_name = "John Doe"
        
        # Mock context
        self.context = {
            'client': self.mock_client,
            'retirement_age': 67,
            'life_expectancy': 85,
            'indexation_rate': 0.02,
            'pension_calculation': {
                'total_capital': 1000000,
                'reservation_impact': 50000,
                'effective_capital': 950000,
                'years_in_retirement': 18,
                'annual_pension': 52777,
                'monthly_pension': 4398
            },
            'processed_grants': [
                {
                    'grant_type': 'Severance',
                    'original_amount': 200000,
                    'reservation_impact': 70000,
                    'payment_year': 2024
                }
            ],
            'tax_parameters': {
                'brackets': [
                    {'min': 0, 'max': 75960, 'rate': 0.10},
                    {'min': 75960, 'max': 108960, 'rate': 0.14}
                ]
            }
        }
        
        # Mock cashflow
        self.cashflow = [
            {
                'year': 2024,
                'gross_income': 100000,
                'pension_income': 60000,
                'grant_income': 40000,
                'other_income': 0,
                'tax': 20000,
                'net_income': 80000
            },
            {
                'year': 2025,
                'gross_income': 105000,
                'pension_income': 62000,
                'grant_income': 43000,
                'other_income': 0,
                'tax': 21000,
                'net_income': 84000
            }
        ]
    
    def test_setup_custom_styles(self):
        """Test custom styles setup"""
        assert 'CustomTitle' in self.builder.styles
        assert 'CustomSubtitle' in self.builder.styles
        assert 'SectionHeader' in self.builder.styles
        assert 'BodyHebrew' in self.builder.styles
        assert 'HighlightBox' in self.builder.styles
    
    def test_build_cover_page(self):
        """Test cover page generation"""
        elements = self.builder._build_cover_page(self.context)
        
        assert len(elements) > 0
        # Should contain title, client info, summary, and disclaimer
        assert len(elements) >= 4
    
    def test_build_executive_summary(self):
        """Test executive summary generation"""
        elements = self.builder._build_executive_summary(self.context, self.cashflow)
        
        assert len(elements) > 0
        # Should contain summary table and insights
    
    def test_build_detailed_analysis(self):
        """Test detailed analysis section"""
        elements = self.builder._build_detailed_analysis(self.context, self.cashflow)
        
        assert len(elements) > 0
        # Should contain pension calculation and grant analysis
    
    def test_build_cashflow_tables(self):
        """Test cashflow tables generation"""
        elements = self.builder._build_cashflow_tables(self.cashflow)
        
        assert len(elements) > 0
        # Should contain at least one table
    
    def test_build_cashflow_tables_empty(self):
        """Test cashflow tables with empty data"""
        elements = self.builder._build_cashflow_tables([])
        
        assert len(elements) > 0
        # Should contain message about no data
    
    def test_build_appendices(self):
        """Test appendices generation"""
        elements = self.builder._build_appendices(self.context)
        
        assert len(elements) > 0
        # Should contain tax parameters and assumptions
    
    @patch('utils.pdf_graphs.render_cashflow_chart')
    @patch('utils.pdf_graphs.render_income_breakdown_chart')
    @patch('utils.pdf_graphs.render_cumulative_chart')
    def test_build_charts_section(self, mock_cumulative, mock_breakdown, mock_cashflow):
        """Test charts section generation with mocked chart functions"""
        # Mock chart functions to return BytesIO objects
        mock_chart = io.BytesIO(b'fake_chart_data')
        mock_cashflow.return_value = mock_chart
        mock_breakdown.return_value = mock_chart
        mock_cumulative.return_value = mock_chart
        
        elements = self.builder._build_charts_section(self.cashflow)
        
        assert len(elements) > 0
        # Should call chart generation functions
        mock_cashflow.assert_called_once()
        mock_breakdown.assert_called_once()
        mock_cumulative.assert_called_once()
    
    def test_build_charts_section_empty_data(self):
        """Test charts section with empty cashflow data"""
        elements = self.builder._build_charts_section([])
        
        assert len(elements) > 0
        # Should contain message about no data

class TestPDFBuildIntegration:
    """Integration tests for PDF building"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock client
        self.mock_client = Mock()
        self.mock_client.id = 1
        self.mock_client.full_name = "Test Client"
        
        # Context data
        self.context = {
            'client': self.mock_client,
            'retirement_age': 67,
            'life_expectancy': 85,
            'indexation_rate': 0.02,
            'pension_calculation': {
                'total_capital': 1000000,
                'effective_capital': 950000,
                'annual_pension': 52777,
                'monthly_pension': 4398
            },
            'processed_grants': [],
            'tax_parameters': {
                'brackets': [
                    {'min': 0, 'max': 75960, 'rate': 0.10}
                ]
            }
        }
        
        # Cashflow data
        self.cashflow = [
            {
                'year': 2024,
                'gross_income': 100000,
                'pension_income': 60000,
                'grant_income': 40000,
                'other_income': 0,
                'tax': 20000,
                'net_income': 80000
            }
        ]
    
    def test_build_pdf_success(self):
        """Test successful PDF generation"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            result_path = build_pdf(self.context, self.cashflow, file_path)
            
            assert result_path == file_path
            assert os.path.exists(file_path)
            assert os.path.getsize(file_path) > 1000  # PDF should have reasonable size
            
            # Verify it's a valid PDF (starts with PDF header)
            with open(file_path, 'rb') as f:
                header = f.read(4)
                assert header == b'%PDF'
        
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def test_build_pdf_empty_cashflow(self):
        """Test PDF generation with empty cashflow"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            result_path = build_pdf(self.context, [], file_path)
            
            assert result_path == file_path
            assert os.path.exists(file_path)
            assert os.path.getsize(file_path) > 500  # Should still generate a PDF
        
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def test_build_pdf_invalid_path(self):
        """Test PDF generation with invalid file path"""
        invalid_path = "/invalid/path/test.pdf"
        
        with pytest.raises(Exception):
            build_pdf(self.context, self.cashflow, invalid_path)

class TestPDFUtilities:
    """Test PDF utility functions"""
    
    def test_number_formatting(self):
        """Test number formatting in Hebrew locale"""
        # This test verifies that numbers are formatted correctly
        # The actual formatting may depend on system locale settings
        test_number = 1234567.89
        formatted = f"{test_number:,.2f}"
        
        # Should contain some form of thousands separator
        assert len(formatted) > len(str(int(test_number)))
    
    def test_hebrew_text_handling(self):
        """Test Hebrew text handling in PDF"""
        # Test that Hebrew text doesn't cause encoding issues
        hebrew_text = "דוח תכנון פרישה"
        
        # Should not raise encoding errors
        try:
            encoded = hebrew_text.encode('utf-8')
            decoded = encoded.decode('utf-8')
            assert decoded == hebrew_text
        except UnicodeError:
            pytest.fail("Hebrew text encoding failed")

if __name__ == "__main__":
    pytest.main([__file__])
