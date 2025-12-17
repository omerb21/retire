def get_full_report_styles() -> str:
    return """
body {
    font-family: Arial, sans-serif;
    direction: rtl;
    padding: 18px;
    color: #2c3e50;
}

h1, h2 {
    color: #1f4e79;
}

h1 {
    text-align: center;
    margin-bottom: 6px;
}

.meta {
    text-align: center;
    color: #6c757d;
    font-size: 12px;
    margin-bottom: 16px;
}

.section {
    margin: 18px 0;
}

.card {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
}

th, td {
    border: 1px solid #dee2e6;
    padding: 6px 8px;
    text-align: right;
    vertical-align: top;
    font-size: 12px;
}

th {
    background-color: #1f4e79;
    color: #fff;
}

tr:nth-child(even) {
    background-color: #f8f9fa;
}

.page-break {
    page-break-before: always;
}

.small {
    font-size: 11px;
    color: #6c757d;
}

svg {
    max-width: 100%;
}
"""
