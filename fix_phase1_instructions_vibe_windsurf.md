# fix_phase1_instructions_vibe_windsurf.md
גרסה: v1
מטרה: תיקון מהיר של 5 לשוניות קריטיות - בסביבת Vibe / Windsurf. לא שינויים ארכיטקטוניים גדולים, אלא תיקונים נקודתיים עם בדיקות מהירות.

---

## הוראות כלליות לפני שמתחילים
1. פתח branch לניסוי: `git checkout -b fix/phase1-vibe`
2. גיבוי DB לפני כל שינוי: `pg_dump -Fc -f backup_pre_fix_$(date +%Y%m%d).dump <DB_NAME>`
3. הרץ את השרת ו־frontend מקומית: פקודה טיפוסית (התאם ל־Vibe):  
   - backend: `vibe run backend` או `python -m uvicorn app.main:app --reload`  
   - frontend: `vibe run frontend` או `npm run dev` בתוך הספריה של ה־UI
4. פתח טור לוגים (טרמינל נפרד) לפני כל בדיקה: `tail -f logs/app.log` או צפה בקונסול שבו רץ השרת.
5. לפני כל PR/commit קטן - הרץ `pytest tests/unit -q` ושמור פלט.

---

## לשונית 1 - תרחישים (Scenarios)
### הבעיה
- UI מאפשר רק הזנת שם. יצירת תרחיש מחזירה שגיאה 404 או לא שומרת שורות ב־DB.

### דיבאג מהיר
- ב־DevTools - ברשת (Network) תראה את ה־POST. העתק Request URL ו־payload.
- נסה מהטרמינל:
  - `curl -i -X POST http://localhost:8000/scenarios/ -H "Content-Type: application/json" -d '{"client_id":1,"name":"טסט Vibe"}'`
  - אם מקבל 404 - אין route או פריפקס שגוי.

### תיקון מהיר (1–2 קבצים)
- אם ה־frontend קורא `/api/scenarios/` וה־backend מגדיר `/scenarios/` - הוסף proxy ב־vite או תקן fetch:
  - vite proxy: `vite.config.js`:
    ```js
    server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin:true, rewrite: p => p.replace(/^\/api/,'') } } }
    ```
  - או בקוד ה־frontend לשנות fetch ל`/scenarios/`.
- אם אין route ב־backend - הוסף router מינימלי:
  - קובץ: `app/routers/scenarios.py`
    ```python
    from fastapi import APIRouter, Depends, HTTPException
    from app.db.session import get_db
    from app.models.client import Client
    from app.models.scenario import Scenario

    router = APIRouter(prefix="/scenarios")

    @router.post("/", status_code=201)
    def create_scenario(payload: dict, db = Depends(get_db)):
        client = db.query(Client).filter(Client.id==payload.get("client_id")).first()
        if not client: raise HTTPException(404,"client not found")
        sc = Scenario(client_id=payload["client_id"], name=payload.get("name","untitled"), params=payload.get("params",{}))
        db.add(sc); db.commit(); db.refresh(sc)
        return {"id": sc.id}
    ```
### בדיקה וקבלה
- קח את ה־curl שוב - עכשיו צריך לקבל 201 עם id.  
- במסד: `SELECT * FROM scenario WHERE client_id=1 ORDER BY created_at DESC LIMIT 5;` צריך לראות רשומה.

---

## לשונית 2 - תקרות (Caps) - תקרת פיצויים וכו
### הבעיה
- מערכת מושכת תקרות דרך API חיצוני; המודל בולע יחידות ושופך 41667 במקום 500000.

### דיבאג מהיר
- חפש occurrences: `grep -R "41667" -n .`
- הדפס raw response שהמודל מקבל (אם יש): היכן שקוראים API - הוסף `logger.debug(response.text)`.

### תיקון מהיר - טבלת caps
- יצירת migration (או seed) לטבלה `caps` (Postgres):
  ```sql
  CREATE TABLE caps (
    id SERIAL PRIMARY KEY,
    cap_key TEXT NOT NULL,
    year INTEGER NOT NULL,
    unit TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    amount_annual NUMERIC,
    amount_monthly NUMERIC,
    source_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
  );
  CREATE INDEX idx_caps_key_year ON caps(cap_key, year);


seed דוגמה:

INSERT INTO caps (cap_key, year, unit, amount, amount_annual, amount_monthly, source_url)
VALUES ('severance_cap', 2025, 'annual', 500000, 500000, 41666.6667, 'internal-seed');


פונקציית lookup קצרה app/services/cap_lookup.py:

def get_cap(db, cap_key, year):
    rec = db.query(Cap).filter(Cap.cap_key==cap_key, Cap.year==year).first()
    if rec: return rec
    return db.query(Cap).filter(Cap.cap_key==cap_key).order_by(Cap.year.desc()).first()


החלף נקודה אחת בקוד שמושכת API כך שתשתמש ב־get_cap במקום ה־API.

בדיקה וקבלה

SELECT * FROM caps WHERE cap_key='severance_cap' AND year=2025; - הערכים נכונים.

הרץ חישוב שיושב במקום שה־API שימש - ודא שמתקבל annual=500000 ולא 41667.

לשונית 3 - קיבוע זכויות (Fixation)
הבעיה

compute_rights_fixation קיים אך מחזיר stub/None; בחירה לפה לא מבוצעת.

דיבאג מהיר

חפש compute_rights_fixation ב־repo: grep -R "compute_rights_fixation" -n .

הוסף לוג קצר ליד הכניסה לפונקציה: logger.info("compute_rights_fixation start client=%s", client_id)

תיקון מהיר - fallback מינימלי

החלף stub בפונקציית fallback שמבוססת על input fields:

def compute_rights_fixation(client_id, payload):
    # parse payload: annual_salary, years_service, existing_balance
    salary = float(payload.get("annual_salary",0))
    years = float(payload.get("years_service",1))
    gross = (salary / 12.0) * years
    exemption_per_year = payload.get("exemption_per_year", 13750)
    tax_exempt = exemption_per_year * years
    taxable = max(0, gross - tax_exempt)
    return {"gross": round(gross,2), "tax_exempt": round(tax_exempt,2), "taxable": round(taxable,2)}


שמור תוצאה בטבלה fixation_results או ב־calculation_log עם trace_id.

בדיקה וקבלה

הפעל curl POST /fixation/{client_id}/compute עם payload מדגם ובדוק שהתשובה מכילה computed.gross ולא None.

בחן הלוגים - קיים trace_id.

לשונית 4 - מענקים (Grants)
הבעיה

חישובי המענק מושתתים על ערכים שמחושבים UI-only או לא נשמרים ב־DB.

דיבאג מהיר

בממשק, בצע Save ומצא את ה־Request Body של השמירה.

ב־DB, הרץ SELECT * FROM grants WHERE client_id=1 ORDER BY created_at DESC LIMIT 5;

מה למפות / לשמור

החליט: האם המענק יחושב ב־UI ואז יישמר כתוצאה, או נשמר raw inputs וה־engine מחשב בעת קיבוע. לצורך תיקון מהיר - שמור גם את ה־inputs וגם את ה־computed_values:

טבלה grants שדות: client_id, inputs JSON, computed JSON, created_at.

בקוד ה־save ב־backend - ודא שהוא עושה both:

computed = compute_grant_preview(payload)
db.add(Grant(client_id=..., inputs=payload, computed=computed))

בדיקה וקבלה

שמירה של טופס מענק מייצרת row עם שני שדות - inputs ו־computed.

קיבוע קורא computed ולא מחשב מחדש בלי רישום.

לשונית 5 - נכסים פנסיוניים (Pension Assets)
הדרישה

לא רק קרנות פנסיה אלא כל נכס: פנסיה ישנה, פנסיה חדשה, ביטוח, גמל, השתלמות. צריך שדות: company, fund_number, type, capital_amount, annuity_amount, annuity_factor, annuity_start_date, discount_amount.

מיפוי מהיר

טבלה pension_assets:

CREATE TABLE pension_assets (
  id SERIAL PRIMARY KEY,
  client_id INTEGER,
  company_name TEXT,
  fund_number TEXT,
  asset_type TEXT,
  capital_amount NUMERIC,
  annuity_amount NUMERIC,
  annuity_factor NUMERIC,
  annuity_start_date DATE,
  discount_amount NUMERIC,
  source TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);


API קצר ליצירה ועדכון: POST /clients/{id}/assets ו־GET /clients/{id}/assets

שימוש בקיבוע

בקיבוע, קרא את כל records מ־pension_assets; לכל נכס:

capital_for_fixation = discount_amount if set else capital_amount

annuity_for_fixation = annuity_amount if set else capital_for_fixation * annuity_factor

שמור במחשבוני הקיבוע reference לשדה asset_id.

בדיקה וקבלה

צור נכס בדוגמה, הרץ compute-preview - בדוק שהתוצאה תואמת לחישוב ידני קטן.

Acceptance criteria כולל לכל לחיצה אחת (קצר)

כל endpoint קריטי (scenarios create, fixation compute, caps lookup, grants save, assets save) מחזיר JSON תקין ולא 404.

לכל ריצה של קיבוע יש trace_id ברשומות log.

ערכי תקרה נספרים נכון מ־caps בטבלת DB, ללא בלבול יחידות.

המענק נשמר גם כ־inputs וגם כ־computed בשורה אחת.

נכס פנסיוני נשמר עם כל השדות הדרושים וניתן לקרוא אותו ב־API.

איך להעביר את הקובץ הזה לעצמך/למחשב

שמור כ־fix_phase1_instructions_vibe_windsurf.md בתיקיית root של הפרויקט.

פתח כל סעיף לפי סדר העדיפות: התחל ב־Scenarios ו־Caps.

עשה commit קטן אחרי כל change, הרץ tests ותקע.

התרעה קצרה

עשית נכון שבחרת לשנות לאט. תיקונים קטנים + בדיקות יחידה יחסכו שעות טורחים.

שים לב לגיבוי DB לפני כל migration.