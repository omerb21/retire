from enum import Enum


class OrchestrationPlan(str, Enum):
    CASHFLOW_ONLY = "cashflow_only"
    FIXATION_STATUS = "fixation_status"
    SYSTEM_SNAPSHOT = "system_snapshot"
    NONE = "none"
