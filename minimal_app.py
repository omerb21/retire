"""
אפליקציה מינימלית לבדיקת הפעלה
"""
from fastapi import FastAPI

app = FastAPI(title="מערכת תכנון פרישה - בדיקה")

@app.get("/")
def read_root():
    return {"message": "שלום עולם! המערכת פועלת"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
