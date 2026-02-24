from app.services.llm_chat.orchestration_utils import (
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_targeted_component_conversion_request,
)


def _maybe_override_transform_tool_args_accounts(
    *,
    current_pension_portfolio,
    original_user_msg,
    tool_args,
) -> None:
    if isinstance(current_pension_portfolio, list) and current_pension_portfolio:
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
            if targeted_accounts:
                tool_args["accounts"] = targeted_accounts
                tool_args["use_provided_accounts_only"] = True
        else:
            prev_sev_req = (
                parse_portfolio_wide_prev_employers_severance_conversion_request(
                    original_user_msg
                )
            )
            if prev_sev_req is not None:
                _fields, conv_type = prev_sev_req
                if conv_type != "blocked":
                    portfolio_accounts = build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        conversion_type=conv_type,
                    )
                    if portfolio_accounts:
                        tool_args["accounts"] = portfolio_accounts
                        tool_args["use_provided_accounts_only"] = True
            else:
                after_settle_req = (
                    parse_portfolio_wide_after_settlement_severance_conversion_request(
                        original_user_msg
                    )
                )
                if after_settle_req is not None:
                    _fields, conv_type = after_settle_req
                    portfolio_accounts = build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
                        pension_portfolio=current_pension_portfolio,
                        conversion_type=conv_type,
                    )
                    if portfolio_accounts:
                        tool_args["accounts"] = portfolio_accounts
                        tool_args["use_provided_accounts_only"] = True
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
                        if portfolio_accounts:
                            tool_args["accounts"] = portfolio_accounts
                            tool_args["use_provided_accounts_only"] = True
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
                            if edu_accounts:
                                tool_args["accounts"] = edu_accounts
                                tool_args["use_provided_accounts_only"] = True
