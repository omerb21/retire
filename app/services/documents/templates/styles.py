"""
סגנונות CSS לתבניות HTML
"""


def get_base_styles() -> str:
    """
    מחזיר סגנונות CSS בסיסיים לכל המסמכים
    
    Returns:
        מחרוזת CSS
    """
    return """
        body {
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
        }
        h1 {
            text-align: center;
            color: #2c3e50;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }
        th {
            background-color: #3498db;
            color: white;
        }
        .total-row {
            background-color: #ecf0f1;
            font-weight: bold;
        }
        .client-info {
            margin-bottom: 20px;
        }
        .highlight-row {
            background-color: #d5f4e6;
            font-weight: bold;
        }
    """


def get_grants_styles() -> str:
    """סגנונות ספציפיים לנספח מענקים"""
    return get_base_styles() + """
        th {
            background-color: #3498db;
        }
    """


def get_commutations_styles() -> str:
    """סגנונות ספציפיים לנספח היוונים"""
    return get_base_styles() + """
        th {
            background-color: #e74c3c;
        }
    """


def get_summary_styles() -> str:
    """סגנונות ספציפיים לטבלת סיכום"""
    return get_base_styles() + """
        th {
            background-color: #27ae60;
            font-weight: bold;
        }
        .section-header {
            background-color: #95a5a6;
            color: white;
            font-weight: bold;
            text-align: center;
        }
    """
