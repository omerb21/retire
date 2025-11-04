"""
Cashflow chart rendering for PDF reports.
"""

import io
import json
import logging
from typing import Dict, Any, List

import matplotlib.pyplot as plt

from ..fonts import ensure_fonts
from ..config import CHART_FIGURE_SIZE

_logger = logging.getLogger(__name__)


class CashflowChartRenderer:
    """Renders cashflow charts for reports."""
    
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
            
            fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)
            
            # Extract data from cashflow projection
            if isinstance(cashflow_projection, dict) and 'annual_cashflow' in cashflow_projection:
                annual_data = cashflow_projection['annual_cashflow']
                years = list(range(len(annual_data)))
                values = [entry.get('net_cashflow', 0) for entry in annual_data]
                
                # Plot the cashflow
                ax.plot(years, values, linewidth=2, color='#2E86AB', marker='o', markersize=4)
                ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
                ax.fill_between(years, 0, values, where=[v >= 0 for v in values], 
                               color='green', alpha=0.2, label='תזרים חיובי')
                ax.fill_between(years, 0, values, where=[v < 0 for v in values], 
                               color='red', alpha=0.2, label='תזרים שלילי')
                
                ax.set_xlabel('שנים', fontsize=12)
                ax.set_ylabel('תזרים נטו (₪)', fontsize=12)
                ax.set_title('תזרים מזומנים נטו שנתי', fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3)
                ax.legend()
                
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
            _logger.error(f"Error creating cashflow chart: {e}")
            return CashflowChartRenderer._create_error_chart(str(e))
    
    @staticmethod
    def create_net_cashflow_chart(chart_data: Dict[str, List]) -> bytes:
        """
        Create net cashflow chart using matplotlib.
        
        Args:
            chart_data: Dictionary with 'dates' and 'values' keys
            
        Returns:
            PNG image as bytes
        """
        ensure_fonts()
        try:
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)
            
            dates = chart_data.get('dates', [])
            values = chart_data.get('values', [])
            
            if dates and values:
                ax.plot(dates, values, linewidth=2, color='#1f77b4', marker='o', markersize=3)
                ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
                ax.fill_between(range(len(values)), 0, values, 
                               where=[v >= 0 for v in values], 
                               color='green', alpha=0.2)
                ax.fill_between(range(len(values)), 0, values, 
                               where=[v < 0 for v in values], 
                               color='red', alpha=0.2)
                
                ax.set_xlabel('תאריך', fontsize=12)
                ax.set_ylabel('תזרים נטו (₪)', fontsize=12)
                ax.set_title('תזרים מזומנים נטו חודשי', fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3)
                
                # Format y-axis
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
                
                # Rotate x-axis labels if there are many dates
                if len(dates) > 12:
                    plt.xticks(rotation=45, ha='right')
            else:
                ax.text(0.5, 0.5, 'אין נתונים זמינים', 
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
            _logger.error(f"Error creating net cashflow chart: {e}")
            return CashflowChartRenderer._create_error_chart(str(e))
    
    @staticmethod
    def _create_error_chart(error_message: str) -> bytes:
        """
        Create an error chart with message.
        
        Args:
            error_message: Error message to display
            
        Returns:
            PNG image as bytes
        """
        fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)
        ax.text(0.5, 0.5, f'שגיאה ביצירת גרף: {error_message}', 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=12, color='red')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close(fig)
        
        return img_buffer.getvalue()


# Backward compatibility functions
def render_cashflow_chart(cashflow_projection: Dict[str, Any]) -> bytes:
    """Backward compatibility wrapper."""
    return CashflowChartRenderer.render_cashflow_chart(cashflow_projection)


def create_net_cashflow_chart(chart_data: Dict[str, List]) -> bytes:
    """Backward compatibility wrapper."""
    return CashflowChartRenderer.create_net_cashflow_chart(chart_data)
