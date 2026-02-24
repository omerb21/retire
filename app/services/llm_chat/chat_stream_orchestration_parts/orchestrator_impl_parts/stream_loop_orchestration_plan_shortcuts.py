import json

from fastapi.responses import StreamingResponse


def _maybe_handle_orchestration_plan_shortcuts(
    *,
    plan,
    request,
    db,
    stream_request_id: str,
    computed_data,
    effective_portfolio,
    original_user_msg: str,
    force_max_exemption: bool,
    advice_compensation_mode: bool,
    build_recent_state_banner,
    load_latest_pension_portfolio_snapshot_models,
    generate_cashflow,
    execute_tool_call,
    sanitize_user_visible_text,
    format_system_inventory_snapshot,
    OrchestrationPlanClass,
):
    if plan == OrchestrationPlanClass.SYSTEM_SNAPSHOT and request.client_id is not None:

        def _generate_orchestration_plan_system_snapshot(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = execute_tool_call(
                "GET_SYSTEM_STATE_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )
            if isinstance(tool_result, str) and tool_result.strip().lower().startswith(
                "tool error"
            ):
                yield sanitize_user_visible_text(tool_result)
                return

            yield sanitize_user_visible_text(
                format_system_inventory_snapshot(tool_result)
            )

        return StreamingResponse(
            _generate_orchestration_plan_system_snapshot(stream_request_id),
            media_type="text/plain",
        )

    if plan == OrchestrationPlanClass.FIXATION_STATUS and request.client_id is not None:

        def _generate_orchestration_plan_fixation_status(req_id: str):
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

            tool_result = execute_tool_call(
                "GET_FIXATION_STATUS_SNAPSHOT",
                {},
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            yield (
                "🔧 **פלט כלי (סטטוס קיבוע זכויות):**\n"
                + sanitize_user_visible_text(tool_result)
                + "\n\n"
            )

            try:
                parsed = json.loads(tool_result) if isinstance(tool_result, str) else {}
            except Exception:
                parsed = {}

            has_prior_fixation = str(parsed.get("has_prior_fixation") or "unknown")
            has_161 = str(parsed.get("has_161") or "unknown")
            has_161d = str(parsed.get("has_161d") or "unknown")
            has_commutation = str(parsed.get("has_commutation") or "unknown")
            has_exempt_grants = str(parsed.get("has_exempt_grants") or "unknown")
            employment_ended = str(parsed.get("employment_ended") or "unknown")
            missing_inputs = (
                parsed.get("missing_inputs")
                if isinstance(parsed.get("missing_inputs"), list)
                else []
            )

            def _yn(value: str) -> str:
                v = (value or "").strip().lower()
                if v == "yes":
                    return "כן"
                if v == "no":
                    return "לא"
                return "לא ידוע"

            yield (
                "כותרת: סטטוס קיבוע זכויות במערכת\n\n"
                "מה נמצא:\n"
                f"- קיבוע קודם: {_yn(has_prior_fixation)}\n"
                f"- טופס 161: {_yn(has_161)}\n"
                f"- טופס 161ד: {_yn(has_161d)}\n"
                f"- היוונים: {_yn(has_commutation)}\n"
                f"- מענקים פטורים: {_yn(has_exempt_grants)}\n"
                f"- סטטוס סיום עבודה: {_yn(employment_ended)}\n\n"
                "מה חסר:\n"
            )

            if missing_inputs:
                for item in missing_inputs:
                    if isinstance(item, str) and item.strip():
                        yield f"- {item.strip()}\n"
            else:
                yield "- לא זוהה חוסר נתונים ספציפי\n"

            yield "\nפעולה הבאה במערכת:\n- להשלים את החוסרים ואז להריץ קיבוע/מסמכים בהתאם."

        return StreamingResponse(
            _generate_orchestration_plan_fixation_status(stream_request_id),
            media_type="text/plain",
        )

    if plan == OrchestrationPlanClass.CASHFLOW_ONLY and request.client_id is not None:

        def _generate_orchestration_plan_cashflow(req_id: str):
            banner = build_recent_state_banner()
            if banner:
                yield banner + "\n\n"

            portfolio_for_cashflow = effective_portfolio

            try:
                loaded = load_latest_pension_portfolio_snapshot_models(
                    db, request.client_id
                )
                if loaded is not None:
                    portfolio_for_cashflow, _snapshot_at = loaded
            except Exception:
                pass

            yield from generate_cashflow(
                computed_data=None,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=portfolio_for_cashflow,
                force_max_exemption=force_max_exemption,
                stream_request_id=req_id,
            )

            if advice_compensation_mode:
                yield (
                    "\n\n"
                    + "כותרת: סיכום החלטה לגבי פיצויים\n\n"
                    + "מה בדקתי במערכת:\n"
                    + "- תזרים\n"
                    + "- מס\n"
                    + "- יתרות\n"
                    + "- סטטוסים (כולל חסומים) ואירוע סיום עבודה\n\n"
                    + "מה המשמעות של שתי אפשרויות עיקריות:\n"
                    + "- מימוש כהון: שינוי באופי המימוש והנזילות; עשוי להשפיע על רכיבי המס והיתרות שנצפות בדוחות\n"
                    + "- השארה כהמשך קצבתי/אחר: המשך צבירה/תשלום במבנה קצבתי בהתאם להגדרות הקופות והסטטוסים במערכת\n\n"
                    + "מה חסר כדי לתת המלצה סופית (אם חסר):\n"
                    + "- בחירת יעד (נזילות מול קצבה)\n"
                    + "- סטטוס תהליך סיום עבודה ומסמכים נלווים\n"
                    + "- אישור שהנתונים במערכת עדכניים לכל הגופים\n\n"
                    + "פעולה הבאה במערכת:\n"
                    + "- להפיק דוח מסכם מהמערכת כדי לקבל מסמך תומך החלטה על בסיס הנתונים והחישובים שבוצעו\n"
                )

        return StreamingResponse(
            _generate_orchestration_plan_cashflow(stream_request_id),
            media_type="text/plain",
        )

    return None
