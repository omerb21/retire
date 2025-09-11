"""
סקריפט להתקנה והפעלה מקומית של מערכת תכנון פרישה
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, cwd=None):
    """הרצת פקודה והצגת הפלט"""
    print(f"\n>>> הרצת פקודה: {cmd}")
    process = subprocess.Popen(
        cmd, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=cwd
    )
    
    for line in process.stdout:
        print(line.strip())
    
    process.wait()
    return process.returncode

def check_prerequisites():
    """בדיקת דרישות מקדימות"""
    print("\n🔍 בודק דרישות מקדימות...")
    
    # בדיקת Python
    print("בודק התקנת Python...")
    if run_command("python --version") != 0:
        print("❌ Python לא מותקן או לא נמצא בנתיב. אנא התקן Python 3.10 או גרסה חדשה יותר.")
        return False
    
    # בדיקת pip
    print("בודק התקנת pip...")
    if run_command("pip --version") != 0:
        print("❌ pip לא מותקן. אנא התקן pip.")
        return False
    
    # בדיקת Docker (אופציונלי)
    print("בודק התקנת Docker (אופציונלי)...")
    docker_installed = run_command("docker --version") == 0
    if not docker_installed:
        print("⚠️ Docker לא מותקן. המערכת תופעל במצב מקומי ללא קונטיינרים.")
    
    print("✅ כל הדרישות המקדימות הושלמו!")
    return True

def setup_virtual_env():
    """הקמת סביבה וירטואלית והתקנת תלויות"""
    print("\n🔧 מקים סביבה וירטואלית...")
    
    # יצירת סביבה וירטואלית
    if not os.path.exists("venv"):
        if run_command("python -m venv venv") != 0:
            print("❌ נכשל ביצירת סביבה וירטואלית.")
            return False
    
    # הפעלת הסביבה והתקנת תלויות
    activate_cmd = "venv\\Scripts\\activate" if sys.platform == "win32" else "source venv/bin/activate"
    install_cmd = f"{activate_cmd} && pip install -r requirements.txt"
    
    if run_command(install_cmd) != 0:
        print("❌ נכשל בהתקנת תלויות.")
        return False
    
    print("✅ סביבה וירטואלית הוקמה בהצלחה!")
    return True

def setup_database():
    """הקמת מסד נתונים"""
    print("\n🗄️ מקים מסד נתונים...")
    
    # הרצת מיגרציות
    activate_cmd = "venv\\Scripts\\activate" if sys.platform == "win32" else "source venv/bin/activate"
    db_cmd = f"{activate_cmd} && python create_db.py"
    
    if run_command(db_cmd) != 0:
        print("❌ נכשל בהקמת מסד נתונים.")
        return False
    
    print("✅ מסד נתונים הוקם בהצלחה!")
    return True

def run_application():
    """הפעלת האפליקציה"""
    print("\n🚀 מפעיל את האפליקציה...")
    
    # הפעלת האפליקציה
    activate_cmd = "venv\\Scripts\\activate" if sys.platform == "win32" else "source venv/bin/activate"
    run_cmd = f"{activate_cmd} && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    
    print(f"\n✅ האפליקציה פועלת!")
    print(f"🌐 ניתן לגשת לאפליקציה בכתובת: http://localhost:8000")
    print(f"📚 תיעוד ה-API זמין בכתובת: http://localhost:8000/docs")
    print(f"🔍 בדיקת בריאות המערכת: http://localhost:8000/health")
    print("\nלחץ Ctrl+C לעצירת האפליקציה.")
    
    # הרצת האפליקציה
    run_command(run_cmd)
    
    return True

def main():
    """פונקציה ראשית"""
    print("\n🌟 ברוכים הבאים למערכת תכנון פרישה! 🌟")
    
    # בדיקת דרישות מקדימות
    if not check_prerequisites():
        return False
    
    # הקמת סביבה וירטואלית
    if not setup_virtual_env():
        return False
    
    # הקמת מסד נתונים
    if not setup_database():
        return False
    
    # הפעלת האפליקציה
    if not run_application():
        return False
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 תודה שהשתמשת במערכת תכנון פרישה!")
    except Exception as e:
        print(f"\n❌ אירעה שגיאה: {str(e)}")
        sys.exit(1)
