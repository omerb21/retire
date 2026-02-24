from fastapi.responses import StreamingResponse

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund


def _maybe_handle_system_info_requests(
    *,
    tools_enabled: bool,
    request,
    db,
    computed_data,
    effective_portfolio,
    effective_snapshot_at,
    stream_request_id: str,
    wrap_with_restore_banner,
    is_data_awareness_request,
    generate_data_awareness,
    is_list_all_financial_entities_request,
    generate_list_all_entities,
    is_portfolio_breakdown_request,
    generate_breakdown,
    is_portfolio_analysis_request,
    generate_portfolio_analysis,
    is_system_inventory_request,
    generate_system_inventory,
    is_system_results_request,
    generate_system_results,
    original_user_msg: str,
):
    if (
        tools_enabled
        and request.client_id is not None
        and is_data_awareness_request(original_user_msg)
    ):
        return StreamingResponse(
            wrap_with_restore_banner(
                generate_data_awareness(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    effective_snapshot_at=effective_snapshot_at,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain",
        )

    if (
        tools_enabled
        and request.client_id is not None
        and is_list_all_financial_entities_request(original_user_msg)
    ):
        return StreamingResponse(
            wrap_with_restore_banner(
                generate_list_all_entities(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    effective_snapshot_at=effective_snapshot_at,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain",
        )

    if tools_enabled and is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:
            return StreamingResponse(
                generate_breakdown(
                    computed_data=computed_data,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain",
            )

    if tools_enabled and is_portfolio_analysis_request(original_user_msg):
        portfolio = effective_portfolio or []
        has_portfolio = bool(portfolio)
        has_additional_incomes = False
        has_system_assets = False
        if (not has_portfolio) and request.client_id is not None:
            try:
                row = (
                    db.query(AdditionalIncome)
                    .filter(AdditionalIncome.client_id == request.client_id)
                    .first()
                )
                has_additional_incomes = row is not None
            except Exception:
                has_additional_incomes = False

            try:
                pf_row = (
                    db.query(PensionFund)
                    .filter(PensionFund.client_id == request.client_id)
                    .first()
                )
                ca_row = (
                    db.query(CapitalAsset)
                    .filter(CapitalAsset.client_id == request.client_id)
                    .first()
                )
                has_system_assets = (pf_row is not None) or (ca_row is not None)
            except Exception:
                has_system_assets = False

        if has_portfolio or has_additional_incomes or has_system_assets:
            try:
                from app.services.agent_execution.tool_executor import execute_tool_call

                if request.client_id is not None:
                    execute_tool_call(
                        tool_name="GET_SYSTEM_NUMERIC_CONSTANTS",
                        args={},
                        client_id=int(request.client_id),
                        db=db,
                        pension_portfolio=portfolio,
                        force_max_exemption=False,
                        user_approved=True,
                    )
            except Exception:
                pass
            return StreamingResponse(
                generate_portfolio_analysis(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain",
            )

    if (
        tools_enabled
        and request.client_id is not None
        and is_system_inventory_request(original_user_msg)
    ):
        return StreamingResponse(
            wrap_with_restore_banner(
                generate_system_inventory(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain",
        )

    if (
        tools_enabled
        and request.client_id is not None
        and is_system_results_request(original_user_msg)
    ):
        return StreamingResponse(
            wrap_with_restore_banner(
                generate_system_results(
                    computed_data=computed_data,
                    original_user_msg=original_user_msg,
                    request=request,
                    db=db,
                    effective_portfolio=effective_portfolio,
                    stream_request_id=stream_request_id,
                )
            ),
            media_type="text/plain",
        )

    return None
