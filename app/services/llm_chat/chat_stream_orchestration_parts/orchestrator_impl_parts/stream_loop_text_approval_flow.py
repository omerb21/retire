import json

from fastapi.responses import StreamingResponse


def _has_positive_component_amounts(raw: object) -> bool:
    if not isinstance(raw, dict) or not raw:
        return False
    for _k, v in raw.items():
        try:
            if float(v or 0) > 0:
                return True
        except Exception:
            continue
    return False


def _accounts_are_thin(accounts: object) -> bool:
    if not isinstance(accounts, list) or not accounts:
        return False

    def _get_account_number(acc: dict) -> str:
        return str(
            acc.get("account_number")
            or acc.get("מספר_חשבון")
            or acc.get("מספר חשבון")
            or acc.get("מספר-חשבון")
            or ""
        ).strip()

    for acc in accounts:
        if not isinstance(acc, dict):
            continue

        account_number = _get_account_number(acc)
        if not account_number:
            continue
        raw_balance = acc.get("balance")
        if raw_balance is None:
            raw_balance = acc.get("יתרה")
        if raw_balance is None:
            raw_balance = acc.get("current_balance")

        try:
            if float(raw_balance or 0) > 0:
                continue
        except Exception:
            pass

        if _has_positive_component_amounts(acc.get("specific_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_components")):
            continue

        return True

    return False


def _maybe_handle_text_approval_flow(
    *,
    request,
    db,
    stream_request_id: str,
    lowered_user_msg: str,
    ScenarioModel,
    load_latest_pension_portfolio_snapshot_models,
    execute_tool_call,
    clear_pending_approval_request,
    get_tool_display_name_hebrew,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    coerce_float_safe,
    compute_existing_income_offset_monthly,
    store_latest_target_pension_plan_data,
    store_latest_target_pension_plan,
):
    if request.client_id is None:
        return None

    try:
        from app.services.llm_chat.message_utils import is_user_approval_intent_text
    except Exception:
        is_user_approval_intent_text = None

    def _has_pending_approval() -> bool:
        try:
            row = (
                db.query(ScenarioModel)
                .filter(ScenarioModel.client_id == request.client_id)
                .filter(ScenarioModel.scenario_name == "pending_approval")
                .order_by(ScenarioModel.created_at.desc())
                .first()
            )
            return row is not None
        except Exception:
            return False

    if lowered_user_msg in {"אוקי", "אוקיי", "הבנתי", "בסדר", "סבבה"} and (
        not _has_pending_approval()
    ):
        return StreamingResponse(
            iter(["קיבלתי."]),
            media_type="text/plain",
        )

    if callable(is_user_approval_intent_text):
        if not is_user_approval_intent_text(lowered_user_msg):
            return None
    elif lowered_user_msg not in {"מאשר", "אשר", "כן", "approve", "ok"}:
        return None

    def _load_latest_pending_approval_payload() -> tuple[str, dict] | None:
        try:
            row = (
                db.query(ScenarioModel)
                .filter(ScenarioModel.client_id == request.client_id)
                .filter(ScenarioModel.scenario_name == "pending_approval")
                .order_by(ScenarioModel.created_at.desc())
                .first()
            )
        except Exception:
            row = None
        if row is None or not getattr(row, "parameters", None):
            return None
        try:
            parsed = json.loads(row.parameters)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        tool_name = parsed.get("tool_name")
        tool_args = parsed.get("arguments")
        if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
            return None
        return tool_name, tool_args

    pending = _load_latest_pending_approval_payload()
    if pending is None:
        return StreamingResponse(
            iter(["לא נמצאה בקשת אישור פעילה."]),
            media_type="text/plain",
        )

    approved_tool, approved_args = pending

    def _append_transform_hint_if_needed(
        *, tool_name: str, rendered_output: str
    ) -> str:
        if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
            return rendered_output
        try:
            parsed = json.loads(rendered_output)
        except Exception:
            parsed = None
        if not (isinstance(parsed, dict) and parsed.get("success") is True):
            return rendered_output
        if "השלב הבא המומלץ: הפקת דוח" in rendered_output:
            return rendered_output
        return rendered_output + "\n\nהשלב הבא המומלץ: הפקת דוח"

    def _generate_text_approved_exec(req_id: str):
        try:
            effective_portfolio = request.pension_portfolio
            try:
                loaded = load_latest_pension_portfolio_snapshot_models(
                    db, request.client_id
                )
                if loaded is not None:
                    effective_portfolio, _snapshot_at = loaded
            except Exception:
                pass

            if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS" and isinstance(
                approved_args, dict
            ):
                try:
                    accounts = approved_args.get("accounts")
                    if _accounts_are_thin(accounts):
                        approved_args["use_provided_accounts_only"] = False
                except Exception:
                    pass

            tool_result = execute_tool_call(
                approved_tool,
                approved_args,
                request.client_id,
                db,
                pension_portfolio=effective_portfolio,
                force_max_exemption=False,
                user_approved=True,
                request_id=req_id,
            )

            if approved_tool == "TRANSFORM_FUNDS_TO_ASSETS" and isinstance(
                approved_args, dict
            ):
                try:
                    parsed = json.loads(tool_result)
                except Exception:
                    parsed = None

                should_retry = False
                if isinstance(parsed, dict) and parsed.get("success") is True:
                    try:
                        total_converted = int(parsed.get("total_converted") or 0)
                    except Exception:
                        total_converted = 0
                    try:
                        skipped_zero_balance = int(
                            parsed.get("skipped_zero_balance") or 0
                        )
                    except Exception:
                        skipped_zero_balance = 0

                    if (
                        total_converted == 0
                        and skipped_zero_balance > 0
                        and bool(approved_args.get("use_provided_accounts_only"))
                        is True
                    ):
                        should_retry = True

                if should_retry:
                    approved_args["use_provided_accounts_only"] = False
                    yield "\n\n" + "לא נטענו נתוני חשבון מלאים, מנסה לטעון מה־DB."
                    tool_result = execute_tool_call(
                        approved_tool,
                        approved_args,
                        request.client_id,
                        db,
                        pension_portfolio=effective_portfolio,
                        force_max_exemption=False,
                        user_approved=True,
                        request_id=req_id,
                    )
        finally:
            try:
                clear_pending_approval_request(db=db, client_id=request.client_id)
            except Exception:
                pass

        tool_display = get_tool_display_name_hebrew(approved_tool)
        user_tool_output = format_tool_output_for_user_stream(
            approved_tool, tool_result
        )
        rendered = f"🔧 **פלט כלי ({tool_display}):**\n" + sanitize_user_visible_text(
            user_tool_output
        )
        yield _append_transform_hint_if_needed(
            tool_name=approved_tool, rendered_output=rendered
        )

    return StreamingResponse(
        _generate_text_approved_exec(stream_request_id),
        media_type="text/plain",
    )
