"""AI analyzer placeholders for SP/CLR analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIAnalysis:
    object_name: str
    summary: str
    difficulty: str
    automation_pct: int


def analyze_procedure_with_ai(object_name: str, definition: str) -> AIAnalysis:
    """Return placeholder AI analysis; external API integration is future work."""
    _ = definition
    return AIAnalysis(
        object_name=object_name,
        summary="AI analysis placeholder",
        difficulty="moderate",
        automation_pct=70,
    )


def analyze_clr_with_ai(object_name: str, metadata: dict[str, object]) -> AIAnalysis:
    """Return placeholder CLR intent analysis."""
    _ = metadata
    return AIAnalysis(
        object_name=object_name,
        summary="CLR replacement placeholder",
        difficulty="complex",
        automation_pct=30,
    )
