from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LoopStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"


class Source(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    path: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class Loop(BaseModel):
    """One open commitment: who owes what, optionally by when."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    text: str = Field(..., description="Clear statement of the commitment")
    owner: Optional[str] = Field(None, description="Person who owes the action")
    due_date: Optional[date] = None
    due_text: Optional[str] = Field(None, description="Original deadline phrase")
    status: LoopStatus = LoopStatus.OPEN
    evidence: Optional[str] = Field(None, description="Snippet from the source")
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractResult(BaseModel):
    loops: list[Loop] = Field(default_factory=list)
