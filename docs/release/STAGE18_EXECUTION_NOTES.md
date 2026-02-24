# Stage 18 - Release Engineering - Execution Notes (Tracked)

## Stage 18.1 Release Gates

Release gates commands and determinism artifact spec are defined in docs/release/RELEASE_GATES.md
Artifact path: artifacts/determinism-report/determinism-report.json

Exception approved (single test file only): allow a minimal refactor in `tests/services/llm_chat/capability_router/stage16/test_determinism_report.py` to expose `build_cases()` for determinism artifact generation.
Constraints: no assertion changes, no expected-output changes, no behavior changes. This exception is limited to this file only.

### Determinism Report Guard (קשיח)

- אין ליצור generator חדש לדוח determinism.
- יש להשתמש רק במנגנון report קיים בריפו.
- אם אין command קיים שמייצר report, יש לעצור ולדווח (לא להמציא פתרון).
- המודל המבצע לא מוסיף tooling חדש.
- אין scope creep לכיוון observability חדש.

### CI Structure Hardening (קשיח)

- `release_gates` יהיה job נפרד ב-CI.
- רק אם מבנה ה-workflow הקיים לא מאפשר זאת technically, מותר fallback ל-step פנימי.
- מטרה: לאפשר Required Check בעתיד.
- אין לכתוב "מאושר פורמלית" עבור Stage 18.1 בלי ראיה של ריצת CI. במקום זאת: "Implementation נראה תואם לקריטריונים לפי דיווח, נדרש אימות ב CI".

## Stage 18.2 Canary Strategy

### Loader Selection Rule (קשיח)

כלל הכרעה מחייב:

- אם קיים loader יחיד ל-`capability_map`, לעדכן אותו נקודתית.
- אם קיימים מספר loaders או שאין נקודת טעינה ברורה, ליצור `canary.py`.

איסורים:

- אסור ליצור `canary.py` אם קיימת נקודת טעינה יחידה ברורה.
- אסור לפצל loading paths קיימים.

### min_core_version enforcement

#### Version Comparison Rule (קשיח)

השוואת גרסאות תתבצע כך:

- השוואת גרסאות תתבצע באמצעות parser קיים בריפו.
- אם אין parser קיים, להשתמש ב-`packaging.version`.
- אין לכתוב parser ידני.

דגש:

- השוואה לקסיקוגרפית אסורה.
- אין מימוש custom.

#### 2.4 Version source guard (קשיח, ללא יצירת SSOT חדש)

1. לחפש מקור גרסה קיים לפי סדר עדיפויות:

   - מקור גרסה קיים באפליקציה (module/version constant)
   - package metadata אם כבר בשימוש בריפו
   - כל מקור גרסה שכבר קיים בפועל ומשמש את המערכת (לא ליצור חדש)

2. אם נמצא מקור גרסה ברור:

   - להשתמש בו ל CORE_VERSION במצב core_and_map
   - להשוות מול min_core_version באמצעות parser קיים, ואם אין אז packaging.version

3. אם לא נמצא מקור גרסה ברור (מצב “missing version SSOT”):

   - לא ליצור `app/version.py`
   - לא ליצור CORE_VERSION זמני
   - ההתנהגות במצב `CAPABILITY_ROUTER_CANARY_MODE=core_and_map` תהיה דטרמיניסטית:

     - לבצע fallback ל stable map מיד
     - ולוג ברור: “core version source missing - core_and_map disabled until version SSOT exists”
   - במצב זה, אין min_core_version check כי core_and_map מושבת.

## Stage 18.2 Rollback Procedure

- לבצע rollback לפי ה-runbook הרלוונטי.
- אין להוסיף מנגנוני rollback חדשים מעבר למה שכבר קיים בריפו.

## Stage 18.3 Runbooks

### 4.1 Locate incident SSOT (taxonomy or equivalent) - קשיח, עם fallback

סדר discovery מחייב:

1. לנסות לאתר path לקובץ taxonomy דרך `test_trace_event_taxonomy.py`:

   - אם הטסט מפנה לקובץ YAML/JSON וכו, זה ה SSOT.

2. אם אין path לקובץ, לבדוק האם הטסט:

   - מגדיר incident list inline (למשל list/dict של ids)
   - או מייבא incident list / taxonomy object ממודול אחר

במקרה כזה:

- ה SSOT ל incident list הוא אותו מקור (הטסט עצמו או המודול שממנו הוא מייבא).
- “הסט הראשון” מוגדר כקבוצה הראשונה לפי סדר הופעה באותו מקור.
- יוצרים runbooks לפי הרשימה הזו, בלי לכתוב taxonomy file חדש.

3. לעצור רק אם:

- אין קובץ,
- ואין incident list inline,
- ואין מודול מיובא שמכיל incident ids בצורה שניתנת לשליפה דטרמיניסטית.

## Scope Guard

- אין שינוי runtime logic של `capability_router`.
- אין שינוי contracts קיימים, כולל `predicate_eval`.
- אין פתיחת Stage 17 מחדש.
- אין הוספת tooling חדש מעבר למה שכבר קיים בריפו.
- אין שינוי ל-`.gitignore`.
- אין שינוי קוד.
- אין שינוי workflows.

## Execution Order

1. לאתר האם קיים מסמך tracked שמכיל כבר Stage 18. אם קיים, לערוך אותו נקודתית בלבד.
2. אם אין מסמך כזה, להשתמש במסמך זה כמסמך tracked מינימלי לשלב Stage 18 בלבד.
3. להטמיע את 5 ההבהרות במיקומים הבאים בלבד:
   - Loader Selection Rule תחת Stage 18.2.
   - Version Comparison Rule תחת min_core_version enforcement.
   - Determinism Report Guard תחת Stage 18.1.
   - Taxonomy Selection Rule תחת Stage 18.3.
   - CI Structure Hardening תחת Stage 18.1.
4. ולידציה בלבד:
   - לוודא שהקובץ tracked ב-Git.
   - לוודא שהשינויים מופיעים ב-`git diff`.
   - לא להריץ בדיקות קוד (אין בדיקות נדרשות לעדכון הנחיה בלבד).
