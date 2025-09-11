from enum import Enum
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class ClientCase(str, Enum):
    """Client case types for workflow determination"""
    NO_CURRENT_EMPLOYER = "NO_CURRENT_EMPLOYER"
    SELF_EMPLOYED_ONLY = "SELF_EMPLOYED_ONLY"
    PAST_RETIREMENT_AGE = "PAST_RETIREMENT_AGE"
    ACTIVE_NO_LEAVE = "ACTIVE_NO_LEAVE"
    REGULAR_WITH_LEAVE = "REGULAR_WITH_LEAVE"
    standard = "standard"


class CaseDetectionResult(BaseModel):
    """Result of client case detection"""
    client_id: int = Field(..., description="Client ID")
    case_id: Union[int, ClientCase] = Field(..., description="Case ID (1-5) or ClientCase enum")
    case_name: str = Field(..., description="Case name")
    reasons: List[str] = Field([], description="Reasons for case detection")
    detected_at: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")

    class Config:
        schema_extra = {
            "example": {
                "client_id": 1,
                "case_id": 5,
                "case_name": "REGULAR_WITH_LEAVE",
                "reasons": ["has_current_employer", "planned_leave_detected_or_default"],
                "detected_at": "2025-09-03T12:34:56Z"
            }
        }


class CaseDetectionResponse(BaseModel):
    """API response wrapper for case detection"""
    result: CaseDetectionResult

    class Config:
        schema_extra = {
            "example": {
                "result": {
                    "client_id": 1,
                    "case_id": 5,
                    "case_name": "REGULAR_WITH_LEAVE",
                    "reasons": ["has_current_employer", "planned_leave_detected_or_default"],
                    "detected_at": "2025-09-03T13:25:00Z"
                }
            }
        }


class CaseDetectResponse(BaseModel):
    """Simple case detection response for sprint11 verification"""
    case: Optional[ClientCase] = None
