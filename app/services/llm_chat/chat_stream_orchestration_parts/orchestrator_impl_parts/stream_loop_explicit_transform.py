from typing import Any

from app.services.llm_chat.chat_orchestration_helpers import (
    build_pension_portfolio_update_after_transform,
    clear_pending_approval_request,
    format_transform_result_for_user,
)
from app.services.llm_chat.orchestration_utils import (
    build_partial_pension_transform_accounts_from_portfolio,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_targeted_component_conversion_request,
)
from app.utils.llm_chat_log import log_llm_event

from ..stream_tool_execution import _execute_tool_call


def _stream_handle_explicit_transform(
    *,
    lowered_user_msg,
    original_user_msg,
    current_pension_portfolio,
    request,
    db,
    req_id: str,
    wants_capital_transform,
):
    wants_remaining_only = any(
        token in (lowered_user_msg or "")
        for token in (
            "שנותר",
            "שנשאר",
            "מה שנשאר",
            "remaining",
            "left",
        )
    )
    partial_req = parse_partial_pension_conversion_request(original_user_msg)
    if partial_req is not None:
        acc_num, amount = partial_req
        partial_accounts = build_partial_pension_transform_accounts_from_portfolio(
            pension_portfolio=current_pension_portfolio,
            account_number=acc_num,
            amount=amount,
        )
        if not partial_accounts:
            yield (
                f"לא הצלחתי למצוא חשבון מספר {acc_num} בתיק כדי לבצע המרה חלקית. "
                "אנא ודא שמספר החשבון נכון ושיש סנאפשוט תיק מעודכן."
            )
            return
        tool_args: dict[str, Any] = {
            "accounts": partial_accounts,
            "use_provided_accounts_only": True,
        }
    else:
        targeted_req = parse_targeted_component_conversion_request(original_user_msg)
        if targeted_req is not None:
            acc_num, fields, conv_type = targeted_req
            targeted_accounts = (
                build_targeted_component_transform_accounts_from_portfolio(
                    pension_portfolio=current_pension_portfolio,
                    account_number=acc_num,
                    fields=fields,
                    conversion_type=conv_type,
                )
            )
            if not targeted_accounts:
                yield (
                    f"לא הצלחתי למצוא רכיבים מתאימים בחשבון מספר {acc_num} כדי לבצע המרה ממוקדת. "
                    "אנא ודא שמספר החשבון נכון ושיש רכיב רלוונטי בתיק."
                )
                return
            tool_args = {
                "accounts": targeted_accounts,
                "use_provided_accounts_only": True,
            }
        else:
            prev_sev_req = (
                parse_portfolio_wide_prev_employers_severance_conversion_request(
                    original_user_msg
                )
            )
            if prev_sev_req is not None:
                fields, conv_type = prev_sev_req
                if conv_type == "blocked":
                    yield (
                        "מצאתי בקשה ל'פיצויים מעסיקים קודמים (רצף זכויות)', אך רכיב זה חסום להמרה במערכת "
                        "ודורש טיפול חיצוני/התחשבנות. אם תרצה, אוכל להציג באילו חשבונות הוא מופיע."
                    )
                    return
                portfolio_accounts = build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
                    pension_portfolio=current_pension_portfolio,
                    conversion_type=conv_type,
                )
                if not portfolio_accounts:
                    yield "לא מצאתי בתיק רכיב 'פיצויים מעסיקים קודמים (רצף קצבה)' להמרה."
                    return
                tool_args = {
                    "accounts": portfolio_accounts,
                    "use_provided_accounts_only": True,
                }
            else:
                after_settle_req = (
                    parse_portfolio_wide_after_settlement_severance_conversion_request(
                        original_user_msg
                    )
                )
                if after_settle_req is not None:
                    fields, conv_type = after_settle_req
                    portfolio_accounts = build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        conversion_type=conv_type,
                    )
                    if not portfolio_accounts:
                        yield "לא מצאתי בתיק רכיב 'פיצויים לאחר התחשבנות' להמרה."
                        return
                    tool_args = {
                        "accounts": portfolio_accounts,
                        "use_provided_accounts_only": True,
                    }
                else:
                    portfolio_wide_req = (
                        parse_portfolio_wide_component_conversion_request(
                            original_user_msg
                        )
                    )
                    if portfolio_wide_req is not None:
                        fields, conv_type = portfolio_wide_req
                        portfolio_accounts = build_portfolio_wide_component_transform_accounts_from_portfolio(
                            pension_portfolio=current_pension_portfolio,
                            fields=fields,
                            conversion_type=conv_type,
                        )
                        if not portfolio_accounts:
                            yield (
                                "לא מצאתי בתיק רכיבי 'תגמולים אחרי 2000' להמרה. "
                                "אם אתה מתכוון לרכיבים אחרים, ציין במפורש אילו רכיבים להמיר."
                            )
                            return
                        tool_args = {
                            "accounts": portfolio_accounts,
                            "use_provided_accounts_only": True,
                        }
                    else:
                        edu_req = (
                            parse_portfolio_wide_education_fund_conversion_request(
                                original_user_msg
                            )
                        )
                        if edu_req is not None:
                            _fields, conv_type = edu_req
                            edu_accounts = build_portfolio_wide_education_fund_transform_accounts_from_portfolio(
                                pension_portfolio=current_pension_portfolio,
                                conversion_type=conv_type,
                            )
                            if not edu_accounts:
                                yield "לא מצאתי בתיק קרנות השתלמות להמרה."
                                return
                            tool_args = {
                                "accounts": edu_accounts,
                                "use_provided_accounts_only": True,
                            }
                        else:
                            derived_accounts = build_transform_accounts_from_portfolio(
                                current_pension_portfolio
                            )
                            if not derived_accounts:
                                yield (
                                    "לא ניתן לבצע המרה כי אין תיק מסלקה/סנאפשוט זמין במערכת (pension_portfolio_snapshot ריק). "
                                    "כדי לבצע המרה מלאה צריך קודם לטעון תיק מסלקה כך שיופיע פירוט חשבונות."
                                )
                                return
                            tool_args = {
                                "accounts": derived_accounts,
                            }

    if wants_remaining_only and partial_req is None:
        tool_args["remaining_only"] = True

    if wants_capital_transform:
        yield (
            "המרה להון של רכיבים קצבתיים (למשל 'תגמולים אחרי 2000') לא מבוצעת דרך TRANSFORM_FUNDS_TO_ASSETS, "
            "כדי למנוע הפרת קצבת מינימום.\n\n"
            "אם הכוונה ל*משיכה הונית מלאה* — בקש: 'משיכה הונית מלאה' ואז אשר את תרחיש 'מקסימום הון' "
            "(ששומר קצבת מינימום 5,500).\n"
            "אם הכוונה ל*היוון קצבה ספציפית* — בקש: 'הוון קצבה' וציין מספר חשבון/שם קצבה."
        )
        return

    log_llm_event(
        request_id=req_id,
        event_type="tool_call",
        payload={"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    tool_result = _execute_tool_call(
        "TRANSFORM_FUNDS_TO_ASSETS",
        tool_args,
        request.client_id,
        db,
        pension_portfolio=current_pension_portfolio,
        force_max_exemption=False,
        request_id=req_id,
    )

    try:
        clear_pending_approval_request(db=db, client_id=request.client_id)
    except Exception:
        pass

    log_llm_event(
        request_id=req_id,
        event_type="tool_result",
        payload={"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "result": tool_result},
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    portfolio_update_marker = build_pension_portfolio_update_after_transform(
        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
        tool_result=tool_result,
        tool_args=tool_args,
        current_pension_portfolio=current_pension_portfolio,
    )

    if isinstance(portfolio_update_marker, str) and portfolio_update_marker.strip():
        yield portfolio_update_marker

    yield format_transform_result_for_user(tool_result=tool_result)
    return
