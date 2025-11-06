"""
Base report service - main entry point for report generation
Provides backward compatibility with original report_service.py
"""
import io
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models import Client, Scenario
from .services.data_service import DataService
from .services.pdf_service import PDFService
from .charts import render_cashflow_chart, render_scenarios_compare_chart
from .fonts import ensure_fonts

_logger = logging.getLogger(__name__)


class ReportService:
    """
    Main report service class - provides backward compatibility
    with original report_service.py implementation
    """
    
    def __init__(self):
        """Initialize the report service."""
        pass
    
    @staticmethod
    def build_summary_table(client: Client, scenarios: List[Scenario], db: Session) -> Dict[str, Any]:
        """
        Build summary table data for the PDF report.
        
        Args:
            client: Client object
            scenarios: List of scenario objects
            db: Database session
            
        Returns:
            Dictionary with summary data organized by sections
        """
        return DataService.build_summary_table(client, scenarios, db)
    
    @staticmethod
    def render_cashflow_chart(cashflow_projection: Dict[str, Any]) -> bytes:
        """
        Render cashflow chart as PNG bytes for PDF embedding.
        
        Args:
            cashflow_projection: Cashflow data from scenario
            
        Returns:
            PNG image as bytes
        """
        return render_cashflow_chart(cashflow_projection)
    
    def create_cashflow_chart(self, data):
        """Wrapper for render_cashflow_chart to maintain compatibility."""
        return self.render_cashflow_chart(data)
    
    @staticmethod
    def render_scenarios_compare_chart(scenarios: List[Scenario]) -> bytes:
        """
        Render scenarios comparison chart as PNG bytes.
        
        Args:
            scenarios: List of scenarios to compare
            
        Returns:
            PNG image as bytes
        """
        return render_scenarios_compare_chart(scenarios)
    
    @staticmethod
    def generate_pdf_report(
        client: Client,
        scenarios: List[Scenario],
        report_type: str = "comprehensive",
        include_charts: bool = True,
        include_cashflow: bool = True
    ) -> io.BytesIO:
        """
        Generate PDF report for client scenarios.
        
        Args:
            client: Client object
            scenarios: List of scenario objects
            report_type: Type of report to generate
            include_charts: Whether to include charts
            include_cashflow: Whether to include cashflow data
            
        Returns:
            PDF buffer
        """
        try:
            # Build summary data
            from app.database import get_db
            db = next(get_db())
            summary = DataService.build_summary_table(client, scenarios, db)
            
            # Generate charts if requested
            chart_cashflow = None
            chart_compare = None
            
            if include_charts and scenarios:
                # Generate cashflow chart for first scenario
                if scenarios[0].cashflow_projection:
                    try:
                        import json
                        cashflow_data = json.loads(scenarios[0].cashflow_projection) if isinstance(scenarios[0].cashflow_projection, str) else scenarios[0].cashflow_projection
                        chart_cashflow = render_cashflow_chart(cashflow_data)
                    except Exception as e:
                        _logger.error(f"Error generating cashflow chart: {e}")
                
                # Generate comparison chart if multiple scenarios
                if len(scenarios) > 1:
                    chart_compare = render_scenarios_compare_chart(scenarios)
            
            # Compose PDF
            pdf_content = ReportService.compose_pdf(
                client=client,
                scenarios=scenarios,
                summary=summary,
                chart_cashflow=chart_cashflow or b'',
                chart_compare=chart_compare or b''
            )
            
            # Return as BytesIO buffer
            buffer = io.BytesIO(pdf_content)
            return buffer
            
        except Exception as e:
            _logger.error(f"Error generating PDF report: {e}")
            # Create error PDF
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            story.append(Paragraph(f"שגיאה ביצירת דוח: {str(e)}", styles['Normal']))
            doc.build(story)
            buffer.seek(0)
            return buffer

    @staticmethod
    def compose_pdf(
        client: Client, 
        scenarios: List[Scenario], 
        summary: Dict[str, Any], 
        chart_cashflow: bytes, 
        chart_compare: bytes
    ) -> bytes:
        """
        Compose the final PDF report.
        
        Args:
            client: Client object
            scenarios: List of scenarios
            summary: Summary data dictionary
            chart_cashflow: Cashflow chart as bytes
            chart_compare: Comparison chart as bytes
            
        Returns:
            PDF as bytes
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from datetime import datetime
        from .fonts import get_default_font
        
        ensure_fonts()
        buffer = io.BytesIO()
        default_font = get_default_font()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build story (content)
        story = []
        styles = getSampleStyleSheet()
        
        # Hebrew-compatible style
        hebrew_style = ParagraphStyle(
            'Hebrew',
            parent=styles['Normal'],
            fontName=default_font,
            fontSize=10,
            alignment=TA_RIGHT,
            wordWrap='RTL'
        )
        
        title_style = ParagraphStyle(
            'HebrewTitle',
            parent=styles['Title'],
            fontName=default_font,
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        # Title
        story.append(Paragraph("דוח תכנון פרישה", title_style))
        story.append(Spacer(1, 20))
        
        # Client information section
        story.append(Paragraph("פרטי הלקוח", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
        
        client_data = [
            ['שם מלא:', summary['client_info']['full_name']],
            ['תעודת זהות:', summary['client_info']['id_number']],
            ['תאריך לידה:', summary['client_info']['birth_date']],
            ['דוא"ל:', summary['client_info']['email']],
            ['טלפון:', summary['client_info']['phone']],
            ['כתובת:', summary['client_info']['address']]
        ]
        
        client_table = Table(client_data, colWidths=[2*inch, 3*inch])
        client_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(client_table)
        story.append(Spacer(1, 20))
        
        # Scenarios summary
        if summary['scenarios_summary']:
            story.append(Paragraph("סיכום תרחישים", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
            
            for scenario_sum in summary['scenarios_summary']:
                story.append(Paragraph(f"<b>{scenario_sum['name']}</b>", hebrew_style))
                story.append(Paragraph(f"תאריך יצירה: {scenario_sum['created_at']}", hebrew_style))
                story.append(Spacer(1, 10))
        
        # Charts
        if chart_cashflow:
            story.append(Paragraph("גרף תזרים מזומנים", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
            cashflow_img = Image(io.BytesIO(chart_cashflow), width=6*inch, height=3*inch)
            story.append(cashflow_img)
            story.append(Spacer(1, 20))
        
        if chart_compare:
            story.append(Paragraph("השוואת תרחישים", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
            compare_img = Image(io.BytesIO(chart_compare), width=6*inch, height=3*inch)
            story.append(compare_img)
            story.append(Spacer(1, 20))
        
        # Footer information
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            f"דוח נוצר בתאריך: {summary['report_metadata']['generated_at']}", 
            ParagraphStyle('Footer', parent=hebrew_style, fontSize=8, alignment=TA_CENTER)
        ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer.getvalue()
