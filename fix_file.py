
import os

file_path = r"app\services\llm_agent_tools_service.py"

# Read the file in binary mode to handle any encoding issues gracefully
with open(file_path, "rb") as f:
    content = f.read()

# Find the point where corruption likely started (around line 1369)
# The previous valid content ended with the return of get_tax_projection.
# We search for the byte sequence corresponding to the end of that method.
end_marker = b'            "explanation": "\\n".join(tax_explanation_parts),\r\n        }\r\n'
end_pos = content.find(end_marker)

if end_pos == -1:
    # Try with just \n
    end_marker = b'            "explanation": "\\n".join(tax_explanation_parts),\n        }\n'
    end_pos = content.find(end_marker)

if end_pos != -1:
    # Cut off everything after the marker
    clean_content = content[:end_pos + len(end_marker)]
    
    # Append the new method
    new_method = """
    def get_pension_products(self) -> Dict[str, Any]:
        \"\"\"
        מחזיר את כל המוצרים הפנסיוניים וההוניים של הלקוח בצורה מרוכזת.
        \"\"\"
        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "GET_PENSION_PRODUCTS",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        products = []

        # 1. קרנות פנסיה וקופות גמל
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()

        for pf in pension_funds:
            products.append({
                "Product Name": pf.fund_name,
                "Managing Company": pf.managing_company or "לא ידוע",
                "Type": f"פנסיוני ({pf.fund_type or 'כללי'})",
                "Accumulated Balance": pf.balance or 0,
                "Monthly Deposit": pf.monthly_deposit or 0,
                "Management Fee": f"{pf.management_fee_accumulation or 0}% מצבירה",
                "Status": "פעיל" if pf.is_active else "לא פעיל"
            })

        # 2. נכסים הוניים (ביטוח מנהלים, גמל להשקעה)
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()

        for ca in capital_assets:
            products.append({
                "Product Name": ca.asset_name,
                "Managing Company": ca.managing_company or "לא ידוע",
                "Type": f"הוני ({ca.asset_type or 'כללי'})",
                "Accumulated Balance": ca.current_balance or 0,
                "Monthly Deposit": ca.monthly_deposit or 0,
                "Management Fee": f"{ca.management_fee_accumulation or 0}% מצבירה",
                "Status": "פעיל" if ca.is_active else "לא פעיל"
            })

        # מיון לפי יתרה יורדת
        products.sort(key=lambda x: x["Accumulated Balance"], reverse=True)

        total_balance = sum(p["Accumulated Balance"] for p in products)
        total_deposit = sum(p["Monthly Deposit"] for p in products)

        # יצירת הסבר טקסטואלי קצר לשימוש המודל
        explanation = (
            f"נמצאו {len(products)} מוצרים בתיק.\\n"
            f"סה\\"כ צבירה: {total_balance:,.0f} ₪.\\n"
            f"סה\\"כ הפקדה חודשית: {total_deposit:,.0f} ₪."
        )

        return {
            "success": True,
            "tool_name": "GET_PENSION_PRODUCTS",
            "result": {
                "products": products,
                "total_balance": total_balance,
                "total_monthly_deposit": total_deposit,
                "count": len(products)
            },
            "explanation": explanation
        }
"""
    # Write back the clean content + new method
    # We write as binary to preserve existing encoding of the first part, 
    # and encode the new part as utf-8 (which is standard for python files)
    with open(file_path, "wb") as f:
        f.write(clean_content)
        f.write(new_method.encode('utf-8'))
    
    print("Successfully repaired file and appended new method.")
else:
    print("Could not find the end marker. File structure might be different than expected.")
    # Fallback: Read text, find line 1368 approx, truncate and write
