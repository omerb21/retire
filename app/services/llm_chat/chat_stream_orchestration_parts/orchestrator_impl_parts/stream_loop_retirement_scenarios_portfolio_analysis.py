def _maybe_prepare_retirement_scenarios_args_for_portfolio_analysis(
    *,
    tool_name,
    tool_args,
    is_portfolio_analysis,
    analysis_default_retirement_age,
):
    if tool_name == "RUN_RETIREMENT_SCENARIOS" and is_portfolio_analysis:
        if not isinstance(tool_args, dict):
            tool_args = {}
        if analysis_default_retirement_age is not None:
            tool_args["retirement_age"] = analysis_default_retirement_age

    return tool_args
