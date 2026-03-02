from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.simulation_engine.adapter import compute_from_snapshot
from app.services.simulation_engine.guard import read_only_session
from app.services.simulation_engine.models import (
    ComparisonMode,
    ConvertedTarget,
    MonthlyCashflowItem,
    SimulationRequest,
    SimulationResult,
    SustainabilityMetrics,
    TaxBreakdown,
)
from app.services.simulation_engine.snapshot import build_client_snapshot


def run_simulation(db: Session, request: SimulationRequest) -> SimulationResult:
    """Deterministic, read-only simulation entry point.

    Stage 1 intentionally performs no persistence and returns a minimal
    deterministic payload.
    """

    with read_only_session(db):
        snapshot = build_client_snapshot(db, request.client_id)
        computed = compute_from_snapshot(snapshot, request)

        monthly_cashflow = [
            MonthlyCashflowItem(**item)
            for item in (computed.get("monthly_cashflow") or [])
        ]
        monthly_cashflow.sort(key=lambda x: x.month)

        converted_targets = [
            ConvertedTarget(**t) for t in (computed.get("converted_targets") or [])
        ]
        converted_targets.sort(key=lambda x: x.target_id)

        tax_breakdown = TaxBreakdown(**(computed.get("tax_breakdown") or {}))
        sustainability_metrics = SustainabilityMetrics(
            **(computed.get("sustainability_metrics") or {})
        )
        exempt_pension_component = computed.get("exempt_pension_component") or {}
        raw_calculation_map = computed.get("raw_calculation_map") or {}

        return SimulationResult(
            converted_targets=converted_targets,
            monthly_cashflow=monthly_cashflow,
            tax_breakdown=tax_breakdown,
            exempt_pension_component=exempt_pension_component,
            sustainability_metrics=sustainability_metrics,
            raw_calculation_map=raw_calculation_map,
        )
