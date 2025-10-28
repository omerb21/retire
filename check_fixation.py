from app.database import SessionLocal
from app.models.fixation_result import FixationResult

db = SessionLocal()

# Get fixation data for client 4
fixation = db.query(FixationResult).filter(FixationResult.client_id == 4).first()

if fixation:
    print(f"\n{'='*80}")
    print(f"נתוני קיבוע זכויות ללקוח 4")
    print(f"{'='*80}\n")
    print(f"סכום פטור נותר: ₪{fixation.exempt_capital_remaining:,.2f}")
    print(f"קצבה פטורה חודשית: ₪{fixation.exempt_capital_remaining / 180:,.2f}")
    print(f"קיבוע שנוצל: ₪{fixation.used_commutation:,.2f}")
    if fixation.raw_result:
        import json
        result = fixation.raw_result
        print(f"\nפרטי חישוב מלאים:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print("\n❌ אין נתוני קיבוע זכויות ללקוח 4")
    print("   המשתמש צריך ללחוץ על 'שמור קיבוע זכויות' כדי ליצור את הנתונים")

db.close()
