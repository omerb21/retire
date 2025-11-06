"""
Report service - Backward compatibility wrapper for modular report system.

This file provides backward compatibility with the original report_service.py
by importing and re-exporting all functions from the modular report package.

All actual implementation is now in app/services/report/ subdirectories.
"""

# Import everything from the modular report package
from app.services.report import (
    # Main service class
    ReportService,
    
    # High-level generation function
    generate_report_pdf,
    
    # Font management
    FontManager,
    ensure_fonts,
    get_default_font,
    DEFAULT_HEBREW_FONT,
    
    # Utilities
    PDFStyles,
    DataFormatters,
    
    # Charts
    CashflowChartRenderer,
    ScenariosChartRenderer,
    render_cashflow_chart,
    create_net_cashflow_chart,
    render_scenarios_compare_chart,
    
    # Internal services (for advanced usage)
    DataService,
    PDFService,
)

# For backward compatibility - create module-level function wrapper
def create_pdf_with_cashflow(*args, **kwargs):
    """Backward compatibility wrapper for PDFService.create_pdf_with_cashflow"""
    return PDFService.create_pdf_with_cashflow(*args, **kwargs)


# Export all public APIs
__all__ = [
    # Main service
    'ReportService',
    'generate_report_pdf',
    'create_pdf_with_cashflow',
    
    # Font management
    'FontManager',
    'ensure_fonts',
    'get_default_font',
    'DEFAULT_HEBREW_FONT',
    
    # Utilities
    'PDFStyles',
    'DataFormatters',
    
    # Charts
    'CashflowChartRenderer',
    'ScenariosChartRenderer',
    'render_cashflow_chart',
    'create_net_cashflow_chart',
    'render_scenarios_compare_chart',
    
    # Internal services
    'DataService',
    'PDFService',
]
