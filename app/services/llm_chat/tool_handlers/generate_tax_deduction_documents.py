import json
import logging
import os
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models import Client, PensionFund
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset

logger = logging.getLogger("app.llm_chat.tools")


def handle_generate_tax_deduction_documents(
    *,
    args: dict,
    client_id: int,
    db: Session,
    client_obj: Optional[Client],
) -> str:
    logger.info("📄 GENERATE_TAX_DEDUCTION_DOCUMENTS called - Tax Document Generation!")

    try:
        document_type = args.get("document_type")
        if not document_type:
            document_type = "kibua_zechuyot"

        if document_type == "kibua_zechuyot":
            document_type = "fixation_package"

        # Validate client exists
        if not client_obj:
            return f"Error: לקוח עם מזהה {client_id} לא נמצא"

        if document_type in {"fixation_package", "package", "161d_package"}:
            from app.services.documents import generate_document_package

            package_result = generate_document_package(db, client_id)
            if not (isinstance(package_result, dict) and package_result.get("success")):
                err_msg = None
                try:
                    err_msg = str(package_result.get("error") or "").strip() or None
                except Exception:
                    err_msg = None
                return json.dumps(
                    {
                        "success": False,
                        "error_code": "DOCUMENT_PACKAGE_FAILED",
                        "message": err_msg or "שגיאה בייצור חבילת מסמכי קיבוע זכויות",
                    },
                    ensure_ascii=False,
                )

            folder = package_result.get("folder")
            files = package_result.get("files")
            folder_text = str(folder or "")
            folder_text_norm = folder_text.replace("\\", "/")
            if folder_text_norm.startswith("packages/"):
                folder_in_packages = folder_text_norm[len("packages/") :]
            else:
                folder_in_packages = folder_text_norm
            folder_in_packages = folder_in_packages.strip("/")

            file_entries: list[dict[str, str]] = []
            if isinstance(files, list):
                for name in files:
                    file_name = str(name or "").strip()
                    if not file_name:
                        continue
                    rel_path = (
                        f"{folder_in_packages}/{file_name}"
                        if folder_in_packages
                        else file_name
                    )
                    file_entries.append(
                        {
                            "name": file_name,
                            "download_url": f"/api/v1/files?path={quote(rel_path)}",
                        }
                    )

            safe_filename = f"fixation_{client_id}_documents.zip"
            hebrew_filename = (
                f"מסמכי_קיבוע_{client_obj.first_name}_{client_obj.last_name}.zip"
            )
            encoded_filename = quote(hebrew_filename)
            download_url = f"/api/v1/fixation/{client_id}/package"

            return json.dumps(
                {
                    "success": True,
                    "message": "✅ חבילת מסמכי קיבוע זכויות הופקה בהצלחה",
                    "client_id": client_id,
                    "client_name": client_obj.full_name,
                    "document_type": document_type,
                    "download_url": download_url,
                    "download_filename": safe_filename,
                    "download_filename_hebrew": hebrew_filename,
                    "download_filename_hebrew_encoded": encoded_filename,
                    "package_folder": folder_in_packages,
                    "files": file_entries,
                },
                ensure_ascii=False,
            )

        # ===== GUARDRAIL: Check for critical assets =====
        pension_count = (
            db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
        )
        capital_count = (
            db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
        )
        income_count = (
            db.query(AdditionalIncome)
            .filter(AdditionalIncome.client_id == client_id)
            .count()
        )

        total_assets = pension_count + capital_count + income_count
        logger.info(
            "🔍 GUARDRAIL check (tax docs): client_id=%s, pensions=%d, capitals=%d, incomes=%d",
            client_id,
            pension_count,
            capital_count,
            income_count,
        )

        if total_assets == 0:
            guardrail_response = {
                "success": False,
                "error_code": "MISSING_CRITICAL_DATA",
                "message": "לא נמצאו נכסי פנסיה, נכסי הון או הכנסות נוספות ללקוח. "
                "לא ניתן להפיק מסמכי מס ללא נתונים. "
                "אנא בקש מהלקוח להזין נתונים או בצע המרת כספים לפני הפקת מסמכים.",
                "missing_data": {
                    "pension_funds": pension_count == 0,
                    "capital_assets": capital_count == 0,
                    "additional_incomes": income_count == 0,
                },
                "required_actions": [
                    "הזנת נכסי פנסיה (קרנות פנסיה, ביטוחי מנהלים)",
                    "הזנת נכסי הון (פיצויים, חסכונות)",
                    "הזנת הכנסות נוספות (שכירות, דיבידנדים)",
                    "או ביצוע המרת כספים דרך מסך עזיבת עבודה",
                ],
            }
            logger.warning(
                "⚠️ GUARDRAIL blocked tax document generation - no assets for client %s",
                client_id,
            )
            return json.dumps(guardrail_response, ensure_ascii=False)

        # Generate unique document ID
        doc_id = f"DOC-{client_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        logger.info(
            "📄 GENERATE_TAX_DEDUCTION_DOCUMENTS: client_id=%s, type=%s",
            client_id,
            document_type,
        )

        # Document type names
        doc_type_names = {
            "kibua_zechuyot": "מסמך קיבוע זכויות",
            "ptor_pitzuim": "אישור פטור פיצויים",
            "form_161": "טופס 161",
            "tax_spread": "מסמך פריסת מס",
        }

        # ===== ACTUAL PDF GENERATION =====
        import io as io_module

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        pdf_buffer = io_module.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        styles = getSampleStyleSheet()
        hebrew_style = ParagraphStyle(
            "Hebrew",
            parent=styles["Normal"],
            fontSize=12,
            alignment=TA_RIGHT,
        )
        title_style = ParagraphStyle(
            "HebrewTitle",
            parent=styles["Title"],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=30,
        )

        story = []
        doc_name = doc_type_names.get(document_type, "מסמך")
        story.append(Paragraph(doc_name, title_style))
        story.append(Spacer(1, 20))

        # Client info
        story.append(Paragraph(f"שם לקוח: {client_obj.full_name}", hebrew_style))
        story.append(
            Paragraph(f"ת.ז.: {client_obj.id_number or 'לא צוין'}", hebrew_style)
        )
        story.append(
            Paragraph(
                f"תאריך הפקה: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                hebrew_style,
            )
        )
        story.append(Spacer(1, 20))

        # Document-specific content
        if document_type == "kibua_zechuyot":
            story.append(
                Paragraph("אישור קיבוע זכויות לפטור ממס על קצבה", hebrew_style)
            )
            story.append(Spacer(1, 10))
            story.append(
                Paragraph(
                    "בהתאם לסעיף 9א לפקודת מס הכנסה, מאושר בזאת קיבוע זכויות לפטור ממס על קצבה.",
                    hebrew_style,
                )
            )
        elif document_type == "ptor_pitzuim":
            story.append(Paragraph("אישור פטור על פיצויי פיטורים", hebrew_style))
            story.append(Spacer(1, 10))
            story.append(
                Paragraph(
                    "בהתאם לסעיף 9(7א) לפקודת מס הכנסה, מאושר בזאת פטור על פיצויי פיטורים.",
                    hebrew_style,
                )
            )
        elif document_type == "form_161":
            story.append(Paragraph("טופס 161 - הודעה על פרישה מעבודה", hebrew_style))
            story.append(Spacer(1, 10))
            story.append(
                Paragraph(
                    "טופס זה מיועד להגשה לרשות המיסים בעת פרישה מעבודה.",
                    hebrew_style,
                )
            )
        elif document_type == "tax_spread":
            story.append(Paragraph("מסמך פריסת מס", hebrew_style))
            story.append(Spacer(1, 10))
            story.append(
                Paragraph(
                    "בקשה לפריסת מס על הכנסה חד-פעמית בהתאם לסעיף 8(ג) לפקודת מס הכנסה.",
                    hebrew_style,
                )
            )

        story.append(Spacer(1, 40))
        story.append(Paragraph("חתימה: _______________", hebrew_style))
        story.append(Paragraph("תאריך: _______________", hebrew_style))

        doc.build(story)
        pdf_buffer.seek(0)

        # Save PDF to artifacts folder
        artifacts_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "artifacts",
            "documents",
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        pdf_path = os.path.join(artifacts_dir, f"{doc_id}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_buffer.getvalue())

        pdf_size = os.path.getsize(pdf_path)
        logger.info("📄 Tax document PDF saved: %s (%d bytes)", pdf_path, pdf_size)

        response = {
            "success": True,
            "message": f"✅ המסמך הופק בהצלחה! {doc_name} מוכן להורדה.",
            "status_message": f"✅ המסמך הופק בהצלחה! {doc_name} מוכן להורדה.",
            "document_id": doc_id,
            "client_id": client_id,
            "client_name": client_obj.full_name,
            "document_type": document_type,
            "document_name": doc_name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "PDF",
            "file_size_bytes": pdf_size,
            "download_url": f"/api/v1/documents/{doc_id}/download",
            "next_steps": [],
        }

        # Add next steps based on document type
        if document_type == "kibua_zechuyot":
            response["next_steps"] = [
                "יש להגיש את המסמך לפקיד השומה",
                "לשמור עותק בתיק הלקוח",
                "לעדכן את המערכת לאחר אישור",
            ]
        elif document_type == "ptor_pitzuim":
            response["next_steps"] = [
                "יש להעביר למעסיק לצורך ניכוי מס",
                "לשמור עותק לתיעוד",
            ]
        elif document_type == "form_161":
            response["next_steps"] = [
                "יש למלא את הפרטים החסרים",
                "להגיש לרשות המיסים",
                "לשמור אישור הגשה",
            ]
        elif document_type == "tax_spread":
            response["next_steps"] = [
                "יש להגיש בקשה לפריסת מס לפקיד השומה",
                "לעקוב אחר לוח התשלומים",
            ]

        logger.info(
            "✅ GENERATE_TAX_DEDUCTION_DOCUMENTS completed: doc_id=%s",
            doc_id,
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("GENERATE_TAX_DEDUCTION_DOCUMENTS failed: %s", e, exc_info=True)
        return f"Error: שגיאה בהפקת המסמך: {str(e)}"
