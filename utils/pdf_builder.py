"""
PDF Builder - Generate comprehensive retirement planning reports using ReportLab
"""
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from utils.pdf_graphs import (
    render_cashflow_chart, render_income_breakdown_chart,
    render_cumulative_chart, render_tax_analysis_chart, create_summary_pie_chart
)
from typing import Dict, List, Any, Optional
from datetime import datetime
import io
import locale

# Try to set Hebrew locale for better number formatting
try:
    locale.setlocale(locale.LC_ALL, 'he_IL.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Hebrew_Israel.1255')
    except:
        pass  # Use default locale

class RetirementReportBuilder:
    """
    Comprehensive retirement planning report builder
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        self.page_width, self.page_height = A4
        
    def setup_custom_styles(self):
        """Setup custom paragraph styles"""
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2E86AB'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            textColor=HexColor('#A23B72'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#1B5E7A'),
            fontName='Helvetica-Bold'
        ))
        
        # Body text with Hebrew support
        self.styles.add(ParagraphStyle(
            name='BodyHebrew',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_RIGHT,  # Right-to-left for Hebrew
            fontName='Helvetica'
        ))
        
        # Highlight box style
        self.styles.add(ParagraphStyle(
            name='HighlightBox',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            spaceBefore=12,
            leftIndent=20,
            rightIndent=20,
            backColor=HexColor('#F0F8FF'),
            borderColor=HexColor('#2E86AB'),
            borderWidth=1,
            borderPadding=10
        ))

    def build_pdf(self, context: Dict[str, Any], cashflow: List[Dict[str, Any]], file_path: str) -> str:
        """
        Build complete PDF report
        """
        
        # Create document
        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Build story (content)
        story = []
        
        # Cover page
        story.extend(self._build_cover_page(context))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._build_executive_summary(context, cashflow))
        story.append(PageBreak())
        
        # Detailed analysis
        story.extend(self._build_detailed_analysis(context, cashflow))
        story.append(PageBreak())
        
        # Charts and graphs
        story.extend(self._build_charts_section(cashflow))
        story.append(PageBreak())
        
        # Cashflow tables
        story.extend(self._build_cashflow_tables(cashflow))
        story.append(PageBreak())
        
        # Appendices
        story.extend(self._build_appendices(context))
        
        # Build PDF
        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        
        return file_path

    def _build_cover_page(self, context: Dict[str, Any]) -> List:
        """Build cover page"""
        
        elements = []
        
        # Title
        title = Paragraph("דוח תכנון פרישה מקיף", self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.5*inch))
        
        # Client information
        client = context.get('client', {})
        client_name = getattr(client, 'full_name', 'לקוח לא ידוע')
        
        client_info = f"""
        <b>שם הלקוח:</b> {client_name}<br/>
        <b>תאריך הדוח:</b> {datetime.now().strftime('%d/%m/%Y')}<br/>
        <b>גיל פרישה:</b> {context.get('retirement_age', 67)}<br/>
        <b>תוחלת חיים:</b> {context.get('life_expectancy', 85)}
        """
        
        elements.append(Paragraph(client_info, self.styles['BodyHebrew']))
        elements.append(Spacer(1, 1*inch))
        
        # Summary box
        summary_text = """
        <b>תקציר מנהלים:</b><br/>
        דוח זה מציג ניתוח מקיף של תכנית הפרישה האישית, כולל חישובי קצבה,
        מענקי פרישה, השלכות מס ותחזית תזרים מזומנים לכל שנות הפרישה.
        """
        
        elements.append(Paragraph(summary_text, self.styles['HighlightBox']))
        elements.append(Spacer(1, 1*inch))
        
        # Disclaimer
        disclaimer = """
        <i>הערה חשובה: הדוח מבוסס על נתונים שסופקו ועל הנחות כלכליות נוכחיות.
        תוצאות בפועל עשויות להיות שונות. מומלץ להתייעץ עם יועץ פנסיוני מוסמך.</i>
        """
        
        elements.append(Paragraph(disclaimer, self.styles['Normal']))
        
        return elements

    def _build_executive_summary(self, context: Dict[str, Any], cashflow: List[Dict[str, Any]]) -> List:
        """Build executive summary section"""
        
        elements = []
        
        # Section title
        elements.append(Paragraph("תקציר מנהלים", self.styles['CustomSubtitle']))
        
        # Calculate summary statistics
        if cashflow:
            total_gross = sum(entry['gross_income'] for entry in cashflow)
            total_net = sum(entry['net_income'] for entry in cashflow)
            total_tax = sum(entry['tax'] for entry in cashflow)
            avg_annual_net = total_net / len(cashflow) if cashflow else 0
            effective_tax_rate = (total_tax / total_gross * 100) if total_gross > 0 else 0
        else:
            total_gross = total_net = total_tax = avg_annual_net = effective_tax_rate = 0
        
        # Summary table
        summary_data = [
            ['פריט', 'סכום (ש"ח)', 'הערות'],
            ['סה"כ הכנסה ברוטו', f'{total_gross:,.0f}', 'כל שנות הפרישה'],
            ['סה"כ מס', f'{total_tax:,.0f}', f'שיעור ממוצע: {effective_tax_rate:.1f}%'],
            ['סה"כ הכנסה נטו', f'{total_net:,.0f}', 'לאחר ניכוי מס'],
            ['ממוצע שנתי נטו', f'{avg_annual_net:,.0f}', 'הכנסה שנתית ממוצעת'],
            ['ממוצע חודשי נטו', f'{avg_annual_net/12:,.0f}', 'הכנסה חודשית ממוצעת']
        ]
        
        summary_table = Table(summary_data, colWidths=[4*cm, 3*cm, 5*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 1, black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Key insights
        insights_title = Paragraph("תובנות מרכזיות", self.styles['SectionHeader'])
        elements.append(insights_title)
        
        insights = []
        
        if cashflow:
            # Find peak income year
            peak_year_data = max(cashflow, key=lambda x: x['net_income'])
            insights.append(f"• שנת ההכנסה הגבוהה ביותר: {peak_year_data['year']} ({peak_year_data['net_income']:,.0f} ש\"ח)")
            
            # Tax burden analysis
            if effective_tax_rate > 25:
                insights.append(f"• נטל המס גבוה יחסית ({effective_tax_rate:.1f}%) - מומלץ לבחון אפשרויות אופטימיזציה")
            else:
                insights.append(f"• נטל המס סביר ({effective_tax_rate:.1f}%)")
            
            # Pension vs grants analysis
            total_pension = sum(entry.get('pension_income', 0) for entry in cashflow)
            total_grants = sum(entry.get('grant_income', 0) for entry in cashflow)
            
            if total_pension > total_grants:
                insights.append(f"• הכנסה מקצבאות ({total_pension:,.0f} ש\"ח) גבוהה מהכנסה ממענקים ({total_grants:,.0f} ש\"ח)")
            else:
                insights.append(f"• הכנסה ממענקים ({total_grants:,.0f} ש\"ח) גבוהה מהכנסה מקצבאות ({total_pension:,.0f} ש\"ח)")
        
        for insight in insights:
            elements.append(Paragraph(insight, self.styles['Normal']))
        
        return elements

    def _build_detailed_analysis(self, context: Dict[str, Any], cashflow: List[Dict[str, Any]]) -> List:
        """Build detailed analysis section"""
        
        elements = []
        
        # Section title
        elements.append(Paragraph("ניתוח מפורט", self.styles['CustomSubtitle']))
        
        # Pension calculation details
        pension_calc = context.get('pension_calculation', {})
        
        elements.append(Paragraph("פירוט חישוב קצבה", self.styles['SectionHeader']))
        
        pension_details = f"""
        <b>סך הון פנסיוני:</b> {pension_calc.get('total_capital', 0):,.0f} ש"ח<br/>
        <b>השפעת שריונים:</b> {pension_calc.get('reservation_impact', 0):,.0f} ש"ח<br/>
        <b>הון יעיל לקצבה:</b> {pension_calc.get('effective_capital', 0):,.0f} ש"ח<br/>
        <b>שנות פרישה:</b> {pension_calc.get('years_in_retirement', 0)} שנים<br/>
        <b>קצבה שנתית:</b> {pension_calc.get('annual_pension', 0):,.0f} ש"ח<br/>
        <b>קצבה חודשית:</b> {pension_calc.get('monthly_pension', 0):,.0f} ש"ח
        """
        
        elements.append(Paragraph(pension_details, self.styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Grant analysis
        processed_grants = context.get('processed_grants', [])
        if processed_grants:
            elements.append(Paragraph("ניתוח מענקים", self.styles['SectionHeader']))
            
            grant_data = [['סוג מענק', 'סכום מקורי', 'השפעת שריון', 'שנת תשלום']]
            
            for grant in processed_grants:
                grant_data.append([
                    grant.get('grant_type', 'לא מוגדר'),
                    f"{grant.get('original_amount', 0):,.0f}",
                    f"{grant.get('reservation_impact', 0):,.0f}",
                    str(grant.get('payment_year', ''))
                ])
            
            grant_table = Table(grant_data, colWidths=[3*cm, 3*cm, 3*cm, 2.5*cm])
            grant_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
            ]))
            
            elements.append(grant_table)
        
        return elements

    def _build_charts_section(self, cashflow: List[Dict[str, Any]]) -> List:
        """Build charts and graphs section"""
        
        elements = []
        
        # Section title
        elements.append(Paragraph("גרפים וניתוחים חזותיים", self.styles['CustomSubtitle']))
        
        if not cashflow:
            elements.append(Paragraph("אין נתוני תזרים זמינים להצגה", self.styles['Normal']))
            return elements
        
        # Cashflow chart
        try:
            cashflow_chart = render_cashflow_chart(cashflow, "תחזית תזרים מזומנים")
            elements.append(Paragraph("תזרים מזומנים לאורך זמן", self.styles['SectionHeader']))
            elements.append(Image(cashflow_chart, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 0.2*inch))
        except Exception as e:
            elements.append(Paragraph(f"שגיאה ביצירת גרף תזרים: {str(e)}", self.styles['Normal']))
        
        # Income breakdown chart
        try:
            breakdown_chart = render_income_breakdown_chart(cashflow, "פירוט הכנסות לפי מקור")
            elements.append(Paragraph("פירוט הכנסות לפי מקור", self.styles['SectionHeader']))
            elements.append(Image(breakdown_chart, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 0.2*inch))
        except Exception as e:
            elements.append(Paragraph(f"שגיאה ביצירת גרף פירוט: {str(e)}", self.styles['Normal']))
        
        # Cumulative chart
        try:
            cumulative_chart = render_cumulative_chart(cashflow, "הכנסה מצטברת")
            elements.append(Paragraph("הכנסה מצטברת", self.styles['SectionHeader']))
            elements.append(Image(cumulative_chart, width=6*inch, height=4*inch))
            elements.append(Spacer(1, 0.2*inch))
        except Exception as e:
            elements.append(Paragraph(f"שגיאה ביצירת גרף מצטבר: {str(e)}", self.styles['Normal']))
        
        return elements

    def _build_cashflow_tables(self, cashflow: List[Dict[str, Any]]) -> List:
        """Build detailed cashflow tables"""
        
        elements = []
        
        # Section title
        elements.append(Paragraph("טבלאות תזרים מפורטות", self.styles['CustomSubtitle']))
        
        if not cashflow:
            elements.append(Paragraph("אין נתוני תזרים זמינים", self.styles['Normal']))
            return elements
        
        # Split cashflow into chunks for multiple tables if needed
        chunk_size = 15
        for i in range(0, len(cashflow), chunk_size):
            chunk = cashflow[i:i + chunk_size]
            
            # Table header
            table_data = [['שנה', 'הכנסה ברוטו', 'קצבה', 'מענקים', 'מס', 'הכנסה נטו']]
            
            # Add data rows
            for entry in chunk:
                table_data.append([
                    str(entry['year']),
                    f"{entry['gross_income']:,.0f}",
                    f"{entry.get('pension_income', 0):,.0f}",
                    f"{entry.get('grant_income', 0):,.0f}",
                    f"{entry['tax']:,.0f}",
                    f"{entry['net_income']:,.0f}"
                ])
            
            # Create table
            table = Table(table_data, colWidths=[1.5*cm, 2.5*cm, 2*cm, 2*cm, 2*cm, 2.5*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 0.3*inch))
        
        return elements

    def _build_appendices(self, context: Dict[str, Any]) -> List:
        """Build appendices section"""
        
        elements = []
        
        # Section title
        elements.append(Paragraph("נספחים", self.styles['CustomSubtitle']))
        
        # Tax parameters appendix
        elements.append(Paragraph("נספח א': פרמטרי מס", self.styles['SectionHeader']))
        
        tax_params = context.get('tax_parameters', {})
        brackets = tax_params.get('brackets', [])
        
        if brackets:
            tax_data = [['מדרגה', 'מ-', 'עד', 'שיעור מס']]
            
            for i, bracket in enumerate(brackets):
                tax_data.append([
                    str(i + 1),
                    f"{bracket.get('min', 0):,.0f}",
                    f"{bracket.get('max', 'ללא הגבלה'):,.0f}" if isinstance(bracket.get('max'), (int, float)) else "ללא הגבלה",
                    f"{bracket.get('rate', 0) * 100:.1f}%"
                ])
            
            tax_table = Table(tax_data, colWidths=[2*cm, 3*cm, 3*cm, 2*cm])
            tax_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F18F01')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#FFF8E1')])
            ]))
            
            elements.append(tax_table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Assumptions appendix
        elements.append(Paragraph("נספח ב': הנחות חישוב", self.styles['SectionHeader']))
        
        assumptions = f"""
        • <b>שיעור הצמדה:</b> {context.get('indexation_rate', 0.02) * 100:.1f}% שנתי<br/>
        • <b>גיל פרישה:</b> {context.get('retirement_age', 67)} שנים<br/>
        • <b>תוחלת חיים:</b> {context.get('life_expectancy', 85)} שנים<br/>
        • <b>מכפיל שריון מענקים:</b> 1.35<br/>
        • <b>בסיס חישוב:</b> נתונים נכון ל-{datetime.now().strftime('%d/%m/%Y')}
        """
        
        elements.append(Paragraph(assumptions, self.styles['Normal']))
        
        return elements

    def _add_header_footer(self, canvas, doc):
        """Add header and footer to pages"""
        
        canvas.saveState()
        
        # Header
        canvas.setFont('Helvetica-Bold', 12)
        canvas.setFillColor(HexColor('#2E86AB'))
        canvas.drawString(2*cm, A4[1] - 1.5*cm, "דוח תכנון פרישה")
        
        # Footer
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(black)
        canvas.drawRightString(A4[0] - 2*cm, 1*cm, f"עמוד {doc.page}")
        canvas.drawString(2*cm, 1*cm, f"נוצר ב-{datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        canvas.restoreState()

def build_pdf(context: Dict[str, Any], cashflow: List[Dict[str, Any]], file_path: str) -> str:
    """
    Main function to build PDF report
    """
    
    builder = RetirementReportBuilder()
    return builder.build_pdf(context, cashflow, file_path)
