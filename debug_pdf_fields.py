"""
סקריפט לחילוץ שמות שדות מטופס PDF
"""
from pathlib import Path
import pdf_filler

template_path = Path("templates/161d.pdf")

if template_path.exists():
    print("📄 Extracting field names from 161d.pdf...")
    fields = pdf_filler.get_pdf_fields(template_path)
    
    if fields:
        print(f"\n✅ Found {len(fields)} fields:")
        print("=" * 60)
        for i, field in enumerate(fields, 1):
            print(f"{i}. {field}")
        print("=" * 60)
    else:
        print("❌ No fields found or error reading PDF")
else:
    print(f"❌ Template not found: {template_path}")
