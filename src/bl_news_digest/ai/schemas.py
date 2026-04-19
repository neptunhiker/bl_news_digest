"""Pydantic schema for AI review output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ItemReview(BaseModel):
    decision: Literal["include", "exclude"]
    topic_type: str = Field(
        description="Short label for the topic category, e.g. 'AVGS regulation', 'AZAV compliance'."
    )
    relevance_score: int = Field(ge=1, le=10, description="Overall relevance to BeginnerLuft (1–10).")
    beginnerluft_fit_score: int = Field(ge=1, le=10, description="How well the item fits BeginnerLuft's service profile (1–10).")
    actionability_score: int = Field(ge=1, le=10, description="How actionable this information is for BeginnerLuft staff (1–10).")
    business_impact_score: int = Field(ge=1, le=10, description="Potential business impact on BeginnerLuft (1–10).")
    urgency_score: int = Field(ge=1, le=10, description="How urgently BeginnerLuft should act on this (1–10).")
    confidence: int = Field(ge=1, le=10, description="Model confidence in this review (1–10).")
    summary: str = Field(description="One-sentence plain-language summary of the item.")
    why_relevant: str = Field(description="One or two sentences explaining why this is relevant to BeginnerLuft.")
    recommended_actions: list[str] = Field(
        description="List of concrete next steps BeginnerLuft could take in response to this item."
    )

