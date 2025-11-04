"""
Scenarios comparison chart rendering.
"""

import io
import json
import logging
from typing import List

import matplotlib.pyplot as plt

from ..fonts import ensure_fonts
from ..config import CHART_FIGURE_SIZE, CHART_COLORS

_logger = logging.getLogger(__name__)


class ScenariosChartRenderer:
    """Renders scenario comparison charts."""
    
    @staticmethod
    def render_scenarios_compare_chart(scenarios: List) -> bytes:
        """
        Render scenarios comparison chart as PNG bytes.
        
        Args:
            scenarios: List of scenarios to compare
            
        Returns:
            PNG image as bytes
        """
        ensure_fonts()
        try:
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)
            
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
                        _logger.warning(f"Error parsing scenario {scenario.id} for comparison: {e}")
            
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
            _logger.error(f"Error creating comparison chart: {e}")
            # Return empty chart
            fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)
            ax.text(0.5, 0.5, f'שגיאה ביצירת גרף השוואה: {str(e)}', 
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


# Backward compatibility
def render_scenarios_compare_chart(scenarios: List) -> bytes:
    """Backward compatibility wrapper."""
    return ScenariosChartRenderer.render_scenarios_compare_chart(scenarios)
