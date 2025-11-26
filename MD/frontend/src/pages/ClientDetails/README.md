# ClientDetails - מבנה מודולרי

## סקירה כללית
דף פרטי לקוח פוצל למבנה מודולרי של קומפוננטות קטנות ומנוהלות.

## מבנה התיקיות

```
ClientDetails/
├── index.tsx                          # קומפוננטה ראשית (26 שורות)
├── hooks/                             # Custom hooks
│   ├── useClientData.ts              # ניהול נתוני לקוח (36 שורות)
│   └── usePensionDate.ts             # ניהול תאריך קצבה (60 שורות)
└── components/                        # קומפוננטות UI
    ├── ClientInfo/                   # תצוגה ועריכת פרטי לקוח
    │   └── index.tsx                 # (140 שורות)
    ├── ClientNavigation/             # ניווט בין מודולים
    │   ├── index.tsx                 # (32 שורות)
    │   └── ModuleLink.tsx            # (26 שורות)
    └── ClientSystemSnapshot/         # שמירה ושחזור מצב
        └── index.tsx                 # (32 שורות)
```

## קומפוננטות

### 1. ClientDetailsPage (index.tsx)
**תפקיד:** קומפוננטה ראשית המרכיבה את כל הקומפוננטות הנוספות.

**תלויות:**
- `useClientData` - טעינת נתוני לקוח
- `ClientInfo` - תצוגת פרטי לקוח
- `ClientNavigation` - ניווט
- `ClientSystemSnapshot` - שמירת מצב

**Props:** אין (משתמש ב-useParams)

### 2. useClientData Hook
**תפקיד:** ניהול מצב וטעינת נתוני לקוח מה-API.

**Returns:**
```typescript
{
  client: ClientItem | null;
  loading: boolean;
  error: string | null;
  refreshClient: () => void;
}
```

### 3. usePensionDate Hook
**תפקיד:** ניהול עריכה ושמירה של תאריך קבלת קצבה.

**Parameters:**
- `client: ClientItem | null`
- `onUpdate: () => void`

**Returns:**
```typescript
{
  editMode: boolean;
  pensionStartDate: string;
  saving: boolean;
  error: string | null;
  successMessage: string | null;
  setEditMode: (value: boolean) => void;
  setPensionStartDate: (value: string) => void;
  handleSavePensionDate: () => Promise<void>;
  handleCancelEdit: () => void;
}
```

### 4. ClientInfo Component
**תפקיד:** תצוגה ועריכה של פרטי לקוח בסיסיים ותאריך קצבה.

**Props:**
```typescript
{
  client: ClientItem;
  onUpdate: () => void;
}
```

**Features:**
- תצוגת פרטי לקוח (ת"ז, תאריך לידה, מין, אימייל, טלפון)
- עריכת תאריך קבלת קצבה
- הודעות שגיאה והצלחה

### 5. ClientNavigation Component
**תפקיד:** קישורים לניווט בין מודולים שונים של הלקוח.

**Props:**
```typescript
{
  clientId: string;
}
```

**Modules:**
- קרנות פנסיה
- הכנסות נוספות
- נכסי הון
- קיבוע זכויות
- תרחישים

### 6. ModuleLink Component
**תפקיד:** קומפוננטת עזר לתצוגת קישור בודד.

**Props:**
```typescript
{
  to: string;
  label: string;
}
```

### 7. ClientSystemSnapshot Component
**תפקיד:** wrapper לקומפוננטת SystemSnapshot עם עיצוב מותאם.

**Props:**
```typescript
{
  clientId: number;
  onSnapshotRestored: () => void;
}
```

## שימוש

```typescript
import ClientDetailsPage from './pages/ClientDetails';

// In App.tsx
<Route path="/clients/:id" element={<ClientDetailsPage />} />
```

## יתרונות המבנה המודולרי

1. **קריאות משופרת** - כל קומפוננטה קטנה וממוקדת
2. **תחזוקה קלה** - קל למצוא ולתקן באגים
3. **שימוש חוזר** - ניתן לעשות שימוש חוזר בקומפוננטות
4. **בדיקות** - קל יותר לבדוק קומפוננטות קטנות
5. **ביצועים** - React.memo יכול לעבוד טוב יותר עם קומפוננטות קטנות

## גודל קבצים

כל הקבצים הם **פחות מ-300 שורות**:
- הקובץ הגדול ביותר: ClientInfo (140 שורות)
- הקובץ הקטן ביותר: ModuleLink (26 שורות)
- סה"כ: ~384 שורות (לעומת 252 שורות בקובץ המקורי)

## הערות

- כל הפונקציונליות המקורית נשמרה בדיוק
- העיצוב והסגנונות זהים למקור
- לא בוצעו שינויים בלוגיקה העסקית
- הקוד תואם ל-TypeScript strict mode

## תאריך פיצול
6 בנובמבר 2025
