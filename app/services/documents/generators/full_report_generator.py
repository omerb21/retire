from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.scenario import Scenario
from app.services.case_service import detect_case
from app.services.cashflow_service import generate_cashflow
from app.services.documents.converters import html_to_pdf
from app.services.documents.data_fetchers import (
    fetch_client_data,
    fetch_commutations_data,
    fetch_fixation_data,
    fetch_grants_data,
    fetch_pension_data,
)
from app.services.documents.templates.full_report_styles import get_full_report_styles
from app.services.documents.templates.full_report_template import FullReportHTMLTemplate


def _calc_yearly_totals(
    cashflow_rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    yearly_totals: Dict[str, Dict[str, float]] = {}

    for row in cashflow_rows:
        d = row.get("date")
        year = str(d)[:4] if d else None
        if not year:
            continue

        if year not in yearly_totals:
            yearly_totals[year] = {
                "inflow": 0.0,
                "outflow": 0.0,
                "additional_income_net": 0.0,
                "capital_return_net": 0.0,
                "net": 0.0,
            }

        yearly_totals[year]["inflow"] += float(row.get("inflow", 0) or 0)
        yearly_totals[year]["outflow"] += float(row.get("outflow", 0) or 0)
        yearly_totals[year]["additional_income_net"] += float(
            row.get("additional_income_net", 0) or 0
        )
        yearly_totals[year]["capital_return_net"] += float(
            row.get("capital_return_net", 0) or 0
        )
        yearly_totals[year]["net"] += float(row.get("net", 0) or 0)

    return yearly_totals


def generate_full_report_pdf(
    *,
    db: Session,
    client_id: int,
    scenario_id: int,
    report_id: str,
    artifacts_dir: Path,
    start_ym: str,
    end_ym: str,
    include_charts: bool,
    analysis_result: Optional[dict],
    generated_at: str,
) -> bytes:
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    client = fetch_client_data(db, client_id)
    if not client:
        raise ValueError(f"Client {client_id} not found")

    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    try:
        case_detection = detect_case(db, client_id)
        case_id = case_detection.case_id
    except Exception:
        case_id = 1

    cashflow_rows = generate_cashflow(
        db=db,
        client_id=client_id,
        scenario_id=scenario_id,
        start_ym=start_ym,
        end_ym=end_ym,
        case_id=case_id,
    )

    yearly_totals = _calc_yearly_totals(cashflow_rows)

    fixation_data = fetch_fixation_data(db, client_id)
    pension_funds = fetch_pension_data(db, client_id)
    grants_dates_map = fetch_grants_data(db, client_id)
    commutations = fetch_commutations_data(db, client_id)

    additional_incomes = (
        db.query(AdditionalIncome)
        .filter(AdditionalIncome.client_id == client_id)
        .order_by(AdditionalIncome.start_date.asc())
        .all()
    )

    capital_assets_all = (
        db.query(CapitalAsset)
        .filter(CapitalAsset.client_id == client_id)
        .order_by(CapitalAsset.start_date.asc())
        .all()
    )

    commutation_ids = {getattr(c, "id", None) for c in commutations}
    capital_assets = [
        a for a in capital_assets_all if getattr(a, "id", None) not in commutation_ids
    ]

    css_filename = f"{report_id}.css"
    html_filename = f"{report_id}.html"

    css_path = artifacts_dir / css_filename
    html_path = artifacts_dir / html_filename
    pdf_path = artifacts_dir / f"{report_id}.pdf"

    css_path.write_text(get_full_report_styles(), encoding="utf-8")

    template = FullReportHTMLTemplate(
        client=client,
        report_title="דוח פרישה מלא",
        date_range=f"{start_ym} - {end_ym}",
        generated_at=generated_at,
        analysis_result=analysis_result,
        fixation_data=fixation_data,
        pension_funds=pension_funds,
        additional_incomes=additional_incomes,
        capital_assets=capital_assets,
        commutations=commutations,
        grants_dates_map=grants_dates_map,
        yearly_totals=yearly_totals,
        cashflow_rows=cashflow_rows,
        include_charts=include_charts,
        css_filename=css_filename,
    )

    html_path.write_text(template.render(), encoding="utf-8")

    html_to_pdf(html_path, pdf_path)

    pdf_bytes = pdf_path.read_bytes()
    if not (
        isinstance(pdf_bytes, (bytes, bytearray))
        and len(pdf_bytes) > 100
        and bytes(pdf_bytes).startswith(b"%PDF")
    ):
        raise ValueError("Invalid PDF produced by HTML-to-PDF")

    return bytes(pdf_bytes)
