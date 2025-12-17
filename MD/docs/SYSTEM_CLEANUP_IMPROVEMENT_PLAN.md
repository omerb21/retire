# תכנית מקיפה לניקוי ושיפור מערכת "retire"

## מטרות
- להפוך את הפרויקט לבסיס Production יציב: קוד נקי, מודולרי, עקבי, ניתן לתחזוקה והרחבה.
- לצמצם סיכוני רגרסיות: שינויים לא־הרסניים, שמירה על תאימות לאחור, ובדיקות עקביות.
- להקשיח איכות: סטנדרטים אחידים, טיפול שגיאות ושקיפות לוגים, וולידציה בסיסית בכל שינוי.

## עקרונות מחייבים (Guiding Principles)
- ללא מחיקות קוד/קבצים: במקום זאת מבצעים הוצאה לשכבות נכונות, wrappers ותאימות לאחור.
- Entry points (למשל `app/main.py`, `run_app.py`) נשארים דקים: אתחול, wiring, routers, middleware בלבד.
- Routers נשארים דקים: ולידציה, קריאה לשירות, החזרת response. ללא לוגיקה עסקית.
- ארגון לפי אחריות: `routers/`, `services/`, `schemas/`, `models/`, `utils/`. מבנה רדוד.
- אין מודול Authentication/Authorization (לפי דרישת המערכת): אין הגנות/סיסמאות/headers שמגבילים גישה.
- אין יצירת endpoints חדשים לפני בדיקה שקיים/לא קיים.
- ללא `eval/exec` וללא דפוסים מסוכנים.
- שימוש ב־relative paths בקוד.

## תמונת מצב נוכחית (תצפיות מהירות)
- קיימת שכבת routers עשירה ומספר services; יש תיעוד משמעותי תחת `MD/docs/` וכן סיכומי refactor תחת `MD/frontend/`.
- `app/routers/llm_chat.py` הוא קובץ גדול מאוד (≈ 2,300+ שורות) עם לוגיקה מעורבת (parsing, state, tool definitions, orchestration).
- ב־`app/main.py` יש middleware `SystemAccessMiddleware` (מנגנון הגבלת גישה). זה אינו תואם לדרישה “ללא auth”.
- קיימים מנגנוני validation/health שכבר הוכנסו בעבר (System Validator). יש להמשיך בקו הזה באופן עקבי.

---

# Phase 0 — Baseline & Guardrails (לפני כל refactor)
## תוצרים
- קובץ "מפת מערכת" קצר (ניתן להוסיף בנספח למסמך זה): נקודות כניסה, routers עיקריים, services עיקריים, תלות DB.
- סט בדיקות איכות מינימלי שמורץ לפני/אחרי כל מקבץ שינוי.

## פעולות
- Backend:
  - בדיקת תחביר ללא כתיבת קבצים: AST parse לכל `*.py` תחת `app/`, `db/`, `utils/`, `tests/`.
  - הרצת `pytest` אם יש סביבת בדיקות פעילה.
- Frontend:
  - `npm run build` (או מקביל) כדי לוודא TypeScript + bundling.
- CI:
  - בדיקה שה־workflow הקיים ב־`.github/workflows/ci.yml` תואם לפקודות שנבחרו.

## קריטריוני קבלה
- אין שגיאות תחביר Python.
- build פרונט עובר.
- כל שינוי בהמשך ייכנס רק אחרי מעבר בדיקות אלה.

---

# Phase 1 — Backend Cleanup (ארכיטקטורה, שכבות, עקביות)
## 1.1 יישור קו על מבנה שכבות
מטרה: להפוך את Backend ל־“Thin Router + Services + Schemas + Models + Utils”.

פעולות:
- סקירה של `app/routers/*`:
  - זיהוי routers עם לוגיקה עסקית.
  - הוצאה של לוגיקה לשירותים תחת `app/services/`.
  - יצירת פונקציות שירות קטנות, בדידות, עם input/output ברור.
- סקירה של `app/services/*`:
  - איחוד כפילויות: להוציא חישובים משותפים ל־`utils/` או שירות משותף.
  - להקטין קבצים גדולים: פיצול לפי אחריות לתתי־מודולים.
- יישור קו של `schemas`:
  - אין שימוש ב־`dict` חופשי ב־request/response כשאפשר להגדיר schema.
  - להחזיר תמיד response עקבי ומסודר (כולל שדות שנדרשים בפרונט).

קריטריוני קבלה:
- routers דקים באופן עקבי.
- לוגיקה עסקית קיימת ב־services בלבד.
- אין שברי תאימות API.

## 1.2 הסרת הגבלות גישה (ללא Auth)
מטרה: התאמה לכלל מערכת: “אין צורך/רצון באימות משתמשים”.

פעולות:
- איתור נקודות הגנה (למשל `SystemAccessMiddleware` ב־`app/main.py`).
- הפיכה למנגנון no-op או הסרה מבוקרת:
  - אם יש תלות תפעולית (לדוגמה בסביבת Render) — לא לשבור. במקום זאת:
    - לשמור קונפיג ברירת מחדל פתוח,
    - ולהשאיר אפשרות הגדרה סביבתית, אך לא לדרוש header.

קריטריוני קבלה:
- אין כשלי 401/403 שמקורם במנגנון “גישה מוגנת”.
- אין הוספת auth חדש.

## 1.3 עקביות prefixes ו־routes
מטרה: יציבות API ושקיפות.

פעולות:
- מיפוי כל `include_router` ב־`app/main.py`:
  - לזהות כפילויות/אי־עקביות בין `prefix` שמוגדר ב־router לבין `include_router(prefix=...)`.
- לוודא שאין שינוי התנהגות של trailing slash (להימנע מ־`redirect_slashes=False`).
- להגדיר קו מנחה אחיד:
  - routers תחת `/api/v1` בלבד,
  - endpoints root מינימליים (`/health`, `/api/v1/health`).

קריטריוני קבלה:
- אין 404 בגלל trailing slash.
- אין “כפל prefix”.

## 1.4 DB Sessions & Transactions
מטרה: DB usage עקבי ובטוח.

פעולות:
- וידוא שימוש עקבי ב־`Depends(get_db)` ב־routers.
- הסרת יצירה ידנית של sessions במקומות שאפשר להימנע (למעט background jobs שדורשים זאת).
- הוספת עקרונות ל־services:
  - שירותים מקבלים `db: Session` מבחוץ.
  - שירותים לא פותחים session בעצמם (למעט תת־מערכות ייעודיות).

קריטריוני קבלה:
- אין leaks של connections.
- אין מצב שבו service “מחליט” לפתוח DB באופן לא צפוי.

---

# Phase 2 — LLM Agent / Chat Module Refactor (קובץ llm_chat.py)
מטרה: להפוך את מודול הסוכן ליציב, בדיד, קריא ומודולרי.

## 2.1 פירוק לפי אחריות
יעד תיקיות (דוגמה):
- `app/routers/llm_chat.py` — router בלבד.
- `app/services/llm/`:
  - `conversation_service.py` — orchestrator.
  - `state_service.py` — חישוב state וסטטוס תיק.
  - `tool_registry.py` — רישום tools והגדרות schema.
  - `prompt_builder.py` — בניית prompt באופן עקבי.
- `app/utils/llm/`:
  - parsing, regex helpers, normalizers.

## 2.2 הסרת “עקיפות זמניות”
דוגמה בולטת: `has_portfolio = True` כעקיפה זמנית.

פעולות:
- להחזיר לוגיקה אמיתית מבוססת DB.
- אם יש צורך במנגנון fallback — לעשות אותו explicit בקונפיג, לא “hardcoded override”.

## 2.3 Tool execution & logging
פעולות:
- אחידות logging:
  - request_id עקבי לכל שיחה.
  - תיעוד tool calls בצורה מובנית (כולל inputs/outputs מסוננים).
- הוצאה של regex/keywords לפונקציות util בדיקות.

קריטריוני קבלה:
- `llm_chat.py` יורד משמעותית בגודל.
- router נשאר דק.
- אין שינוי endpoint /api/v1/llm.* כלפי חוץ.

---

# Phase 3 — Data Layer & Migrations Hygiene
מטרה: שכבת נתונים צפויה, קלה לתחזוקה.

פעולות:
- סקירת `alembic/` ו־`migrations/`:
  - יישור קו: מקור אמת אחד למיגרציות.
  - תיעוד כלל עבודה ברור: איך מוסיפים schema changes.
- סקירת models:
  - naming conventions: `snake_case` לטבלאות, `camelCase` לשדות JSON/response (איפה שנדרש).
  - הוספת constraints/indexes רק כשברור שנדרש (ללא שבירות).

קריטריוני קבלה:
- תהליך migrations ברור, עקבי ומתועד.

---

# Phase 4 — Frontend Cleanup (ארגון, ביצועים, עקביות)
מטרה: pages דקים, קומפוננטות קטנות, לוגיקת חישוב ב־utils.

## 4.1 Pages כ־orchestrators
פעולות:
- מעבר על כל `frontend/src/pages/*`:
  - הוצאת חישובים/formatting ל־`frontend/src/utils/*`.
  - הוצאת קריאות API לשכבת API קיימת.
  - פיצול pages גדולים לתיקיות `components/` ו־`hooks/`.

## 4.2 Error handling אחיד
פעולות:
- אחידות הצגת errors:
  - error boundary למסכים כבדים.
  - תבנית הודעות משתמש בעברית.

## 4.3 CSS & Maintainability
פעולות:
- הימנעות מ־inline styles.
- ריכוז CSS למסכים/קומפוננטות בקבצים חיצוניים.

## 4.4 Performance
פעולות:
- lazy loading למסכים כבדים (חלק כבר קיים ב־RetirementScenariosPage).
- memoization נקודתית היכן שנדרש.

קריטריוני קבלה:
- build עובר.
- אין ירידה בפונקציונליות.

---

# Phase 5 — Cross-cutting Quality (Lint, Formatting, Typing)
מטרה: לאכוף סטנדרט איכות אחיד ומכני.

Backend:
- בחירה והטמעה של lint/format סטנדרטי (למשל ruff + black + isort) בהגדרות קיימות.
- בדיקות typing בסיסיות במקומות רגישים (אופציונלי, לא חובה בשלב ראשון).

Frontend:
- eslint/prettier אם לא מוגדרים/לא עקביים.

קריטריוני קבלה:
- ריצה עקבית ב־CI.

---

# Phase 6 — Testing, Regression & Release Discipline
מטרה: כל שינוי מגיע עם רשת ביטחון.

פעולות:
- הרחבת בדיקות Python לפי שירותים מרכזיים (tax, fixation, cashflow, scenario engine).
- הגדרת “smoke paths” מהירים (API + frontend build) לכל PR.
- תיעוד release checklist קצר.

קריטריוני קבלה:
- ירידה בכמות regressions.
- כל שינוי משמעותי מכוסה לפחות ב־smoke test.

---

# Definition of Done (הגדרה ברורה לסיום ניקוי)
- אין שגיאות תחביר Python.
- frontend build עובר.
- routers דקים, services ברורים.
- `llm_chat.py` מפוצל לפי אחריות וקצר משמעותית.
- אין הגנות גישה/אימות שמונעות שימוש (לפי דרישת המערכת).
- מבנה תיקיות רדוד, עקבי וברור.

---

# ניהול סיכונים
- סיכון: שינויי refactor שוברים imports.
  - מיתון: wrappers ותאימות לאחור, שינוי הדרגתי.
- סיכון: שינוי לוגיקה עסקית תוך “ניקוי”.
  - מיתון: להעביר לוגיקה כפי שהיא, ורק לאחר מכן לשפר עם בדיקות.

---

# הערה תפעולית
- שינויי קונפיג/שרת לא יבוצעו דרך restart אוטומטי; אם נדרש restart אחרי שינויי קוד, הדבר יצוין במפורש בסיכום העבודה.
