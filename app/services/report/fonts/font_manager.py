"""
Font management for PDF reports with Hebrew support.
"""

import os
import logging
from typing import List, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..config import (
    DEFAULT_HEBREW_FONT,
    FONT_ALIAS,
    FONT_PATH_CANDIDATES,
    MATPLOTLIB_FONT_FAMILIES,
    MATPLOTLIB_SANS_SERIF
)

_logger = logging.getLogger(__name__)


class FontManager:
    """Manages font registration and configuration for PDF and chart generation."""
    
    _fonts_ready = False
    _default_font = DEFAULT_HEBREW_FONT
    
    @classmethod
    def register_font_once(cls, alias: str, path: str) -> str:
        """
        Register a TrueType font with ReportLab if not already registered.
        
        Args:
            alias: Font alias name
            path: Path to TTF font file
            
        Returns:
            Font alias if successful, "Helvetica" as fallback
        """
        try:
            if alias in pdfmetrics.getRegisteredFontNames():
                return alias
            pdfmetrics.registerFont(TTFont(alias, path))
            _logger.info(f"Successfully registered font: {alias} from {path}")
            return alias
        except Exception as e:
            _logger.warning(f"Font registration failed ({alias} -> {path}): {e}")
            return "Helvetica"
    
    @classmethod
    def get_font_candidates(cls) -> List[str]:
        """
        Get list of font path candidates with matplotlib paths included.
        
        Returns:
            List of font file paths to try
        """
        candidates = list(FONT_PATH_CANDIDATES)
        
        # Add matplotlib-bundled DejaVu Sans paths
        try:
            # Try to find DejaVu Sans through matplotlib
            try:
                dv_path = fm.findfont("DejaVu Sans", fallback_to_default=False)
                if dv_path and os.path.exists(dv_path):
                    candidates.insert(1, dv_path)  # High priority
            except Exception:
                pass
            
            # Fallback to data path lookup
            dv2 = os.path.join(mpl.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
            if os.path.exists(dv2):
                candidates.insert(1, dv2)
        except Exception as e:
            _logger.warning(f"Matplotlib DejaVu font discovery failed: {e}")
        
        return candidates
    
    @classmethod
    def ensure_fonts(cls) -> None:
        """
        Initialize fonts for PDF and chart generation.
        Should be called from rendering functions, not at import time.
        """
        if cls._fonts_ready:
            return
        
        _logger.info("Initializing fonts for report generation...")
        
        # Get all font candidates
        candidates = cls.get_font_candidates()
        
        # Register the first available candidate
        font_registered = False
        for path in candidates:
            if os.path.exists(path):
                cls._default_font = cls.register_font_once(FONT_ALIAS, path)
                if cls._default_font != "Helvetica":
                    font_registered = True
                    _logger.info(f"Using font from: {path}")
                    break
        
        if not font_registered:
            _logger.warning("No Hebrew font found, falling back to Helvetica")
        
        # Configure Matplotlib fonts
        cls.configure_matplotlib_fonts()
        
        cls._fonts_ready = True
    
    @classmethod
    def configure_matplotlib_fonts(cls) -> None:
        """Configure matplotlib to use Unicode-capable fonts."""
        try:
            plt.rcParams["font.family"] = MATPLOTLIB_FONT_FAMILIES
            plt.rcParams["axes.unicode_minus"] = False
            _logger.info("Matplotlib fonts configured successfully")
        except Exception as e:
            _logger.warning(f"Matplotlib font setup warning: {e}")
    
    @classmethod
    def get_default_font(cls) -> str:
        """
        Get the default Hebrew font name.
        
        Returns:
            Font name/alias
        """
        if not cls._fonts_ready:
            cls.ensure_fonts()
        return cls._default_font
    
    @classmethod
    def reset(cls) -> None:
        """Reset font initialization state (useful for testing)."""
        cls._fonts_ready = False
        cls._default_font = DEFAULT_HEBREW_FONT


# Module-level functions for backward compatibility
def ensure_fonts() -> None:
    """Ensure fonts are initialized."""
    FontManager.ensure_fonts()


def get_default_font() -> str:
    """Get default Hebrew font."""
    return FontManager.get_default_font()
