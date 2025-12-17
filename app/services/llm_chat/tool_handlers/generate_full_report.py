import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Client, PensionFund, Scenario
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.fixation_result import FixationResult
from app.schemas.report import ReportPdfRequest
from app.services.documents.converters import find_wkhtmltopdf
from app.services.documents.generators.full_report_generator import (
    generate_full_report_pdf as generate_full_report_pdf_html,
)
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.retirement_age_service import calculate_retirement_age
from app.services.report_service import generate_report_pdf

logger = logging.getLogger("app.llm_chat.tools")


def handle_generate_full_report(
    *,
    args: dict,
    client_id: int,
    db: Session,
    client_obj: Optional[Client],
    agent_tools: AgentToolsService,
) -> str:
    logger.info("📄 GENERATE_FULL_REPORT called - Document Generation Mode!")

    def _add_months(ym: str, months: int) -> str:
        """Add months to a YYYY-MM string and return YYYY-MM."""
        year = int(ym[0:4])
        month = int(ym[5:7])
        total = (year * 12 + (month - 1)) + months
        new_year = total // 12
        new_month = (total % 12) + 1
        return f"{new_year:04d}-{new_month:02d}"

    try:
        report_type = args.get("report_type", "full")
        output_format = args.get("output_format") or args.get("format") or "html"
        include_charts = args.get("include_charts", True)
        ensure_analysis = args.get("ensure_analysis", True)
        retirement_date_arg = args.get("retirement_date")

        # Validate client exists
        if not client_obj:
            return f"Error: לקוח עם מזהה {client_id} לא נמצא"

        if str(output_format).lower() != "pdf":
            open_path = f"/clients/{client_id}/reports?auto_html=1"
            response = {
                "success": True,
                "client_id": client_id,
                "open_path": open_path,
                "report_type": report_type,
                "status_message": "פותח את דוח ה-HTML בעמוד התוצאות.",
            }
            return json.dumps(response, ensure_ascii=False)

        # ===== GUARDRAIL: Check for critical assets =====
        pension_count = db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
        capital_count = db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
        income_count = (
            db.query(AdditionalIncome).filter(AdditionalIncome.client_id == client_id).count()
        )

        total_assets = pension_count + capital_count + income_count
        logger.info(
            "🔍 GUARDRAIL check: client_id=%s, pensions=%d, capitals=%d, incomes=%d",
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
                "לא ניתן להפיק דוח ללא נתונים. "
                "אנא בקש מהלקוח להזין נתונים או בצע המרת כספים לפני הפקת דוח.",
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
                "⚠️ GUARDRAIL blocked report generation - no assets for client %s",
                client_id,
            )
            return json.dumps(guardrail_response, ensure_ascii=False)

        # ===== GUARDRAIL: Require at least one computed cashflow analysis =====
        # A report is allowed if there is:
        # 1. A saved scenario with computed cashflow data, OR
        # 2. A saved FixationResult from RUN_RETIREMENT_CASHFLOW_ANALYSIS
        scenario: Optional[Scenario] = None
        scenario_has_results = False
        fixation_result: Optional[FixationResult] = None

        # Check for FixationResult first (from RUN_RETIREMENT_CASHFLOW_ANALYSIS)
        fixation_result = (
            db.query(FixationResult)
            .filter(FixationResult.client_id == client_id)
            .order_by(FixationResult.created_at.desc())
            .first()
        )

        if fixation_result and fixation_result.raw_result:
            # FixationResult exists - this means RUN_RETIREMENT_CASHFLOW_ANALYSIS was run
            logger.info(
                "🔍 GUARDRAIL: Found FixationResult for client %s (id=%s, created_at=%s)",
                client_id,
                fixation_result.id,
                fixation_result.created_at,
            )
            scenario_has_results = True

        # Also check for scenarios with cashflow projection
        scenarios_with_cashflow = (
            db.query(Scenario)
            .filter(
                Scenario.client_id == client_id,
                Scenario.cashflow_projection.isnot(None),
            )
            .order_by(Scenario.created_at.desc())
            .all()
        )

        for candidate in scenarios_with_cashflow:
            if not candidate.cashflow_projection:
                continue
            try:
                parsed_cashflow = (
                    json.loads(candidate.cashflow_projection)
                    if isinstance(candidate.cashflow_projection, str)
                    else candidate.cashflow_projection
                )
                if parsed_cashflow:
                    scenario = candidate
                    scenario_has_results = True
                    logger.info(
                        "🔍 GUARDRAIL: Found Scenario with cashflow for client %s (id=%s)",
                        client_id,
                        scenario.id,
                    )
                    break
            except Exception:
                continue

        if not scenario_has_results:
            logger.warning(
                "⚠️ Cashflow analysis was not found in DB for client %s. Proceeding with report generation anyway.",
                client_id,
            )

        analysis_result: Optional[dict] = None
        analysis_performed = False

        if ensure_analysis:
            retirement_date_to_use: Optional[str] = None

            desired_income_to_use: Optional[float] = None
            desired_income_arg = args.get("desired_monthly_income") or args.get(
                "target_monthly_pension"
            )
            try:
                if desired_income_arg is not None and str(desired_income_arg).strip():
                    desired_income_to_use = float(desired_income_arg)
            except Exception:
                desired_income_to_use = None

            if isinstance(retirement_date_arg, str) and retirement_date_arg.strip():
                retirement_date_to_use = retirement_date_arg.strip()
            else:
                try:
                    if client_obj.birth_date and client_obj.gender:
                        retirement_info = calculate_retirement_age(
                            client_obj.birth_date, client_obj.gender
                        )
                        retirement_dt = retirement_info.get("retirement_date")
                        if retirement_dt:
                            retirement_date_to_use = retirement_dt.isoformat()
                except Exception:
                    retirement_date_to_use = None

            if retirement_date_to_use:
                analysis_raw = agent_tools.run_retirement_cashflow_analysis(
                    retirement_date=retirement_date_to_use,
                    desired_monthly_income=desired_income_to_use,
                    apply_max_exemption=False,
                )

                if analysis_raw.get("success"):
                    analysis_result = analysis_raw.get("result")
                    analysis_performed = True

        # Generate unique report ID
        report_id = f"RPT-{client_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        artifacts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "artifacts",
            "reports",
        )
        os.makedirs(artifacts_dir, exist_ok=True)

        # ===== ACTUAL PDF GENERATION =====
        # If we have FixationResult but no Scenario with cashflow, get any scenario or create default
        if scenario is None:
            # Try to get any scenario for this client
            scenario = (
                db.query(Scenario)
                .filter(Scenario.client_id == client_id)
                .order_by(Scenario.created_at.desc())
                .first()
            )
            if scenario:
                logger.info(
                    "📄 Using existing scenario %s for report (no cashflow but has FixationResult)",
                    scenario.id,
                )
            else:
                # Create a minimal default scenario for the report
                scenario = Scenario(
                    client_id=client_id,
                    scenario_name="תרחיש ברירת מחדל לדוח",
                    parameters=json.dumps({"source": "auto_generated_for_report"}),
                )
                db.add(scenario)
                db.commit()
                db.refresh(scenario)
                logger.info(
                    "📄 Created default scenario %s for report generation",
                    scenario.id,
                )

        # Generate PDF using the modular cashflow PDF generator
        try:
            # Choose a 12-month window starting at retirement date (data-driven).
            # If retirement date is not available, fall back to current year January.
            base_date = None
            if isinstance(retirement_date_arg, str) and retirement_date_arg.strip():
                base_date = retirement_date_arg.strip()
            elif isinstance(analysis_result, dict) and isinstance(analysis_result.get("retirement_date"), str):
                base_date = str(analysis_result.get("retirement_date")).strip()

            if base_date and len(base_date) >= 7:
                start_ym = base_date[:7]
            else:
                start_ym = f"{datetime.now().year:04d}-01"

            end_ym = _add_months(start_ym, 11)

            pdf_bytes: bytes

            if report_type == "full" and find_wkhtmltopdf():
                try:
                    pdf_bytes = generate_full_report_pdf_html(
                        db=db,
                        client_id=client_id,
                        scenario_id=scenario.id,
                        report_id=report_id,
                        artifacts_dir=Path(artifacts_dir),
                        start_ym=start_ym,
                        end_ym=end_ym,
                        include_charts=bool(include_charts),
                        analysis_result=analysis_result,
                        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                except Exception as html_error:
                    logger.warning(
                        "⚠️ Full report HTML->PDF failed, falling back to modular PDF: %s",
                        html_error,
                    )
                    pdf_bytes = b""
            else:
                pdf_bytes = b""

            if not pdf_bytes:
                pdf_request = ReportPdfRequest(
                    **{
                        "from": start_ym,
                        "to": end_ym,
                        "scenario_ids": [scenario.id],
                        "sections": {
                            "summary": True,
                            "cashflow_table": True,
                            "net_chart": bool(include_charts),
                            "scenarios_compare": False,
                        },
                    }
                )

                pdf_bytes = generate_report_pdf(
                    db=db,
                    client_id=client_id,
                    scenario_id=scenario.id,
                    request=pdf_request,
                )

            if not (isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 100):
                raise ValueError("Invalid PDF bytes generated")
            if not bytes(pdf_bytes).startswith(b"%PDF"):
                raise ValueError("Generated bytes are not a PDF")

            pdf_buffer = io.BytesIO(bytes(pdf_bytes))
        except Exception as pdf_error:
            logger.error(
                "🚨 GENERATE_FULL_REPORT: PDF generation failed for client %s: %s",
                client_id,
                pdf_error,
            )
            error_response = {
                "success": False,
                "error": True,
                "message": f"❌ שגיאה בהפקת הדוח: {str(pdf_error)}",
                "status_message": f"❌ שגיאה בהפקת הדוח. אנא בדוק את הלוגים לפרטים נוספים.",
                "client_id": client_id,
                "report_type": report_type,
                "error_details": str(pdf_error),
            }
            return json.dumps(error_response, ensure_ascii=False)

        # Save PDF to artifacts folder
        # __file__ is in app/services/llm_chat/tool_handlers/generate_full_report.py
        # Need to go up 5 levels to reach project root (retire/)
        pdf_path = os.path.join(artifacts_dir, f"{report_id}.pdf")
        
        # Get PDF content and validate it's not empty
        pdf_content = pdf_buffer.getvalue()
        if not pdf_content or len(pdf_content) < 100:
            logger.error(
                "🚨 GENERATE_FULL_REPORT: PDF buffer is empty or too small (%d bytes) for client %s",
                len(pdf_content) if pdf_content else 0,
                client_id,
            )
            error_response = {
                "success": False,
                "error": True,
                "message": "❌ שגיאה בהפקת הדוח: קובץ ה-PDF ריק או פגום.",
                "status_message": "❌ שגיאה בהפקת הדוח: קובץ ה-PDF ריק או פגום.",
                "client_id": client_id,
                "report_type": report_type,
                "error_details": f"PDF buffer size: {len(pdf_content) if pdf_content else 0} bytes",
            }
            return json.dumps(error_response, ensure_ascii=False)
        
        with open(pdf_path, "wb") as f:
            f.write(pdf_content)

        # Verify file was written successfully
        if not os.path.exists(pdf_path):
            logger.error(
                "🚨 GENERATE_FULL_REPORT: PDF file was not created at %s for client %s",
                pdf_path,
                client_id,
            )
            error_response = {
                "success": False,
                "error": True,
                "message": "❌ שגיאה בהפקת הדוח: הקובץ לא נשמר בהצלחה.",
                "status_message": "❌ שגיאה בהפקת הדוח: הקובץ לא נשמר בהצלחה.",
                "client_id": client_id,
                "report_type": report_type,
                "error_details": f"File not found at: {pdf_path}",
            }
            return json.dumps(error_response, ensure_ascii=False)
        
        pdf_size = os.path.getsize(pdf_path)
        if pdf_size < 100:
            logger.error(
                "🚨 GENERATE_FULL_REPORT: PDF file is too small (%d bytes) at %s for client %s",
                pdf_size,
                pdf_path,
                client_id,
            )
            error_response = {
                "success": False,
                "error": True,
                "message": "❌ שגיאה בהפקת הדוח: קובץ ה-PDF קטן מדי ועלול להיות פגום.",
                "status_message": "❌ שגיאה בהפקת הדוח: קובץ ה-PDF קטן מדי ועלול להיות פגום.",
                "client_id": client_id,
                "report_type": report_type,
                "error_details": f"File size: {pdf_size} bytes",
            }
            return json.dumps(error_response, ensure_ascii=False)
        
        logger.info("📄 PDF saved: %s (%d bytes)", pdf_path, pdf_size)

        logger.info(
            "📄 GENERATE_FULL_REPORT: client_id=%s, type=%s, charts=%s",
            client_id,
            report_type,
            include_charts,
        )

        # Build response with report details
        report_type_names = {
            "retirement_plan": "דוח תכנית פרישה",
            "tax_analysis": "דוח ניתוח מס",
            "cashflow": "דוח תזרים מזומנים",
            "full": "דוח פרישה מלא",
        }

        response = {
            "success": True,
            "message": f"✅ הדוח הופק בהצלחה! {report_type_names.get(report_type, 'דוח')} מוכן להורדה.",
            "status_message": f"✅ הדוח הופק בהצלחה! {report_type_names.get(report_type, 'דוח')} מוכן להורדה.",
            "report_id": report_id,
            "client_id": client_id,
            "client_name": client_obj.full_name,
            "report_type": report_type,
            "report_name": report_type_names.get(report_type, "דוח"),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "PDF",
            "file_size_bytes": pdf_size,
            "include_charts": include_charts,
            "analysis_performed": analysis_performed,
            "analysis_result": analysis_result,
            "download_url": f"/api/v1/reports/{report_id}/download",
            "sections_included": [],
        }

        # Add sections based on report type
        if report_type == "full" or report_type == "retirement_plan":
            response["sections_included"].extend(
                [
                    "סיכום תכנית פרישה",
                    "פירוט מקורות הכנסה",
                    "ניתוח קצבה ברוטו ונטו",
                ]
            )
        if report_type == "full" or report_type == "tax_analysis":
            response["sections_included"].extend(
                [
                    "ניתוח מס הכנסה",
                    "פטור קיבוע זכויות",
                    "המלצות אופטימיזציה",
                ]
            )
        if report_type == "full" or report_type == "cashflow":
            response["sections_included"].extend(["תזרים מזומנים שנתי", "גרף תזרים"])

        logger.info("✅ GENERATE_FULL_REPORT completed: report_id=%s", report_id)

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("GENERATE_FULL_REPORT failed: %s", e, exc_info=True)
        return f"Error: שגיאה בהפקת הדוח: {str(e)}"
