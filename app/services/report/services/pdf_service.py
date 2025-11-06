"""
PDF service for report generation - handles PDF creation
"""
import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from app.models import Client, Scenario
from ..fonts import ensure_fonts, get_default_font

_logger = logging.getLogger(__name__)


class PDFService:
    """Service for creating PDF documents"""
    
    @staticmethod
    def create_pdf_with_cashflow(
        client: Client,
        scenario: Scenario,
        cashflow_data: List[Dict[str, Any]],
        yearly_totals: Dict[str, Dict[str, float]],
        chart_cashflow: Optional[bytes],
        sections: Dict[str, bool],
        date_range: str
    ) -> bytes:
        """
        Create PDF with cashflow data and charts.
        
        Args:
            client: Client object
            scenario: Scenario object
            cashflow_data: Monthly cashflow data from Sprint 7
            yearly_totals: Aggregated yearly totals
            chart_cashflow: Chart image as bytes
            sections: Which sections to include
            date_range: Date range string for display
            
        Returns:
            PDF as bytes
        """
        ensure_fonts()
        buffer = io.BytesIO()
        
        # Get default Hebrew font
        default_font = get_default_font()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Hebrew-compatible styles
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
        
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=hebrew_style,
            fontSize=14,
            spaceAfter=10,
            textColor=colors.darkblue
        )
        
        # Title page
        story.append(Paragraph("דוח תזרים נטו חודשי", title_style))
        story.append(Spacer(1, 20))
        
        # Header information
        header_data = [
            ['מזהה לקוח:', str(client.id)],
            ['שם לקוח:', client.full_name or 'N/A'],
            ['מזהה תרחיש:', str(scenario.id)],
            ['טווח תאריכים:', date_range],
            ['תדירות:', 'חודשי'],
            ['תאריך יצירה:', datetime.now().strftime('%d/%m/%Y %H:%M')]
        ]
        
        header_table = Table(header_data, colWidths=[2*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), default_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 30))
        
        # Summary section
        if sections.get('summary', True):
            story.append(Paragraph("סיכום שנתי", section_style))
            
            summary_data = [['שנה', 'הכנסות', 'הוצאות', 'הכנסות נוספות', 'החזרי הון', 'נטו']]
            for year, totals in sorted(yearly_totals.items()):
                summary_data.append([
                    year,
                    f"{totals['inflow']:,.0f} ₪",
                    f"{totals['outflow']:,.0f} ₪",
                    f"{totals['additional_income_net']:,.0f} ₪",
                    f"{totals['capital_return_net']:,.0f} ₪",
                    f"{totals['net']:,.0f} ₪"
                ])
            
            summary_table = Table(summary_data, colWidths=[0.8*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), default_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
        
        # Monthly cashflow table
        if sections.get('cashflow_table', True):
            story.append(Paragraph("פירוט תזרים חודשי", section_style))
            
            table_data = [['תאריך', 'הכנסות', 'הוצאות', 'הכנסות נוספות', 'החזרי הון', 'נטו']]
            for row in cashflow_data:
                # Handle both string and date object formats
                date_val = row['date']
                if hasattr(date_val, 'strftime'):
                    date_str = date_val.strftime('%Y-%m')
                else:
                    date_str = str(date_val)[:7]  # YYYY-MM format
                
                table_data.append([
                    date_str,
                    f"{row.get('inflow', 0):,.0f} ₪",
                    f"{row.get('outflow', 0):,.0f} ₪",
                    f"{row.get('additional_income_net', 0):,.0f} ₪",
                    f"{row.get('capital_return_net', 0):,.0f} ₪",
                    f"{row.get('net', 0):,.0f} ₪"
                ])
            
            cashflow_table = Table(table_data, colWidths=[1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            cashflow_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), default_font),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                # Highlight negative values in red
                ('TEXTCOLOR', (5, 1), (5, -1), colors.red),  # Net column
            ]))
            
            story.append(cashflow_table)
            story.append(Spacer(1, 20))
        
        # Net cashflow chart
        if sections.get('net_chart', True) and chart_cashflow:
            story.append(Paragraph("גרף תזרים נטו חודשי", section_style))
            cashflow_img = Image(io.BytesIO(chart_cashflow), width=6*inch, height=3*inch)
            story.append(cashflow_img)
            story.append(Spacer(1, 20))
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            f"דוח נוצר בתאריך: {datetime.now().strftime('%d/%m/%Y %H:%M')} | מערכת תכנון פרישה", 
            ParagraphStyle('Footer', parent=hebrew_style, fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
        ))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer.getvalue()
