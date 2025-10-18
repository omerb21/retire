"""
בדיקת טמפלייט טופס 161ד
"""
from pathlib import Path
from pdfrw import PdfReader

template_path = Path("templates/161d.pdf")

if not template_path.exists():
    print(f"❌ Template not found: {template_path}")
else:
    print(f"✅ Template found: {template_path}")
    print(f"   Size: {template_path.stat().st_size:,} bytes")
    
    try:
        reader = PdfReader(str(template_path))
        print(f"✅ PDF opened successfully")
        
        if reader.Root.AcroForm:
            print(f"✅ AcroForm found")
            
            if reader.Root.AcroForm.Fields:
                fields = []
                for field in reader.Root.AcroForm.Fields:
                    if field.T:
                        clean_name = field.T[1:-1] if field.T.startswith('(') else str(field.T)
                        fields.append(clean_name)
                
                print(f"\n📋 Found {len(fields)} fields:")
                for i, fname in enumerate(fields, 1):
                    print(f"   {i}. {fname}")
            else:
                print("⚠️ AcroForm exists but no Fields found")
        else:
            print("❌ No AcroForm found in PDF!")
            print("   This PDF cannot be filled programmatically.")
            print("   You need a PDF with fillable form fields.")
            
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
