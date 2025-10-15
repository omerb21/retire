# 🚀 הפעלת המערכת - הוראות קבועות

## ⚠️ חשוב מאוד - קרא לפני כל הפעלה!

### פורטים קבועים:
- **Backend (Python/FastAPI)**: פורט **8005**
- **Frontend (React/Vite)**: פורט **3000**

---

## 🔴 הפעלה נכונה - תמיד בסדר הזה!

### שלב 1: הפעל Backend
```bash
# דרך 1: באמצעות הסקריפט (מומלץ)
start_backend.bat

# דרך 2: ידנית
uvicorn app.main:app --reload --port 8005 --host 0.0.0.0
```

**המתן עד שתראה:** `Application startup complete.`

---

### שלב 2: הפעל Frontend
```bash
# דרך 1: באמצעות הסקריפט (מומלץ)
cd frontend
start_frontend.bat

# דרך 2: ידנית
cd frontend
npm run dev
```

**המתן עד שתראה:** `VITE v5.x.x ready in XXXms`

---

## 🛑 אם יש בעיות

### בעיה: "Address already in use" או שרתים כפולים

**פתרון:**

1. **עצור את כל השרתים:**
   - לחץ Ctrl+C בכל חלון טרמינל
   - סגור את כל חלונות הטרמינל

2. **וודא שאין שרתים רצים:**
   ```bash
   # בדוק פורט 8005
   netstat -ano | findstr :8005
   
   # בדוק פורט 3000
   netstat -ano | findstr :3000
   ```

3. **אם עדיין יש שרתים - עצור ידנית:**
   - פתח Task Manager (Ctrl+Shift+Esc)
   - חפש תהליכי "python.exe" ו-"node.exe"
   - סגור אותם
   
4. **הפעל מחדש** באמצעות הסקריפטים

---

## ✅ איך לדעת שהכל עובד?

1. **Backend:** פתח http://localhost:8005/health
   - אמור להחזיר: `{"status": "ok"}`

2. **Frontend:** פתח http://localhost:3000
   - אמור לראות את המערכת

3. **בדוק שיש רק שרת אחד:**
   ```bash
   netstat -ano | findstr :8005
   netstat -ano | findstr :3000
   ```
   - צריך להיות רק **שורה אחת LISTENING** לכל פורט!

---

## 📝 כללים חשובים

1. **לעולם אל תפעיל יותר משרת אחד** על אותו פורט
2. **תמיד השתמש בסקריפטים** - הם עוצרים שרתים ישנים אוטומטית
3. **אם יש שגיאה - עצור הכל והתחל מחדש**
4. **אל תשנה את הפורטים** ללא תיאום

---

## 🔧 הגדרות Vite (לא לשנות!)

קובץ: `frontend/vite.config.ts`
```typescript
proxy: {
  "/api": {
    target: "http://localhost:8005",  // ✅ פורט 8005 - לא לשנות!
    changeOrigin: true,
  },
}
```

---

## 📞 אם משהו לא עובד

1. עצור את כל השרתים
2. בדוק שאין שרתים רצים (netstat)
3. הפעל מחדש עם הסקריפטים
4. אם עדיין לא עובד - בדוק את הלוגים
