"""
סקריפט לאבחון בעיות בהפעלת השרת
"""
import sys
import os
import importlib
import traceback
import socket
import platform
import psutil
import requests
from datetime import datetime

def check_system_info():
    """בדיקת מידע מערכת"""
    print("=== מידע מערכת ===")
    print(f"מערכת הפעלה: {platform.system()} {platform.release()}")
    print(f"גרסת Python: {sys.version}")
    print(f"ספריית עבודה נוכחית: {os.getcwd()}")
    print(f"PATH: {os.environ.get('PATH', '')[:100]}...")
    
    # בדיקת זיכרון
    mem = psutil.virtual_memory()
    print(f"זיכרון כולל: {mem.total / (1024**3):.2f} GB")
    print(f"זיכרון פנוי: {mem.available / (1024**3):.2f} GB")
    print(f"אחוז שימוש בזיכרון: {mem.percent}%")

def check_port_availability(port):
    """בדיקת זמינות פורט"""
    print(f"\n=== בדיקת זמינות פורט {port} ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"פורט {port} תפוס על ידי תהליך אחר")
            # נסה למצוא איזה תהליך משתמש בפורט
            try:
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    for conn in proc.info.get('connections', []):
                        if conn.laddr.port == port:
                            print(f"תהליך {proc.info['pid']} ({proc.info['name']}) משתמש בפורט {port}")
                            break
            except:
                print("לא ניתן לזהות את התהליך המשתמש בפורט")
        else:
            print(f"פורט {port} פנוי")
        sock.close()
    except Exception as e:
        print(f"שגיאה בבדיקת פורט: {str(e)}")

def check_dependencies():
    """בדיקת תלויות"""
    print("\n=== בדיקת תלויות ===")
    dependencies = [
        "fastapi", "uvicorn", "sqlalchemy", "pydantic", 
        "requests", "reportlab", "matplotlib"
    ]
    
    for dep in dependencies:
        try:
            module = importlib.import_module(dep)
            version = getattr(module, "__version__", "לא ידוע")
            print(f"✓ {dep}: {version}")
        except ImportError:
            print(f"✗ {dep}: לא מותקן")
        except Exception as e:
            print(f"✗ {dep}: שגיאה - {str(e)}")

def check_fastapi_app():
    """בדיקת אפליקציית FastAPI"""
    print("\n=== בדיקת אפליקציית FastAPI ===")
    try:
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/")
        def read_root():
            return {"message": "Hello World"}
        
        print("✓ יצירת אפליקציית FastAPI בסיסית הצליחה")
    except Exception as e:
        print(f"✗ שגיאה ביצירת אפליקציית FastAPI: {str(e)}")
        traceback.print_exc()

def check_uvicorn_import():
    """בדיקת ייבוא uvicorn"""
    print("\n=== בדיקת ייבוא uvicorn ===")
    try:
        import uvicorn
        print(f"✓ ייבוא uvicorn הצליח (גרסה {uvicorn.__version__})")
    except Exception as e:
        print(f"✗ שגיאה בייבוא uvicorn: {str(e)}")
        traceback.print_exc()

def check_project_structure():
    """בדיקת מבנה הפרויקט"""
    print("\n=== בדיקת מבנה הפרויקט ===")
    key_files = [
        "app/main.py",
        "app/__init__.py",
        "app/database.py",
        "app/schemas/__init__.py",
        "app/models/__init__.py",
        "app/routers/__init__.py",
        "requirements.txt"
    ]
    
    for file_path in key_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} קיים")
        else:
            print(f"✗ {file_path} חסר")

def check_api_server():
    """בדיקת שרת API"""
    print("\n=== בדיקת שרת API ===")
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=2)
        if response.status_code == 200:
            print(f"✓ שרת API פועל (קוד תגובה: {response.status_code})")
            print(f"תוכן תגובה: {response.json()}")
        else:
            print(f"✗ שרת API מגיב אך עם קוד שגיאה: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ שרת API אינו פועל או לא מגיב")
    except Exception as e:
        print(f"✗ שגיאה בבדיקת שרת API: {str(e)}")

def create_minimal_app():
    """יצירת אפליקציה מינימלית"""
    print("\n=== יצירת אפליקציה מינימלית ===")
    try:
        minimal_app_path = "minimal_test_app.py"
        with open(minimal_app_path, "w") as f:
            f.write("""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
""")
        print(f"✓ נוצרה אפליקציה מינימלית בקובץ {minimal_app_path}")
        print("הפעל את האפליקציה עם הפקודה:")
        print(f"python {minimal_app_path}")
    except Exception as e:
        print(f"✗ שגיאה ביצירת אפליקציה מינימלית: {str(e)}")

def main():
    """פונקציה ראשית"""
    print(f"=== אבחון מערכת תכנון פרישה - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    check_system_info()
    check_port_availability(8000)
    check_dependencies()
    check_fastapi_app()
    check_uvicorn_import()
    check_project_structure()
    check_api_server()
    create_minimal_app()
    
    print("\n=== סיכום אבחון ===")
    print("1. בדוק אם פורט 8000 פנוי")
    print("2. וודא שכל התלויות מותקנות")
    print("3. נסה להפעיל את האפליקציה המינימלית שנוצרה")
    print("4. בדוק את הלוגים לאיתור שגיאות ספציפיות")

if __name__ == "__main__":
    main()
