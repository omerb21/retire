import json


def generate_commutation_need_account(*, computed_data) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
    yield (
        "כדי לחשב היוון בצורה נכונה אני צריך לזהות *איזו קצבה* אתה רוצה להוון. "
        "בבקשה ציין אחד מהבאים:\n"
        "1) מספר חשבון/תיק ניכויים של הקצבה (5+ ספרות)\n"
        "2) שם הקצבה כפי שמופיע במסך הקצבאות\n\n"
        "בנוסף: האם הכוונה היא ל*סכום חד-פעמי* שתרצה לקבל, או ל*הפחתה חודשית מהקצבה*?"
    )


def generate_commutation_need_amount_existing(*, computed_data) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
    yield (
        "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
        "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
    )


def generate_commutation_need_amount(*, computed_data) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
    yield (
        "מצאתי את הקצבה המתאימה, אבל חסר לי סכום היוון. "
        "כתוב סכום (למשל 50000 ₪) או 'כל היתרה'."
    )


def generate_commutation_missing(*, computed_data, account_number) -> str:
    if computed_data is not None:
        computed_json = json.dumps(
            {"type": "computed_data", "data": computed_data.model_dump()},
            ensure_ascii=False,
        )
        yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

    yield (
        "כדי לבצע היוון אני צריך לזהות **קצבה קיימת במערכת** שמתאימה לחשבון שביקשת. "
        f"לא מצאתי קצבה עם מספר חשבון/תיק ניכויים `{account_number}`.\n\n"
        "אפשרויות:\n"
        "1) כתוב את שם הקצבה כפי שהיא מופיעה במסך קצבאות, או את מזהה הקצבה (pension_fund_id).\n"
        "2) אם הכוונה היא לתכנית בתיק המסלקה בלבד (לא קצבה קיימת), ציין: 'הפוך את החשבון לקצבה ואז בצע היוון'."
    )
