# Stage 18 - Release Engineering - Execution Notes (Tracked)

## Stage 18.1 Release Gates

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

## Stage 18.2 Rollback Procedure

- לבצע rollback לפי ה-runbook הרלוונטי.
- אין להוסיף מנגנוני rollback חדשים מעבר למה שכבר קיים בריפו.

## Stage 18.3 Runbooks

### Taxonomy Selection Rule (קשיח)

- "הסט הראשון" = קבוצת incidents הראשונה לפי סדר הופעה בקובץ taxonomy הראשי.
- אין לבחור subset ואין לשנות סדר.
- מקור אמת יחיד: taxonomy הראשי הקיים בריפו.
- אין בחירה ידנית של incidents.

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
