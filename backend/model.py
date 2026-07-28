from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    question: str

class UploadResponse(BaseModel):
    success: bool
    message: str
    columns: list
    preview: list
    row_count: int
    table_name: str

class ChatResponse(BaseModel):
    answer: str