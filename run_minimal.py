"""
אפליקציית FastAPI מינימלית לבדיקת הפעלה
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime

app = FastAPI(title="מערכת תכנון פרישה - בדיקה")

# הוספת CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """נקודת קצה ראשית"""
    return {
        "message": "שלום עולם! מערכת תכנון פרישה פועלת",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def health_check():
    """בדיקת בריאות המערכת"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "up",
            "database": "simulated"
        }
    }

@app.get("/api/v1/clients/test")
def test_client():
    """נקודת קצה לבדיקת לקוח"""
    return {
        "id": 1,
        "full_name": "ישראל ישראלי",
        "id_number": "123456789",
        "birth_date": "1970-01-01",
        "gender": "male",
        "is_active": True
    }

if __name__ == "__main__":
    print("מפעיל את מערכת תכנון הפרישה המינימלית...")
    print("השרת יהיה זמין בכתובת: http://127.0.0.1:8000")
    print("תיעוד ה-API זמין בכתובת: http://127.0.0.1:8000/docs")
    print("בדיקת בריאות המערכת: http://127.0.0.1:8000/health")
    uvicorn.run(app, host="127.0.0.1", port=8000)
