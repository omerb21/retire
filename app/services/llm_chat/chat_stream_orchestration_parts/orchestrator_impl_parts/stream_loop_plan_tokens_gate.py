import re
from datetime import date


def _compute_plan_tokens_gate(
    *,
    request,
    db,
    original_user_msg: str,
    resolved_intent,
    extract_target_net_ils,
    resolve_target_retirement_age,
    today,
    ClientModel,
    ChatIntentClass,
    is_no_tools_request,
    is_pension_commutation_request,
    is_transform_request,
    is_qa_request,
    is_max_capital_request,
):
    target_net_for_plan = extract_target_net_ils(original_user_msg or "")
    lowered_user_msg = (original_user_msg or "").lower()
    plan_tokens = re.findall(r"[א-תA-Za-z]+", lowered_user_msg)
    plan_token_pairs = set(zip(plan_tokens, plan_tokens[1:]))
    has_plan_build_token = (
        ("בנה" in plan_tokens)
        or ("צור" in plan_tokens)
        or ("תכנן" in plan_tokens)
        or ("תכנון" in plan_tokens)
    )
    has_plan_noun_token = (
        ("תכנית" in plan_tokens)
        or ("תוכנית" in plan_tokens)
        or ("מתווה" in plan_tokens)
    )
    has_plan_pension_token = ("קצבה" in plan_tokens) or ("קצבת" in plan_tokens)
    has_plan_domain_token = ("פרישה" in plan_tokens) or ("משיכה" in plan_tokens)
    has_target_plan_phrase_tokens = (
        (("קצבת", "יעד") in plan_token_pairs)
        or (("יעד", "קצבה") in plan_token_pairs)
        or (("יעד", "הכנסה") in plan_token_pairs)
    )
    has_pension_plan_phrase = any(
        token in lowered_user_msg
        for token in (
            "חשב תכנית קצבה",
            "חשב תוכנית קצבה",
            "תכנית קצבה",
            "תוכנית קצבה",
            "תכנית יעד",
            "תוכנית יעד",
            "בנה תכנית קצבה",
            "בנה תוכנית קצבה",
        )
    )
    is_plan_request_tokens = (
        has_target_plan_phrase_tokens
        or has_pension_plan_phrase
        or ((has_plan_build_token or has_plan_noun_token) and has_plan_domain_token)
        or (has_plan_noun_token and has_plan_pension_token)
    )

    birth_date_for_plan_gate = None
    try:
        if request.client_id is not None:
            client_obj_gate = (
                db.query(ClientModel)
                .filter(ClientModel.id == request.client_id)
                .first()
            )
        else:
            client_obj_gate = None
    except Exception:
        client_obj_gate = None
    try:
        birth_date_for_plan_gate = (
            getattr(client_obj_gate, "birth_date", None) if client_obj_gate else None
        )
    except Exception:
        birth_date_for_plan_gate = None
    try:
        if birth_date_for_plan_gate == date(1970, 1, 1):
            birth_date_for_plan_gate = None
    except Exception:
        birth_date_for_plan_gate = None

    inferred_ret_age_for_plan_gate, _gate_src = resolve_target_retirement_age(
        original_user_msg,
        birth_date_for_plan_gate,
        today(),
        None,
    )
    has_target_plan_keywords = any(
        token in lowered_user_msg
        for token in (
            "קצבת יעד",
            "יעד קצבה",
            "תכנית קצבה",
            "תוכנית קצבה",
            "תכנית יעד",
            "תוכנית יעד",
            "בנה תכנית קצבה",
            "בנה תוכנית קצבה",
            "חשב תכנית קצבה",
            "חשב תוכנית קצבה",
            "בנה תכנית פרישה",
            "בנה תוכנית פרישה",
            "תכנית משיכה",
            "תוכנית משיכה",
            "תכנית יעד",
            "תוכנית יעד",
            "תכנית פרישה",
            "תוכנית פרישה",
        )
    )

    wants_execute_target_plan_text = ("בצע" in lowered_user_msg) and (
        "תכנית" in lowered_user_msg
        or "תוכנית" in lowered_user_msg
        or "מתווה" in lowered_user_msg
    )
    no_tools_requested_local = (
        resolved_intent == ChatIntentClass.NO_TOOLS
    ) or is_no_tools_request(original_user_msg)
    commutation_intent_local = is_pension_commutation_request(original_user_msg)
    explicit_transform_local = is_transform_request(original_user_msg)
    is_qa_mode_local = is_qa_request(original_user_msg)
    max_capital_requested_local = is_max_capital_request(original_user_msg or "")

    return (
        target_net_for_plan,
        lowered_user_msg,
        is_plan_request_tokens,
        inferred_ret_age_for_plan_gate,
        has_target_plan_keywords,
        wants_execute_target_plan_text,
        no_tools_requested_local,
        commutation_intent_local,
        explicit_transform_local,
        is_qa_mode_local,
        max_capital_requested_local,
    )
