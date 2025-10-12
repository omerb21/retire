"""
סקריפט פשוט להפעלת האפליקציה
"""
import uvicorn

if __name__ == "__main__":
    print("מפעיל את מערכת תכנון הפרישה...")
    print("ניתן לגשת לאפליקציה בכתובת: http://localhost:8005")
    print("תיעוד ה-API זמין בכתובת: http://localhost:8005/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)
