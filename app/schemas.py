from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DatasetCreate(BaseModel):
    name: str
    path: str
    schema: Optional[Dict[str, Any]]
    rows: Optional[int]


class InsightOut(BaseModel):
    summary: str
    kpis: List[Dict[str, Any]]
    risks: List[str]
    recommendations: List[str]
    confidence: float
