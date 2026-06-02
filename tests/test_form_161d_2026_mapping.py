from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pdf_filler
from app.services.documents.generators.form_161d_generator import (
    _build_form_161d_field_data,
)
from app.services.documents.data_fetchers.fixation_data import (
    _merge_grants_with_db_rows,
)
from app.services.documents.utils.paths import TEMPLATE_161D
from pypdf import PdfReader


def test_form_161d_2026_field_mapping_uses_existing_fixation_sources() -> None:
    client = SimpleNamespace(
        first_name="Dana",
        last_name="Cohen",
        id_number="123456789",
        address_street="Herzl 1",
        address_city="Tel Aviv",
        birth_date=date(1960, 1, 2),
        phone="0501234567",
        email="dana@example.com",
    )
    fixation_data = SimpleNamespace(
        exemption_summary={
            "total_commutations": 120000,
            "future_grant_reserved": 50000,
        },
        raw_result={
            "eligibility_date": "2026-01-01",
            "grants": [
                {
                    "employer_name": "Old Employer",
                    "work_start_date": "1990-01-01",
                    "work_end_date": "2020-12-31",
                    "limited_indexed_amount": 70000,
                },
                {
                    "employer_name": "Excluded But Listed Employer",
                    "work_start_date": "1980-01-01",
                    "work_end_date": "1985-12-31",
                    "limited_indexed_amount": 40000,
                    "exclusion_reason": "outside_32_year_window",
                },
                {
                    "employer_name": "מענק פיצויים פטור - מעסיק נוכחי",
                    "work_start_date": "2021-01-01",
                    "work_end_date": "2026-01-01",
                    "limited_indexed_amount": 12000,
                },
                {
                    "employer_name": "No Exempt Grant Employer",
                    "work_start_date": "1975-01-01",
                    "work_end_date": "1979-12-31",
                    "limited_indexed_amount": 0,
                    "grant_amount": 0,
                },
            ],
            "current_employer_snapshot": {
                "continues_working": True,
                "employer_name": "Current Employer",
                "work_start_date": "2021-01-01",
                "work_end_date": "2026-01-01",
                "last_salary": 24000,
            },
        },
        raw_payload={
            "form_161d": {
                "additional_exemption_allocation": "pension",
                "form_161h_submitted": False,
                "future_commutation_amount": 33000,
                "request_current_commutation_approval": True,
            },
        },
        eligibility_date="2026-01-01",
    )
    pensions = [
        SimpleNamespace(
            fund_name="Pension Payer",
            pension_amount=9000,
            pension_start_date=date(2026, 2, 1),
            record_status="active",
        )
    ]
    commutations = [
        SimpleNamespace(
            asset_name="Capital Payer",
            description="",
            current_value=120000,
            start_date=date(2026, 3, 1),
            remarks="COMMUTATION:pension_fund_id=1;amount=120000",
        )
    ]

    fields = _build_form_161d_field_data(
        client=client,
        fixation_data=fixation_data,
        pensions=pensions,
        commutations=commutations,
    )

    assert fields["ClientEmail"] == "dana@example.com"
    assert fields["Kitzbapayer1"] == "Pension Payer"
    assert fields["Kitzbasum1"] == "9,000"
    assert fields["pastemply1"] == "Old Employer"
    assert fields["pastemplysum1"] == "70,000"
    assert fields["pastemply2"] == "Excluded But Listed Employer"
    assert fields["pastemplysum2"] == "40,000"
    assert fields["pastemply3"] == "No Exempt Grant Employer"
    assert fields["pastemply1sum3"] == ""
    assert fields["Clientemployer"] == "Current Employer"
    assert fields["clientcapsum"] == "120,000"
    assert fields["futurecapital"] == "33,000"
    assert fields["capitalpayer"] == "Capital Payer"
    assert fields["Check Box3"] is True
    assert fields["Check Box5"] is True
    assert fields["Check Box7"] is True
    assert fields["Check Box8"] is True


def test_pdf_filler_sets_checkbox_appearance(tmp_path: Path) -> None:
    output_path = tmp_path / "filled_161d.pdf"
    pdf_filler.fill_acroform(TEMPLATE_161D, output_path, {"Check Box8": True})

    reader = PdfReader(str(output_path))
    found = False
    for page in reader.pages:
        for annot_ref in page.get("/Annots") or []:
            annot = annot_ref.get_object()
            if annot.get("/T") == "Check Box8":
                found = True
                assert annot.get("/V") == "/Yes"
                assert annot.get("/AS") == "/Yes"
    assert found


def test_form_161d_2026_section_d_uses_actual_commutation_assets() -> None:
    client = SimpleNamespace(
        first_name="Dana",
        last_name="Cohen",
        id_number="123456789",
        address_street="",
        address_city="",
        birth_date=None,
        phone="",
        email="",
    )
    fixation_data = SimpleNamespace(
        exemption_summary={
            "total_commutations": 0,
            "future_grant_reserved": 0,
        },
        raw_payload={},
        raw_result={
            "grants": [],
            "current_employer_snapshot": {},
        },
        eligibility_date="2026-01-01",
    )
    commutations = [
        SimpleNamespace(
            asset_name=None,
            description="היוון קרן א",
            current_value=0,
            start_date=date(2026, 1, 1),
            tax_treatment="taxable",
            remarks="COMMUTATION:pension_fund_id=4&amount=23946.75",
        ),
        SimpleNamespace(
            asset_name=None,
            description="היוון קרן ב",
            current_value=0,
            start_date=date(2026, 1, 1),
            tax_treatment="taxable",
            remarks="COMMUTATION:pension_fund_id=5&amount=7874.02",
        ),
    ]

    fields = _build_form_161d_field_data(
        client=client,
        fixation_data=fixation_data,
        pensions=[],
        commutations=commutations,
    )

    assert fields["clientcapsum"] == "31,821"
    assert fields["futurecapital"] == "31,821"
    assert fields["capitalsum"] == "31,821"
    assert fields["capitalpayer"] == "היוון קרן א ; היוון קרן ב"
    assert fields["Check Box7"] is True
    assert fields["Check Box8"] is True


def test_document_fixation_data_appends_zero_amount_db_grants() -> None:
    raw_grants = [
        {
            "employer_name": "Old Employer",
            "work_start_date": "2010-01-01",
            "work_end_date": "2015-12-31",
            "grant_date": "2015-12-31",
            "grant_amount": 50000,
            "limited_indexed_amount": 50000,
            "impact_on_exemption": 67500,
        }
    ]
    db_grants = [
        SimpleNamespace(
            employer_name="Old Employer",
            work_start_date=date(2010, 1, 1),
            work_end_date=date(2015, 12, 31),
            grant_date=date(2015, 12, 31),
            grant_amount=50000,
            grant_indexed_amount=50000,
            grant_ratio=1,
            limited_indexed_amount=50000,
            impact_on_exemption=67500,
        ),
        SimpleNamespace(
            employer_name="No Exempt Grant Employer",
            work_start_date=date(2016, 1, 1),
            work_end_date=date(2020, 12, 31),
            grant_date=date(2020, 12, 31),
            grant_amount=0,
            grant_indexed_amount=None,
            grant_ratio=None,
            limited_indexed_amount=None,
            impact_on_exemption=None,
        ),
    ]

    merged = _merge_grants_with_db_rows(raw_grants, db_grants)

    assert len(merged) == 2
    assert merged[1]["employer_name"] == "No Exempt Grant Employer"
    assert merged[1]["grant_amount"] == 0
    assert merged[1]["limited_indexed_amount"] == 0
    assert merged[1]["impact_on_exemption"] == 0
