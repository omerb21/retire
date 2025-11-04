"""
Configuration and constants for report generation.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch

# Font configuration
DEFAULT_HEBREW_FONT = "DejaVu Sans"
FONT_ALIAS = "HebrewUI"

# Page configuration
DEFAULT_PAGE_SIZE = A4
DEFAULT_MARGINS = {
    'left': 0.75 * inch,
    'right': 0.75 * inch,
    'top': 0.75 * inch,
    'bottom': 0.75 * inch
}

# Chart configuration
CHART_COLORS = {
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'success': '#2ca02c',
    'danger': '#d62728',
    'warning': '#ff9896',
    'info': '#9467bd'
}

CHART_FIGURE_SIZE = (12, 6)
CHART_DPI = 100

# Table styling
TABLE_HEADER_COLOR = colors.lightgrey
TABLE_GRID_COLOR = colors.black
TABLE_GRID_WIDTH = 1

# Font paths candidates
FONT_PATH_CANDIDATES = [
    # Project-bundled font
    "app/static/fonts/NotoSansHebrew-Regular.ttf",
    # Common Windows fonts
    r"C:\\Windows\\Fonts\\ARIALUNI.TTF",
    r"C:\\Windows\\Fonts\\Arial.ttf",
    r"C:\\Windows\\Fonts\\Tahoma.ttf",
    # Common Linux path
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]

# Matplotlib configuration
MATPLOTLIB_FONT_FAMILIES = ['DejaVu Sans', 'Noto Sans Hebrew', 'Arial Unicode MS']
MATPLOTLIB_SANS_SERIF = ['DejaVu Sans', 'Noto Sans Hebrew', 'Arial Unicode MS']
