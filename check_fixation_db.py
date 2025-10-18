"""
בדיקת נתוני קיבוע זכויות ב-DB
"""
from app.database import SessionLocal
from app.models.fixation_result import FixationResult
from sqlalchemy import desc

db = SessionLocal()

# בדיקת קיבוע זכויות ללקוח 4
fixation = db.query(FixationResult).filter(
    FixationResult.client_id == 4
).order_by(desc(FixationResult.created_at)).first()

if fixation:
    print(f"✅ נמצא קיבוע זכויות ללקוח 4")
    print(f"   ID: {fixation.id}")
    print(f"   Created: {fixation.created_at}")
    print(f"   Has raw_result: {fixation.raw_result is not None}")
    
    if fixation.raw_result:
        raw_result = fixation.raw_result
        print(f"\n📊 Keys in raw_result:")
        for key in raw_result.keys():
            print(f"   - {key}")
        
        if 'exemption_summary' in raw_result:
            print(f"\n📊 exemption_summary keys:")
            for key in raw_result['exemption_summary'].keys():
                print(f"   - {key}: {raw_result['exemption_summary'][key]}")
        
        if 'grants' in raw_result:
            print(f"\n📊 Number of grants: {len(raw_result['grants'])}")
            if raw_result['grants']:
                print(f"   First grant keys: {list(raw_result['grants'][0].keys())}")
else:
    print("❌ לא נמצא קיבוע זכויות ללקוח 4")

db.close()
