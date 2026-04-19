from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class RawItem(BaseModel):
    source_id: str
    url_original: str
    external_id: str | None = None
    raw_payload: str
    raw_hash: str
    stored_at: datetime


class NormalizedItem(BaseModel):
    source_id: str
    source_domain: str
    url_original: str
    url_canonical: str
    title: str
    summary: str | None = None
    content_text: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime
    content_hash: str
    rule_score: int = 0
    status: Literal["new", "candidate", "reviewed", "selected", "rejected"] = "new"


class ItemReview(BaseModel):
    item_id: int
    model_name: str
    decision: Literal["relevant", "borderline", "irrelevant"]
    topic_type: str | None = None
    relevance_score: float
    beginnerluft_fit_score: float
    actionability_score: float
    business_impact_score: float
    urgency_score: float
    confidence: float
    summary: str
    why_relevant: list[str]
    recommended_actions: list[str]


class DigestItem(BaseModel):
    item_id: int
    rank: int
    final_score: float
    title: str
    source_id: str
    url_canonical: str
    summary: str
    why_relevant: str
    recommended_action: str
