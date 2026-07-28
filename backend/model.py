from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    question: str

class ColumnDescription(BaseModel):
    column_name: str
    description: str = ""

class TableCreationRequest(BaseModel):
    table_name: str
    column_descriptions: List[ColumnDescription]
    prompt: Optional[str] = ""

class UploadResponse(BaseModel):
    success: bool
    message: str
    columns: List[str]
    column_info: List[Dict[str, Any]]
    preview: List[Dict[str, Any]]
    row_count: int
    table_name: str

class CreateTableResponse(BaseModel):
    success: bool
    message: str
    table_name: str
    row_count: int
    column_count: int
    column_descriptions: Dict[str, str]
    prompt: Optional[str] = ""