"""
PDF Graph generation utilities using matplotlib
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
import io
import base64
from typing import List, Dict, Any
import numpy as np
from datetime import datetime, date

# Set matplotlib to use non-interactive backend
plt.switch_backend('Agg')

def render_cashflow_chart(cashflow: List[Dict[str, Any]], title: str = "Cashflow Projection") -> io.BytesIO:
    """
    Render cashflow chart as PNG image buffer
    """
    if not cashflow:
        return create_empty_chart("No cashflow data available")
    
    # Extract data
    years = [entry['year'] for entry in cashflow]
    gross_income = [entry['gross_income'] for entry in cashflow]
    net_income = [entry['net_income'] for entry in cashflow]
    tax = [entry['tax'] for entry in cashflow]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot lines
    ax.plot(years, gross_income, label='Gross Income', linewidth=2, color='#2E86AB')
    ax.plot(years, net_income, label='Net Income', linewidth=2, color='#A23B72')
    ax.plot(years, tax, label='Tax', linewidth=2, color='#F18F01')
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Amount (NIS)', fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Format y-axis with thousands separator
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    # Rotate x-axis labels if many years
    if len(years) > 10:
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def render_income_breakdown_chart(cashflow: List[Dict[str, Any]], title: str = "Income Breakdown") -> io.BytesIO:
    """
    Render stacked bar chart showing income breakdown by source
    """
    if not cashflow:
        return create_empty_chart("No income data available")
    
    # Extract data
    years = [entry['year'] for entry in cashflow]
    pension_income = [entry.get('pension_income', 0) for entry in cashflow]
    grant_income = [entry.get('grant_income', 0) for entry in cashflow]
    other_income = [entry.get('other_income', 0) for entry in cashflow]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create stacked bar chart
    width = 0.8
    ax.bar(years, pension_income, width, label='Pension Income', color='#2E86AB')
    ax.bar(years, grant_income, width, bottom=pension_income, label='Grant Income', color='#A23B72')
    
    # Add other income on top
    bottom_values = [p + g for p, g in zip(pension_income, grant_income)]
    ax.bar(years, other_income, width, bottom=bottom_values, label='Other Income', color='#F18F01')
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Amount (NIS)', fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    # Rotate x-axis labels if many years
    if len(years) > 10:
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def render_cumulative_chart(cashflow: List[Dict[str, Any]], title: str = "Cumulative Income") -> io.BytesIO:
    """
    Render cumulative income chart
    """
    if not cashflow:
        return create_empty_chart("No cumulative data available")
    
    # Calculate cumulative values
    years = [entry['year'] for entry in cashflow]
    net_income = [entry['net_income'] for entry in cashflow]
    cumulative_net = np.cumsum(net_income)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot area chart
    ax.fill_between(years, cumulative_net, alpha=0.6, color='#2E86AB', label='Cumulative Net Income')
    ax.plot(years, cumulative_net, linewidth=2, color='#1B5E7A')
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Cumulative Amount (NIS)', fontsize=12)
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    # Rotate x-axis labels if many years
    if len(years) > 10:
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def render_tax_analysis_chart(cashflow: List[Dict[str, Any]], title: str = "Tax Analysis") -> io.BytesIO:
    """
    Render tax rate and burden analysis chart
    """
    if not cashflow:
        return create_empty_chart("No tax data available")
    
    # Calculate tax rates
    years = [entry['year'] for entry in cashflow]
    gross_income = [entry['gross_income'] for entry in cashflow]
    tax = [entry['tax'] for entry in cashflow]
    
    # Calculate effective tax rates (avoid division by zero)
    tax_rates = [t/g * 100 if g > 0 else 0 for t, g in zip(tax, gross_income)]
    
    # Create figure with dual y-axis
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    # Tax amounts (left y-axis)
    color1 = '#F18F01'
    ax1.set_xlabel('Year', fontsize=12)
    ax1.set_ylabel('Tax Amount (NIS)', color=color1, fontsize=12)
    ax1.bar(years, tax, alpha=0.7, color=color1, label='Tax Amount')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    # Tax rates (right y-axis)
    ax2 = ax1.twinx()
    color2 = '#A23B72'
    ax2.set_ylabel('Effective Tax Rate (%)', color=color2, fontsize=12)
    ax2.plot(years, tax_rates, color=color2, marker='o', linewidth=2, label='Tax Rate %')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(0, max(tax_rates) * 1.1 if tax_rates else 50)
    
    # Title and grid
    ax1.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax1.grid(True, alpha=0.3)
    
    # Rotate x-axis labels if many years
    if len(years) > 10:
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def create_empty_chart(message: str) -> io.BytesIO:
    """
    Create an empty chart with a message
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14, 
            transform=ax.transAxes, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def create_summary_pie_chart(summary_data: Dict[str, float], title: str = "Income Summary") -> io.BytesIO:
    """
    Create pie chart for income summary
    """
    if not summary_data or all(v <= 0 for v in summary_data.values()):
        return create_empty_chart("No summary data available")
    
    # Filter out zero values
    filtered_data = {k: v for k, v in summary_data.items() if v > 0}
    
    if not filtered_data:
        return create_empty_chart("No positive values to display")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Data for pie chart
    labels = list(filtered_data.keys())
    sizes = list(filtered_data.values())
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#7209B7'][:len(labels)]
    
    # Create pie chart
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                      startangle=90, textprops={'fontsize': 10})
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    
    # Make percentage text bold
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf
