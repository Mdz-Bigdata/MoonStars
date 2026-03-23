from pydantic import BaseModel
from typing import List, Dict, Optional

class AIChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    provider: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class AIChatResponse(BaseModel):
    answer: str
    model: str

class AISummaryRequest(BaseModel):
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    provider: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class AISummaryResponse(BaseModel):
    summary: str
