"""
Hebrew PDF Report Generation Router
יצירת דוחות PDF בעברית
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.client import Client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import blue, green, black
import io
from datetime import datetime
from typing import List, Dict, Any
import os

router = APIRouter()

def setup_hebrew_font(c):
    """הגדרת פונט עברי"""
    try:
        # ננסה להשתמש בפונט מערכת שתומך בעברית
        font_path = "C:/Windows/Fonts/arial.ttf"  # Arial תומך בעברית
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Hebrew', font_path))
            c.setFont('Hebrew', 12)
            return True
    except:
        pass
    
    try:
        # אם לא עובד, ננסה עם פונט אחר
        font_path = "C:/Windows/Fonts/calibri.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Hebrew', font_path))
            c.setFont('Hebrew', 12)
            return True
    except:
        pass
    
    # אם כל הפונטים נכשלו, נשתמש בפונט בסיסי
    c.setFont('Helvetica', 12)
    return False

def format_hebrew_text(text: str) -> str:
    """עיבוד טקסט עברי לתצוגה נכונה"""
    # פשוט נחזיר את הטקסט כמו שהוא לבדיקה ראשונית
    return text

def draw_hebrew_text(c, x, y, text: str, font_size: int = 12):
    """ציור טקסט עברי עם עיבוד נכון"""
    c.setFont('Hebrew', font_size)
    formatted_text = format_hebrew_text(text)
    c.drawString(x, y, formatted_text)

@router.get("/clients/{client_id}/reports/pdf-hebrew")
async def generate_hebrew_pdf_report(
    client_id: int,
    db: Session = Depends(get_db)
):
    """יצירת דוח PDF בעברית"""
    try:
        # שליפת נתוני הלקוח
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # יצירת PDF בזיכרון
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # הגדרת פונט עברי
        hebrew_font_available = setup_hebrew_font(c)
        
        # כותרת הדוח - נתחיל עם אנגלית לבדיקה
        c.setFont('Helvetica', 20)
        c.setFillColor(blue)
        title_en = "Comprehensive Retirement Planning Report (Hebrew Version)"
        text_width = c.stringWidth(title_en, 'Helvetica', 20)
        c.drawString((width - text_width) / 2, height - 50, title_en)
        
        # תאריך הדוח
        c.setFont('Helvetica', 12)
        c.setFillColor(black)
        current_date = datetime.now().strftime("%d/%m/%Y")
        c.drawString(50, height - 100, f"Report Date: {current_date}")
        
        # פרטי לקוח
        y_pos = height - 130
        if client:
            c.drawString(50, y_pos, f"Client: {client.first_name or ''} {client.last_name or ''}")
            y_pos -= 20
            
            if client.birth_date:
                c.drawString(50, y_pos, f"Birth Date: {client.birth_date}")
                y_pos -= 20
            
            if client.id_number:
                c.drawString(50, y_pos, f"ID: {client.id_number}")
                y_pos -= 20
        
        # הודעה על סטטוס הפונט
        y_pos -= 30
        c.setFont('Helvetica', 10)
        c.setFillColor(green)
        if hebrew_font_available:
            c.drawString(50, y_pos, "Hebrew font available - ready for Hebrew content")
        else:
            c.drawString(50, y_pos, "Hebrew font not available - using fallback")
        
        # סיום הדוח
        c.save()
        
        # החזרת הPDF
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # יצירת שם קובץ באנגלית
        filename = f"retirement_report_{client.first_name or 'client'}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
