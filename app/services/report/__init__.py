"""
Report generation module - modular structure.

This module provides PDF report generation with Hebrew support,
charts, and comprehensive financial data presentation.
"""

from .base import ReportService
from .charts import (
    CashflowChartRenderer,
    ScenariosChartRenderer,
    create_net_cashflow_chart,
    render_cashflow_chart,
    render_scenarios_compare_chart,
)
from .config import *
from .fonts import FontManager, ensure_fonts, get_default_font
from .generators.report_generator import generate_report_pdf
from .services import DataService, PDFService
from .utils import DataFormatters, PDFStyles

__all__ = [
    # Configuration
    "DEFAULT_HEBREW_FONT",
    "DEFAULT_PAGE_SIZE",
    "CHART_COLORS",
    # Font management
    "FontManager",
    "ensure_fonts",
    "get_default_font",
    # Utilities
    "PDFStyles",
    "DataFormatters",
    # Charts
    "CashflowChartRenderer",
    "ScenariosChartRenderer",
    "render_cashflow_chart",
    "create_net_cashflow_chart",
    "render_scenarios_compare_chart",
    # Main service
    "ReportService",
    "generate_report_pdf",
    # Internal services
    "DataService",
    "PDFService",
]
