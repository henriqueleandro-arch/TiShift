"""Stored procedure converter (skeleton templates + optional AI)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from tishift.config import AIConfig
from tishift.core.scan.analyzers.ai_analyzer import analyze_stored_procedures
from tishift.models import RoutineInfo, SPAIAnalysis

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class SPConversionResult:
    language: str
    filename: str
    code: str
    summary: str | None = None


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)
    template = env.get_template(template_name)
    return template.render(**context)


def _escape_jinja(text: str) -> str:
    """Escape Jinja2 syntax in user-provided text to prevent template injection."""
    return text.replace("{%", "{%%").replace("%}", "%%}").replace("{{", "{ {").replace("}}", "} }")


def _base_context(routine: RoutineInfo) -> dict[str, Any]:
    definition = routine.routine_definition or routine.routine_body or ""
    return {
        "schema": routine.routine_schema,
        "name": routine.routine_name,
        "routine_type": routine.routine_type,
        "definition": _escape_jinja(definition),
    }


def _template_for_language(language: str) -> str:
    mapping = {
        "python": "sp_python.py.j2",
        "go": "sp_go.go.j2",
        "java": "sp_java.java.j2",
        "javascript": "sp_javascript.js.j2",
    }
    return mapping.get(language, "sp_python.py.j2")


def convert_stored_procedures(
    routines: list[RoutineInfo],
    *,
    language: str = "python",
    use_ai: bool = False,
    ai_config: AIConfig | None = None,
) -> tuple[list[SPConversionResult], list[SPAIAnalysis]]:
    """Convert stored procedures/functions into application code.

    Returns conversion results and (optional) AI analysis used.
    """
    procedures = [r for r in routines if r.routine_type in ("PROCEDURE", "FUNCTION")]
    ai_analysis: list[SPAIAnalysis] = []

    if use_ai:
        if ai_config is None:
            ai_config = AIConfig()
        ai_analysis = analyze_stored_procedures(procedures, ai_config)

    ai_index = {f"{a.routine_schema}.{a.routine_name}": a for a in ai_analysis}
    results: list[SPConversionResult] = []

    for routine in procedures:
        key = f"{routine.routine_schema}.{routine.routine_name}"
        analysis = ai_index.get(key)
        context = _base_context(routine)

        if analysis and analysis.equivalent_code:
            code = analysis.equivalent_code.get(language) or analysis.equivalent_code.get("python") or ""
            summary = analysis.summary
        else:
            template_name = _template_for_language(language)
            code = _render_template(template_name, context)
            summary = None

        filename = f"{routine.routine_name}.{_ext(language)}"
        results.append(
            SPConversionResult(language=language, filename=filename, code=code, summary=summary)
        )

    return results, ai_analysis


def _ext(language: str) -> str:
    return {
        "python": "py",
        "go": "go",
        "java": "java",
        "javascript": "js",
    }.get(language, "py")
