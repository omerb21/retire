from pydantic import BaseModel, Field
from typing import List, Optional

class FixationSingleResponse(BaseModel):
    success: bool = Field(True)
    message: str
    file_path: str
    client_id: int
    client_name: Optional[str] = None

class FixationPackageResponse(BaseModel):
    success: bool = Field(True)
    message: str
    files: List[str]
    client_id: int
    client_name: Optional[str] = None

