"""
סגנונות CSS לתבניות HTML
"""


def get_fixation_styles() -> str:
    """
    מחזיר סגנונות CSS לטופס קיבוע זכויות
    
    Returns:
        מחרוזת CSS
    """
    return """
        body {
            font-family: Arial, sans-serif;
            direction: rtl;
            padding: 20px;
            background-color: white;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #28a745;
            padding-bottom: 20px;
        }
        h1 {
            color: #28a745;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .client-info {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .client-info p {
            margin: 5px 0;
            font-size: 14px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: right;
        }
        th {
            background-color: #28a745;
            color: white;
            font-weight: bold;
        }
        .summary-table td:first-child {
            font-weight: 500;
            background-color: #f8f9fa;
        }
        .summary-table td:last-child {
            font-family: monospace;
            text-align: left;
        }
        .highlight-row {
            background-color: #d4edda !important;
        }
        .highlight-row td {
            font-weight: bold;
            font-size: 16px;
        }
        .secondary-row {
            background-color: #f8f9fa;
        }
        .secondary-row td {
            color: #6c757d;
        }
        .green-text {
            color: #28a745;
            font-weight: bold;
        }
        .footer {
            margin-top: 30px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #ddd;
            padding-top: 15px;
        }
    """
