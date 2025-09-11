"""
סקריפט לאיתור בעיות בהפעלת האפליקציה
"""
import sys
import os
import importlib
import traceback

def check_imports():
    """בדיקת ייבוא מודולים"""
    print("בודק ייבוא מודולים...")
    
    modules_to_check = [
        "app.main",
        "app.database",
        "app.models",
        "app.schemas",
        "app.routers.client",
        "app.routers.clients",
        "app.routers.scenarios",
        "app.routers.reports"
    ]
    
    for module_name in modules_to_check:
        try:
            print(f"מנסה לייבא: {module_name}")
            module = importlib.import_module(module_name)
            print(f"✓ ייבוא מוצלח: {module_name}")
        except Exception as e:
            print(f"✗ שגיאה בייבוא {module_name}: {str(e)}")
            print("פירוט השגיאה:")
            traceback.print_exc()
            return False
    
    return True

def check_database():
    """בדיקת חיבור למסד נתונים"""
    print("\nבודק חיבור למסד נתונים...")
    
    try:
        from app.database import engine, Base
        from sqlalchemy import text
        
        # בדיקת חיבור
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✓ חיבור למסד נתונים תקין: {result.fetchone()}")
        
        # בדיקת טבלאות
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✓ טבלאות קיימות במסד הנתונים: {', '.join(tables)}")
        
        return True
    except Exception as e:
        print(f"✗ שגיאה בחיבור למסד נתונים: {str(e)}")
        print("פירוט השגיאה:")
        traceback.print_exc()
        return False

def check_app_structure():
    """בדיקת מבנה האפליקציה"""
    print("\nבודק מבנה האפליקציה...")
    
    try:
        from app.main import app
        
        # בדיקת נתיבים
        routes = [
            {"path": route.path, "name": route.name, "methods": route.methods}
            for route in app.routes
        ]
        
        print(f"✓ מספר נתיבים שנמצאו: {len(routes)}")
        for i, route in enumerate(routes[:5]):  # הצג רק 5 נתיבים לדוגמה
            print(f"  - {route['path']} ({', '.join(route['methods'])})")
        
        if len(routes) > 5:
            print(f"  ... ועוד {len(routes) - 5} נתיבים")
        
        return True
    except Exception as e:
        print(f"✗ שגיאה בבדיקת מבנה האפליקציה: {str(e)}")
        print("פירוט השגיאה:")
        traceback.print_exc()
        return False

def run_minimal_app():
    """הפעלת אפליקציה מינימלית לבדיקה"""
    print("\nמנסה להפעיל אפליקציה מינימלית...")
    
    try:
        import uvicorn
        from fastapi import FastAPI
        
        # יצירת אפליקציה מינימלית
        mini_app = FastAPI(title="Test App")
        
        @mini_app.get("/")
        def read_root():
            return {"message": "Hello World"}
        
        # שמירת האפליקציה לקובץ זמני
        temp_file = "temp_app.py"
        with open(temp_file, "w") as f:
            f.write("""
from fastapi import FastAPI

app = FastAPI(title="Test App")

@app.get("/")
def read_root():
    return {"message": "Hello World"}
""")
        
        print("✓ נוצרה אפליקציה מינימלית")
        print("הפעל את האפליקציה המינימלית עם הפקודה:")
        print("uvicorn temp_app:app --host 0.0.0.0 --port 8001")
        
        return True
    except Exception as e:
        print(f"✗ שגיאה ביצירת אפליקציה מינימלית: {str(e)}")
        print("פירוט השגיאה:")
        traceback.print_exc()
        return False

def check_environment():
    """בדיקת סביבת העבודה"""
    print("\nבודק סביבת עבודה...")
    
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    
    # בדיקת תלויות
    try:
        import fastapi
        print(f"FastAPI version: {fastapi.__version__}")
    except ImportError:
        print("✗ FastAPI לא מותקן")
    
    try:
        import uvicorn
        print(f"Uvicorn version: {uvicorn.__version__}")
    except ImportError:
        print("✗ Uvicorn לא מותקן")
    
    try:
        import sqlalchemy
        print(f"SQLAlchemy version: {sqlalchemy.__version__}")
    except ImportError:
        print("✗ SQLAlchemy לא מותקן")
    
    return True

def main():
    """פונקציה ראשית"""
    print("🔍 מתחיל אבחון מערכת תכנון פרישה...\n")
    
    # בדיקת סביבה
    check_environment()
    
    # בדיקת ייבוא מודולים
    if not check_imports():
        print("\n❌ נכשל בבדיקת ייבוא מודולים")
        return False
    
    # בדיקת מסד נתונים
    if not check_database():
        print("\n❌ נכשל בבדיקת מסד נתונים")
    
    # בדיקת מבנה האפליקציה
    if not check_app_structure():
        print("\n❌ נכשל בבדיקת מבנה האפליקציה")
    
    # הפעלת אפליקציה מינימלית
    run_minimal_app()
    
    print("\n✅ האבחון הושלם")
    print("עקוב אחר ההוראות לעיל כדי לפתור את הבעיות שנמצאו")
    
    return True

if __name__ == "__main__":
    main()
