"""
Schemas package initialization
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel

# Import client schemas
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientList
from app.schemas.client import ClientResponse as Client  # Alias for backward compatibility

# Import other schemas as needed
try:
    from app.schemas.employment import EmploymentCreate, EmploymentUpdate, EmploymentResponse
    from app.schemas.pension import PensionCreate, PensionUpdate, PensionResponse
    from app.schemas.grant import GrantCreate, GrantUpdate, GrantResponse
    from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioResponse
    from app.schemas.current_employer import CurrentEmployerCreate, CurrentEmployerUpdate, CurrentEmployerResponse
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
