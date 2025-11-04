"""
PDF styling utilities for Hebrew/RTL reports.
"""

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import TableStyle

from ..config import DEFAULT_HEBREW_FONT, TABLE_HEADER_COLOR, TABLE_GRID_COLOR, TABLE_GRID_WIDTH


class PDFStyles:
    """PDF styling utilities."""
    
    @staticmethod
    def get_hebrew_style(font_name: str = None) -> ParagraphStyle:
        """
        Get base Hebrew paragraph style with RTL support.
        
        Args:
            font_name: Font name to use (defaults to config)
            
        Returns:
            ParagraphStyle for Hebrew text
        """
        if font_name is None:
            from ..fonts import get_default_font
            font_name = get_default_font()
        
        return ParagraphStyle(
            'HebrewStyle',
            fontName=font_name,
            fontSize=12,
            alignment=TA_RIGHT,
            leading=16,
            rightIndent=0,
            leftIndent=0,
            wordWrap='RTL'
        )
    
    @staticmethod
    def get_title_style(font_name: str = None) -> ParagraphStyle:
        """
        Get title paragraph style.
        
        Args:
            font_name: Font name to use
            
        Returns:
            ParagraphStyle for titles
        """
        hebrew_style = PDFStyles.get_hebrew_style(font_name)
        return ParagraphStyle(
            'TitleStyle',
            parent=hebrew_style,
            fontSize=18,
            fontName=font_name or hebrew_style.fontName,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#1f77b4'),
            bold=True
        )
    
    @staticmethod
    def get_section_style(font_name: str = None) -> ParagraphStyle:
        """
        Get section header style.
        
        Args:
            font_name: Font name to use
            
        Returns:
            ParagraphStyle for section headers
        """
        hebrew_style = PDFStyles.get_hebrew_style(font_name)
        return ParagraphStyle(
            'SectionStyle',
            parent=hebrew_style,
            fontSize=14,
            fontName=font_name or hebrew_style.fontName,
            alignment=TA_RIGHT,
            spaceAfter=12,
            textColor=colors.HexColor('#2ca02c'),
            bold=True
        )
    
    @staticmethod
    def get_body_style(font_name: str = None) -> ParagraphStyle:
        """
        Get body text style.
        
        Args:
            font_name: Font name to use
            
        Returns:
            ParagraphStyle for body text
        """
        hebrew_style = PDFStyles.get_hebrew_style(font_name)
        return ParagraphStyle(
            'BodyStyle',
            parent=hebrew_style,
            fontSize=10,
            fontName=font_name or hebrew_style.fontName,
            alignment=TA_RIGHT,
            spaceAfter=6
        )
    
    @staticmethod
    def get_footer_style(font_name: str = None) -> ParagraphStyle:
        """
        Get footer text style.
        
        Args:
            font_name: Font name to use
            
        Returns:
            ParagraphStyle for footer
        """
        hebrew_style = PDFStyles.get_hebrew_style(font_name)
        return ParagraphStyle(
            'FooterStyle',
            parent=hebrew_style,
            fontSize=8,
            fontName=font_name or hebrew_style.fontName,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
    
    @staticmethod
    def get_table_style(font_name: str = None) -> TableStyle:
        """
        Get standard table style with Hebrew support.
        
        Args:
            font_name: Font name to use
            
        Returns:
            TableStyle for tables
        """
        if font_name is None:
            from ..fonts import get_default_font
            font_name = get_default_font()
        
        return TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), TABLE_GRID_WIDTH, TABLE_GRID_COLOR),
            ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
        ])
    
    @staticmethod
    def get_all_styles(font_name: str = None):
        """
        Get dictionary of all common styles.
        
        Args:
            font_name: Font name to use
            
        Returns:
            Dictionary of style name to ParagraphStyle
        """
        return {
            'hebrew': PDFStyles.get_hebrew_style(font_name),
            'title': PDFStyles.get_title_style(font_name),
            'section': PDFStyles.get_section_style(font_name),
            'body': PDFStyles.get_body_style(font_name),
            'footer': PDFStyles.get_footer_style(font_name)
        }
