"""
Report service for generating PDF reports with scenarios, cashflow, and summary data.
Supports Hebrew/RTL text and integrates with existing scenario/calculation data.
"""

import io
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
# Configure matplotlib before any plotting occurs
mpl.use("Agg", force=True)
mpl.rcParams['font.family'] = ['DejaVu Sans']
mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Noto Sans Hebrew', 'Arial Unicode MS']
# Reduce font logging noise
import logging
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

from sqlalchemy.orm import Session
from app.models import Client, Scenario, Employment, Employer
from app.schemas.scenario import ScenarioOut
from app.schemas.report import ReportPdfRequest
from app.services.cashflow_service import generate_cashflow
from app.services.case_service import detect_case
from app.schemas.case import ClientCase

_logger = logging.getLogger(__name__)
_DEFAULT_HEBREW_FONT = "DejaVu Sans"  # Default to DejaVu which is bundled with matplotlib
_FONTS_READY = False

def _register_font_once(alias: str, path: str) -> str:
    try:
        if alias in pdfmetrics.getRegisteredFontNames():
            return alias
        pdfmetrics.registerFont(TTFont(alias, path))
        return alias
    except Exception as e:
        _logger.warning("Font registration failed (%s -> %s): %s", alias, path, e)
        return "Helvetica"

def ensure_fonts():
    """Call only from rendering functions (not at import time)."""
    global _FONTS_READY, _DEFAULT_HEBREW_FONT
    if _FONTS_READY:
        return
    # Build a prioritized list of possible TTF font paths that support Hebrew
    candidates = []
    # 1) Project-bundled font (if provided)
    candidates.append(os.path.join("app", "static", "fonts", "NotoSansHebrew-Regular.ttf"))
    
    # 2) Matplotlib-bundled DejaVuSans (portable across CI/OS)
    try:
        import matplotlib as mpl
        from matplotlib import font_manager as fm
        try:
            # Prefer an actual path to DejaVu Sans
            dv_path = fm.findfont("DejaVu Sans", fallback_to_default=False)
            if dv_path and os.path.exists(dv_path):
                candidates.append(dv_path)
        except Exception:
            pass
        # Fallback to data path lookup
        dv2 = os.path.join(mpl.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
        if os.path.exists(dv2):
            candidates.append(dv2)
    except Exception as e:
        _logger.warning("Matplotlib DejaVu font discovery failed: %s", e)

    # 3) Common Windows fonts (if available)
    for win_font in (
        r"C:\\Windows\\Fonts\\ARIALUNI.TTF",
        r"C:\\Windows\\Fonts\\Arial.ttf",
        r"C:\\Windows\\Fonts\\Tahoma.ttf",
    ):
        if os.path.exists(win_font):
            candidates.append(win_font)

    # 4) Common Linux path
    candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

    # Register the first available candidate
    for p in candidates:
        if os.path.exists(p):
            _DEFAULT_HEBREW_FONT = _register_font_once("HebrewUI", p)
            break

    # Configure Matplotlib to use a Unicode-capable font
    try:
        plt.rcParams["font.family"] = ["DejaVu Sans", "HebrewUI", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception as e:
        _logger.warning("Matplotlib font setup warning: %s", e)
    _FONTS_READY = True


class ReportService:
    """Service for generating PDF reports with scenarios and cashflow data."""
    
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
        # Detect case for client
        try:
            case_detection = detect_case(db, client.id)
            case_id = case_detection.case_id
            case_name = case_detection.case_name if hasattr(case_detection, 'case_name') else "standard"
            case_display_name = case_detection.display_name if hasattr(case_detection, 'display_name') else "מקרה רגיל"
            case_reasons = case_detection.reasons if hasattr(case_detection, 'reasons') else []
        except Exception as e:
            _logger.warning(f"Case detection failed for client {client.id}: {e}")
            case_id = 1
            case_name = "standard"
            case_display_name = "מקרה רגיל"
            case_reasons = ["זיהוי אוטומטי נכשל"]
        
        summary = {
            'client_info': {
                'full_name': client.full_name or 'N/A',
                'id_number': client.id_number or 'N/A',
                'birth_date': client.birth_date.strftime('%d/%m/%Y') if client.birth_date else 'N/A',
                'email': client.email or 'N/A',
                'phone': client.phone or 'N/A',
                'address': f"{client.address_street or ''}, {client.address_city or ''}".strip(', ') or 'N/A'
            },
            'employment_info': [],
            'scenarios_summary': [],
            'cashflow_data': {},
            'report_metadata': {
                'generated_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'scenarios_count': len(scenarios),
                'client_is_active': client.is_active
            },
            'case': {
                'id': case_id,
                'name': case_name,
                'display_name': case_display_name,
                'reasons': case_reasons
            }
        }
        
        # Get employment information
        try:
            employments = db.query(Employment).filter(
                Employment.client_id == client.id
            ).order_by(Employment.start_date.desc()).all()
            
            for emp in employments:
                employer = db.query(Employer).filter(Employer.id == emp.employer_id).first()
                emp_info = {
                    'employer_name': employer.name if employer else 'N/A',
                    'start_date': emp.start_date.strftime('%d/%m/%Y') if emp.start_date else 'N/A',
                    'end_date': emp.end_date.strftime('%d/%m/%Y') if emp.end_date else 'פעיל',
                    'monthly_salary': f"{emp.monthly_salary_nominal:,.0f} ₪" if emp.monthly_salary_nominal else 'N/A',
                    'is_current': emp.is_current
                }
                summary['employment_info'].append(emp_info)
        except Exception as e:
            print(f"Error fetching employment data: {e}")
            summary['employment_info'] = [{'error': 'שגיאה בטעינת נתוני תעסוקה'}]
        
        # Process scenarios
        for scenario in scenarios:
            scenario_summary = {
                'id': scenario.id,
                'name': f"תרחיש {scenario.id}",
                'created_at': scenario.created_at.strftime('%d/%m/%Y') if scenario.created_at else 'N/A',
                'has_results': bool(scenario.summary_results and scenario.cashflow_projection)
            }
            
            # Parse summary results if available
            if scenario.summary_results:
                try:
                    results = json.loads(scenario.summary_results) if isinstance(scenario.summary_results, str) else scenario.summary_results
                    scenario_summary.update({
                        'total_pension': results.get('total_pension_at_retirement', 'N/A'),
                        'monthly_pension': results.get('monthly_pension', 'N/A'),
                        'total_grants': results.get('total_grants', 'N/A'),
                        'net_worth_at_retirement': results.get('net_worth_at_retirement', 'N/A')
                    })
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing scenario {scenario.id} results: {e}")
                    scenario_summary['parse_error'] = True
            
            summary['scenarios_summary'].append(scenario_summary)
            
            # Store cashflow data for charts
            if scenario.cashflow_projection:
                try:
                    cashflow = json.loads(scenario.cashflow_projection) if isinstance(scenario.cashflow_projection, str) else scenario.cashflow_projection
                    summary['cashflow_data'][scenario.id] = cashflow
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing scenario {scenario.id} cashflow: {e}")
        
        return summary
    
    @staticmethod
    def render_cashflow_chart(cashflow_projection: Dict[str, Any]) -> bytes:
        """
        Render cashflow chart as PNG bytes for PDF embedding.
        
        Args:
            cashflow_projection: Cashflow data from scenario
            
        Returns:
            PNG image as bytes
        """
        ensure_fonts()  # Initialize fonts for chart rendering
        try:
            # Set up matplotlib for Hebrew support
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Extract data from cashflow projection
            if isinstance(cashflow_projection, dict) and 'annual_cashflow' in cashflow_projection:
                annual_data = cashflow_projection['annual_cashflow']
                years = list(range(len(annual_data)))
                values = [entry.get('net_cashflow', 0) for entry in annual_data]
                
                # Plot the cashflow
                ax.plot(years, values, linewidth=2, color='#2E86AB', marker='o', markersize=4)
                ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
                
                # Formatting
                ax.set_xlabel('שנים', fontsize=12)
                ax.set_ylabel('תזרים נטו (₪)', fontsize=12)
                ax.set_title('תחזית תזרים נטו שנתי', fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3)
                
                # Format y-axis with thousands separator
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
                
            else:
                # Fallback: create empty chart with message
                ax.text(0.5, 0.5, 'אין נתוני תזרים זמינים', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
            
            plt.tight_layout()
            
            # Save to bytes
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            return img_buffer.getvalue()
            
        except Exception as e:
            print(f"Error creating cashflow chart: {e}")
            # Return empty chart
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(0.5, 0.5, f'שגיאה ביצירת גרף: {str(e)}', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            return img_buffer.getvalue()
    
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
        ensure_fonts()  # Initialize fonts for chart rendering
        try:
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
            
            for i, scenario in enumerate(scenarios[:4]):  # Limit to 4 scenarios
                if scenario.cashflow_projection:
                    try:
                        cashflow = json.loads(scenario.cashflow_projection) if isinstance(scenario.cashflow_projection, str) else scenario.cashflow_projection
                        if 'annual_cashflow' in cashflow:
                            annual_data = cashflow['annual_cashflow']
                            years = list(range(len(annual_data)))
                            values = [entry.get('net_cashflow', 0) for entry in annual_data]
                            
                            ax.plot(years, values, 
                                   linewidth=2, 
                                   color=colors[i % len(colors)], 
                                   label=f'תרחיש {scenario.id}',
                                   marker='o', 
                                   markersize=3)
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"Error parsing scenario {scenario.id} for comparison: {e}")
            
            ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
            ax.set_xlabel('שנים', fontsize=12)
            ax.set_ylabel('תזרים נטו (₪)', fontsize=12)
            ax.set_title('השוואת תרחישים - תזרים נטו', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format y-axis
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
            
            plt.tight_layout()
            
            # Save to bytes
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            return img_buffer.getvalue()
            
        except Exception as e:
            print(f"Error creating comparison chart: {e}")
            # Return empty chart
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(0.5, 0.5, f'שגיאה ביצירת גרף השוואה: {str(e)}', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)
            
            return img_buffer.getvalue()
    
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
        ensure_fonts()  # Initialize fonts for rendering
        buffer = io.BytesIO()
        
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
            fontName=_DEFAULT_HEBREW_FONT,
            fontSize=10,
            alignment=2,  # Right alignment for Hebrew
            wordWrap='RTL'
        )
        
        title_style = ParagraphStyle(
            'HebrewTitle',
            parent=styles['Title'],
            fontName=_DEFAULT_HEBREW_FONT,
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
            ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(client_table)
        story.append(Spacer(1, 20))
        
        # Case information
        story.append(Paragraph("סיווג מקרה לקוח", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
        
        case_desc = {
            ClientCase.NO_CURRENT_EMPLOYER: "לקוח ללא מעסיק נוכחי. התוכנית אינה כוללת חישובי פיצויים או קצבה ממעסיק נוכחי.",
            ClientCase.SELF_EMPLOYED_ONLY: "לקוח עצמאי בלבד. התוכנית מתבססת על הכנסה עסקית עצמאית.",
            ClientCase.PAST_RETIREMENT_AGE: "לקוח שכבר הגיע לגיל פרישה. התוכנית מתמקדת במיצוי זכויות קיימות.",
            ClientCase.ACTIVE_NO_LEAVE: "לקוח עם מעסיק נוכחי ללא תכנון עזיבה. התוכנית אינה כוללת חישובי פיצויים סופיים.",
            ClientCase.REGULAR_WITH_LEAVE: "לקוח עם מעסיק נוכחי ותוכנית פרישה. התוכנית כוללת חישובי פיצויים וקצבה מלאים."  
        }.get(summary['case']['id'], "לא מוגדר")
        
        case_data = [
            ['סוג מקרה:', summary['case']['display_name']],
            ['תיאור:', case_desc],
            ['גורמים מזהים:', ' | '.join(summary['case']['reasons'])]
        ]
        
        case_table = Table(case_data, colWidths=[1.5*inch, 3.5*inch])
        case_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(case_table)
        story.append(Spacer(1, 20))
        
        # Employment information
        if summary['employment_info']:
            story.append(Paragraph("פרטי תעסוקה", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
            
            emp_data = [['מעסיק', 'תאריך התחלה', 'תאריך סיום', 'משכורת חודשית', 'סטטוס']]
            for emp in summary['employment_info'][:5]:  # Limit to 5 employments
                if 'error' in emp:
                    emp_data.append([emp['error'], '', '', '', ''])
                else:
                    emp_data.append([
                        emp['employer_name'],
                        emp['start_date'],
                        emp['end_date'],
                        emp['monthly_salary'],
                        'פעיל' if emp['is_current'] else 'לא פעיל'
                    ])
            
            emp_table = Table(emp_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
            emp_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            
            story.append(emp_table)
            story.append(Spacer(1, 20))
        
        # Scenarios summary
        story.append(Paragraph("סיכום תרחישים", ParagraphStyle('SectionTitle', parent=hebrew_style, fontSize=14, spaceAfter=10)))
        
        scenario_data = [['תרחיש', 'תאריך יצירה', 'סה"כ פנסיה', 'פנסיה חודשית', 'מענקים']]
        for scenario_sum in summary['scenarios_summary']:
            scenario_data.append([
                scenario_sum['name'],
                scenario_sum['created_at'],
                f"{scenario_sum.get('total_pension', 'N/A'):,.0f} ₪" if isinstance(scenario_sum.get('total_pension'), (int, float)) else 'N/A',
                f"{scenario_sum.get('monthly_pension', 'N/A'):,.0f} ₪" if isinstance(scenario_sum.get('monthly_pension'), (int, float)) else 'N/A',
                f"{scenario_sum.get('total_grants', 'N/A'):,.0f} ₪" if isinstance(scenario_sum.get('total_grants'), (int, float)) else 'N/A'
            ])
        
        scenario_table = Table(scenario_data, colWidths=[1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        scenario_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        
        story.append(scenario_table)
        story.append(Spacer(1, 30))
        
        # Add charts
        if chart_cashflow:
            story.append(Paragraph("גרף תזרים נטו", ParagraphStyle('ChartTitle', parent=hebrew_style, fontSize=12, spaceAfter=10)))
            cashflow_img = Image(io.BytesIO(chart_cashflow), width=6*inch, height=3*inch)
            story.append(cashflow_img)
            story.append(Spacer(1, 20))
        
        if chart_compare and len(scenarios) > 1:
            story.append(Paragraph("השוואת תרחישים", ParagraphStyle('ChartTitle', parent=hebrew_style, fontSize=12, spaceAfter=10)))
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


def generate_report_pdf(
    db: Session,
    client_id: int,
    scenario_id: int = None,
    request: ReportPdfRequest = None
) -> bytes:
    """
    Generate PDF report for client scenarios with cashflow data and charts.
    
    Args:
        db: Database session
        client_id: Client ID
        scenario_id: Single scenario ID (path parameter)
        request: Report request containing date range and sections
        
    Returns:
        PDF content as bytes
    """
    start_time = datetime.now()
    _logger.info(f"Starting PDF report generation for client={client_id}, scenario={scenario_id}, range={request.from_}-{request.to}")
    
    try:
        # Get client data
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Defensive handling: determine scenario_ids from multiple sources
        scenario_ids = []
        
        # Priority 1: scenario_id from path parameter
        if scenario_id is not None:
            scenario_ids = [scenario_id]
            _logger.info(f"Using scenario_id from path: {scenario_id}")
        
        # Priority 2: scenario_ids from request body (if exists)
        elif hasattr(request, 'scenario_ids') and request.scenario_ids:
            scenario_ids = request.scenario_ids
            _logger.info(f"Using scenario_ids from request body: {scenario_ids}")
        
        # Priority 3: scenarios from request body (alternative field name)
        elif hasattr(request, 'scenarios') and request.scenarios:
            scenario_ids = request.scenarios
            _logger.info(f"Using scenarios from request body: {scenario_ids}")
        
        # Fallback: error if no scenarios found
        else:
            raise ValueError("No scenario ID provided in path or request body")
        
        # Validate scenarios exist
        scenarios = db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()
        
        # Auto-detect case for consistency
        try:
            from app.services.case_service import detect_case
            case_detection = detect_case(db, client_id)
            case_id = case_detection.case_id
            _logger.info(f"Detected case_id={case_id} for client={client_id}")
        except Exception as e:
            _logger.warning(f"Case detection failed, using default case: {e}")
            case_id = 1  # Default to standard case
        
        # Generate cashflow data using Sprint 7 service
        cashflow_data = []
        for sid in scenario_ids:
            try:
                _logger.info(f"Generating cashflow for scenario_id={sid}")
                cashflow_rows = generate_cashflow(
                    db=db,
                    client_id=client_id,
                    scenario_id=sid,
                    start_ym=request.from_,
                    end_ym=request.to,
                    case_id=case_id
                )
                _logger.info(f"Generated {len(cashflow_rows)} cashflow rows for scenario_id={sid}")
                cashflow_data.extend(cashflow_rows)
            except Exception as e:
                _logger.error(f"Error generating cashflow for scenario_id={sid}: {e}")
                raise ValueError(f"Failed to generate cashflow for scenario_id={sid}: {e}")
        
        # Calculate yearly totals for summary
        yearly_totals = {}
        for row in cashflow_data:
            # Handle both string and date object formats
            date_val = row['date']
            if hasattr(date_val, 'strftime'):
                year = date_val.strftime('%Y')
            else:
                year = str(date_val)[:4]  # Extract year from string
            if year not in yearly_totals:
                yearly_totals[year] = {
                    'inflow': 0,
                    'outflow': 0,
                    'additional_income_net': 0,
                    'capital_return_net': 0,
                    'net': 0
                }
            yearly_totals[year]['inflow'] += row.get('inflow', 0)
            yearly_totals[year]['outflow'] += row.get('outflow', 0)
            yearly_totals[year]['additional_income_net'] += row.get('additional_income_net', 0)
            yearly_totals[year]['capital_return_net'] += row.get('capital_return_net', 0)
            yearly_totals[year]['net'] += row.get('net', 0)
        
        # Create chart data for matplotlib
        chart_data = {
            'dates': [row['date'].strftime('%Y-%m') if hasattr(row['date'], 'strftime') else str(row['date'])[:7] for row in cashflow_data],
            'net_values': [row.get('net', 0) for row in cashflow_data]
        }
        
        # Generate charts
        chart_cashflow = None
        if request.sections.get('net_chart', True):
            chart_cashflow = create_net_cashflow_chart(chart_data)
        
        # Build PDF content
        pdf_content = create_pdf_with_cashflow(
            client=client,
            scenarios=scenarios,
            cashflow_data=cashflow_data,
            yearly_totals=yearly_totals,
            chart_cashflow=chart_cashflow,
            sections=request.sections,
            date_range=f"{request.from_} - {request.to}"
        )
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        pdf_size = len(pdf_content)
        _logger.info(f"PDF report completed in {duration:.2f}s, size={pdf_size} bytes")
        
        return pdf_content
        
    except ValueError as e:
        # Specific validation errors - log and re-raise
        _logger.error(f"PDF generation validation error: {e}")
        raise
    except Exception as e:
        # Log detailed error with traceback
        import traceback
        _logger.error(f"Unexpected error in PDF generation:\n{traceback.format_exc()}")
        _logger.error(f"Error details: {e}")
        # Safer to re-raise as ValueError for API consistency
        raise ValueError(f"Internal PDF generation error: {e}")


def create_net_cashflow_chart(chart_data: Dict[str, List]) -> bytes:
    """
    Create net cashflow chart using matplotlib.
    
    Args:
        chart_data: Dictionary with 'dates' and 'net_values' lists
        
    Returns:
        PNG image as bytes
    """
    ensure_fonts()
    try:
        plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        dates = chart_data['dates']
        values = chart_data['net_values']
        
        # Convert dates to month indices for plotting
        month_indices = list(range(len(dates)))
        month_labels = [date[:7] for date in dates]  # YYYY-MM format
        
        # Plot the line
        ax.plot(month_indices, values, linewidth=2, color='#2E86AB', marker='o', markersize=4)
        ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        
        # Formatting
        ax.set_xlabel('חודש', fontsize=12)
        ax.set_ylabel('תזרים נטו (₪)', fontsize=12)
        ax.set_title('תזרים נטו חודשי', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Set x-axis labels (show every 3rd month to avoid crowding)
        step = max(1, len(month_labels) // 4)
        ax.set_xticks(month_indices[::step])
        ax.set_xticklabels(month_labels[::step], rotation=45)
        
        # Format y-axis with thousands separator
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
        
        plt.tight_layout()
        
        # Save to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close(fig)
        
        return img_buffer.getvalue()
        
    except Exception as e:
        _logger.error(f"Error creating net cashflow chart: {e}")
        # Return empty chart
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, f'שגיאה ביצירת גרף: {str(e)}', 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=12)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close(fig)
        
        return img_buffer.getvalue()


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
        fontName=_DEFAULT_HEBREW_FONT,
        fontSize=10,
        alignment=TA_RIGHT,
        wordWrap='RTL'
    )
    
    title_style = ParagraphStyle(
        'HebrewTitle',
        parent=styles['Title'],
        fontName=_DEFAULT_HEBREW_FONT,
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
        ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
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
            ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
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
            ('FONTNAME', (0, 0), (-1, -1), _DEFAULT_HEBREW_FONT),
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
