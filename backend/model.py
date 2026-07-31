from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    question: str
    table_name: Optional[str] = None
    session_id: Optional[int] = None
    user_id: Optional[int] = None

class ColumnDescription(BaseModel):
    column_name: str
    description: str = ""

class TableCreationRequest(BaseModel):
    table_name: str
    column_descriptions: List[ColumnDescription]
    prompt: Optional[str] = ""

class SelectTableRequest(BaseModel):
    table_name: str

class SessionCreateRequest(BaseModel):
    table_name: str
    user_id: Optional[int] = None
    title: Optional[str] = None

class SessionSelectRequest(BaseModel):
    session_id: int

class UserResponse(BaseModel):
    id: int
    display_name: str
    email: str
    avatar_initials: str