"""
PDF Report Export functionality using ReportLab
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.flowables import PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def export_pdf(client_id: int, scenarios: List[Dict[str, Any]], path: str) -> Dict[str, Any]:
    """
    Export PDF report with client scenarios and cashflow data
    
    Args:
        client_id: Client ID
        scenarios: List of scenario data dictionaries
        path: Output file path
        
    Returns:
        Dict with export results and metadata
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20
        )
        
        # Build PDF content
        story = []
        
        # Title
        title = Paragraph(f"Retirement Planning Report - Client {client_id}", title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Generation info
        generation_info = Paragraph(
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles['Normal']
        )
        story.append(generation_info)
        story.append(Spacer(1, 20))
        
        # Executive Summary
        summary_heading = Paragraph("Executive Summary", heading_style)
        story.append(summary_heading)
        
        summary_data = [
            ['Metric', 'Value'],
            ['Client ID', str(client_id)],
            ['Number of Scenarios', str(len(scenarios))],
            ['Report Date', datetime.now().strftime('%Y-%m-%d')],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Process each scenario
        for i, scenario in enumerate(scenarios, 1):
            scenario_heading = Paragraph(f"Scenario {i}: {scenario.get('scenario_name', 'Unnamed')}", heading_style)
            story.append(scenario_heading)
            
            # Scenario parameters
            params_text = f"Planning Flags: Tax Planning: {scenario.get('apply_tax_planning', False)}, "
            params_text += f"Capitalization: {scenario.get('apply_capitalization', False)}, "
            params_text += f"Exemption Shield: {scenario.get('apply_exemption_shield', False)}"
            
            params_para = Paragraph(params_text, styles['Normal'])
            story.append(params_para)
            story.append(Spacer(1, 12))
            
            # Cashflow data
            cashflow_data = scenario.get('cashflow_projection')
            if cashflow_data:
                if isinstance(cashflow_data, str):
                    try:
                        cashflow_data = json.loads(cashflow_data)
                    except json.JSONDecodeError:
                        cashflow_data = None
                
                if cashflow_data and 'monthly' in cashflow_data:
                    # Monthly cashflow table
                    cashflow_heading = Paragraph("Monthly Cashflow Projection", styles['Heading3'])
                    story.append(cashflow_heading)
                    
                    # Create table data
                    table_data = [['Month', 'Date', 'Income', 'Expenses', 'Net', 'Cumulative']]
                    
                    for month_data in cashflow_data['monthly'][:6]:  # Show first 6 months
                        table_data.append([
                            str(month_data.get('month', '')),
                            month_data.get('date', ''),
                            f"₪{month_data.get('income', 0):,.0f}",
                            f"₪{month_data.get('expenses', 0):,.0f}",
                            f"₪{month_data.get('net', 0):,.0f}",
                            f"₪{month_data.get('cumulative_net', 0):,.0f}"
                        ])
                    
                    cashflow_table = Table(table_data, colWidths=[0.8*inch, 1.2*inch, 1*inch, 1*inch, 1*inch, 1.2*inch])
                    cashflow_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    
                    story.append(cashflow_table)
                    story.append(Spacer(1, 12))
                    
                    # Yearly totals
                    yearly_totals = cashflow_data.get('yearly_totals', {})
                    if yearly_totals:
                        yearly_heading = Paragraph("Yearly Totals", styles['Heading3'])
                        story.append(yearly_heading)
                        
                        yearly_data = [['Year', 'Total Income', 'Total Expenses', 'Net Total']]
                        
                        for year, totals in yearly_totals.items():
                            yearly_data.append([
                                year,
                                f"₪{totals.get('income', 0):,.0f}",
                                f"₪{totals.get('expenses', 0):,.0f}",
                                f"₪{totals.get('net', 0):,.0f}"
                            ])
                        
                        yearly_table = Table(yearly_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 1.5*inch])
                        yearly_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('FONTSIZE', (0, 1), (-1, -1), 9),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                        
                        story.append(yearly_table)
                        story.append(Spacer(1, 20))
            
            # Add page break between scenarios (except for last one)
            if i < len(scenarios):
                story.append(PageBreak())
        
        # Footer
        story.append(Spacer(1, 30))
        footer_text = "This report was generated by the Retirement Planning System. "
        footer_text += "All calculations are estimates and should be reviewed by a financial advisor."
        footer = Paragraph(footer_text, styles['Normal'])
        story.append(footer)
        
        # Build PDF
        doc.build(story)
        
        # Verify file was created and get size
        if os.path.exists(path):
            file_size = os.path.getsize(path)
            
            # Verify it's a valid PDF (starts with %PDF)
            with open(path, 'rb') as f:
                header = f.read(4)
                is_valid_pdf = header == b'%PDF'
            
            return {
                "success": True,
                "file_path": path,
                "file_size": file_size,
                "is_valid_pdf": is_valid_pdf,
                "client_id": client_id,
                "scenarios_count": len(scenarios),
                "generated_at": datetime.now().isoformat(),
                "message": f"PDF report generated successfully with {len(scenarios)} scenarios"
            }
        else:
            return {
                "success": False,
                "error": "PDF file was not created",
                "file_path": path
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "file_path": path,
            "client_id": client_id
        }


def create_sample_pdf(output_path: str = "artifacts/test_report.pdf") -> Dict[str, Any]:
    """
    Create a sample PDF report for testing
    
    Args:
        output_path: Path for the output PDF file
        
    Returns:
        Dict with creation results
    """
    # Sample scenario data
    sample_scenarios = [
        {
            "scenario_name": "Basic Retirement Plan",
            "apply_tax_planning": True,
            "apply_capitalization": False,
            "apply_exemption_shield": True,
            "cashflow_projection": json.dumps({
                "monthly": [
                    {"month": 1, "date": "2025-01-01", "income": 15000, "expenses": 12000, "net": 3000, "cumulative_net": 3000},
                    {"month": 2, "date": "2025-02-01", "income": 15200, "expenses": 12100, "net": 3100, "cumulative_net": 6100},
                    {"month": 3, "date": "2025-03-01", "income": 15400, "expenses": 12200, "net": 3200, "cumulative_net": 9300},
                    {"month": 4, "date": "2025-04-01", "income": 15600, "expenses": 12300, "net": 3300, "cumulative_net": 12600},
                    {"month": 5, "date": "2025-05-01", "income": 15800, "expenses": 12400, "net": 3400, "cumulative_net": 16000},
                    {"month": 6, "date": "2025-06-01", "income": 16000, "expenses": 12500, "net": 3500, "cumulative_net": 19500}
                ],
                "yearly_totals": {
                    "2025": {"income": 186000, "expenses": 148800, "net": 37200}
                }
            })
        }
    ]
    
    return export_pdf(1, sample_scenarios, output_path)
