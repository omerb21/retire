"""
Schemas package initialization
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

# Import client schemas
from app.schemas.client import ClientResponse  # Alias for backward compatibility
from app.schemas.client import ClientCreate, ClientList, ClientUpdate

# Import other schemas as needed
try:
    from app.schemas.current_employer import (
        CurrentEmployerCreate,
        CurrentEmployerResponse,
        CurrentEmployerUpdate,
    )
    from app.schemas.employment import (
        EmploymentCreate,
        EmploymentResponse,
        EmploymentUpdate,
    )
    from app.schemas.grant import GrantCreate, GrantResponse, GrantUpdate
    from app.schemas.pension import PensionCreate, PensionResponse, PensionUpdate
    from app.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioUpdate
except ImportError:
    # Fallback for missing schema modules
    pass


# Common response schema
class APIResponse(BaseModel):
    """Common API response schema"""

    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


# Common error response
class ErrorResponse(BaseModel):
    """Error response schema"""

    detail: Union[str, Dict[str, Any]]
