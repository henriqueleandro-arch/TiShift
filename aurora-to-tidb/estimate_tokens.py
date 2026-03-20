#!/usr/bin/env python3
"""Estimate total token usage across all Claude Code sessions, grouped by project.

Includes subagent token usage (Task tool spawns) for each session.
"""

import json
from collections import defaultdict
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects" / "-Users-henriqueleandro"

# Pricing per million tokens (Claude Opus 4, as of Feb 2026)
PRICE_INPUT = 15.00
PRICE_OUTPUT = 75.00
PRICE_CACHE_WRITE = 3.75
PRICE_CACHE_READ = 1.50

# Keywords to classify sessions — checked in priority order against first 10 user messages.
# "sqlserver" is checked first so "tishift-sqlserver" doesn't match "aurora-to-tidb" keywords.
PROJECT_RULES = [
    ("sqlserver", ["sqlserver", "sql server", "sql-server", "tishift-sqlserver", "sqlserver-to-tidb"]),
    ("aurora-to-tidb", ["aurora", "tidb", "tishift", "SKILL.md", "run_logger", "JSONL Run Logger",
                         "aurora-to-tidb", "scan_schema", "mcp"]),
]


def classify_session(path: Path) -> str:
    """Classify a session into a project by scanning user messages for keywords."""
    # Collect text from first N user messages
    texts: list[str] = []
    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "user":
                continue
            content = obj.get("message", {})
            if isinstance(content, dict):
                content = str(content.get("content", ""))
            texts.append(str(content).lower())
            if len(texts) >= 10:
                break

    combined = " ".join(texts)

    # Check rules in priority order
    for project, keywords in PROJECT_RULES:
        for kw in keywords:
            if kw.lower() in combined:
                return project

    return "other"


def sum_tokens_from_jsonl(path: Path) -> dict:
    """Sum token usage from a single JSONL file."""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "api_calls": 0,
    }
    models = set()

    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "assistant":
                continue

            msg = obj.get("message", {})
            if not isinstance(msg, dict):
                continue

            usage = msg.get("usage", {})
            if not usage:
                continue

            totals["input_tokens"] += usage.get("input_tokens", 0)
            totals["output_tokens"] += usage.get("output_tokens", 0)
            totals["cache_creation_input_tokens"] += usage.get("cache_creation_input_tokens", 0)
            totals["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)
            totals["api_calls"] += 1

            model = msg.get("model", "unknown")
            models.add(model)

    totals["models"] = sorted(models)
    return totals


def parse_session(session_jsonl: Path) -> dict:
    """Parse a session JSONL and all its subagent files, returning combined totals."""
    # Main session tokens
    totals = sum_tokens_from_jsonl(session_jsonl)

    # Subagent tokens
    subagent_dir = session_jsonl.parent / session_jsonl.stem / "subagents"
    subagent_count = 0
    if subagent_dir.is_dir():
        for sub_jsonl in subagent_dir.glob("*.jsonl"):
            sub_totals = sum_tokens_from_jsonl(sub_jsonl)
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "api_calls"):
                totals[k] += sub_totals[k]
            totals["models"] = sorted(set(totals["models"]) | set(sub_totals.get("models", [])))
            subagent_count += 1

    totals["subagent_count"] = subagent_count
    return totals


def estimate_cost(totals: dict) -> float:
    cost = 0.0
    cost += (totals["input_tokens"] / 1_000_000) * PRICE_INPUT
    cost += (totals["output_tokens"] / 1_000_000) * PRICE_OUTPUT
    cost += (totals["cache_creation_input_tokens"] / 1_000_000) * PRICE_CACHE_WRITE
    cost += (totals["cache_read_input_tokens"] / 1_000_000) * PRICE_CACHE_READ
    return cost


def new_totals() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "api_calls": 0,
    }


def add_totals(dst: dict, src: dict):
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "api_calls"):
        dst[k] += src[k]


def total_tokens(t: dict) -> int:
    return t["input_tokens"] + t["output_tokens"] + t["cache_creation_input_tokens"] + t["cache_read_input_tokens"]


def fmt(n: int) -> str:
    return f"{n:,}"


def print_header():
    print(f"  {'Session':<40} {'Calls':>7} {'Input':>12} {'Output':>12} {'Cache Wr':>12} {'Cache Rd':>14} {'Cost':>9}")
    print(f"  {'-'*108}")


def print_row(name: str, totals: dict, suffix: str = "", indent: str = "  "):
    cost = estimate_cost(totals)
    line = (
        f"{indent}{name:<40} {totals['api_calls']:>7} "
        f"{fmt(totals['input_tokens']):>12} {fmt(totals['output_tokens']):>12} "
        f"{fmt(totals['cache_creation_input_tokens']):>12} {fmt(totals['cache_read_input_tokens']):>14} "
        f"${cost:>7.2f}"
    )
    if suffix:
        line += f"  {suffix}"
    print(line)


def main():
    session_files = sorted(PROJECTS_DIR.glob("*.jsonl"))

    if not session_files:
        print("No session files found.")
        return

    # Group sessions by project
    projects: dict[str, list[tuple[Path, dict]]] = defaultdict(list)

    for path in session_files:
        totals = parse_session(path)
        if totals["api_calls"] == 0:
            continue
        project = classify_session(path)
        projects[project].append((path, totals))

    grand = new_totals()
    all_models = set()
    grand_sessions = 0
    grand_subagents = 0

    # Print each project
    project_order = ["aurora-to-tidb", "sqlserver", "other"]
    project_labels = {
        "aurora-to-tidb": "Aurora MySQL -> TiDB",
        "sqlserver": "SQL Server -> TiDB",
        "other": "Other / Unclassified",
    }

    for project_key in project_order:
        sessions = projects.get(project_key)
        if not sessions:
            continue

        project_totals = new_totals()
        project_subagents = 0
        label = project_labels.get(project_key, project_key)

        print(f"\n{'='*112}")
        print(f"  {label}")
        print(f"{'='*112}")
        print_header()

        for path, totals in sessions:
            name = path.stem[:36] + "..."
            sub_count = totals.get("subagent_count", 0)
            suffix = f"(+{sub_count} subagents)" if sub_count else ""
            print_row(name, totals, suffix=suffix)
            add_totals(project_totals, totals)
            all_models.update(totals.get("models", []))
            project_subagents += sub_count

        print(f"  {'-'*108}")
        print_row(f"Subtotal — {label}", project_totals)
        print(f"  Total tokens: {fmt(total_tokens(project_totals))}    Sessions: {len(sessions)}    Subagents: {project_subagents}")

        add_totals(grand, project_totals)
        grand_sessions += len(sessions)
        grand_subagents += project_subagents

    # Grand total
    grand_cost = estimate_cost(grand)

    print(f"\n{'='*112}")
    print(f"  GRAND TOTAL (all projects)")
    print(f"{'='*112}")
    print(f"  {'':40} {'Calls':>7} {'Input':>12} {'Output':>12} {'Cache Wr':>12} {'Cache Rd':>14} {'Cost':>9}")
    print(f"  {'-'*108}")
    print_row("ALL PROJECTS", grand)
    print()
    print(f"  Total tokens:  {fmt(total_tokens(grand))}")
    print(f"  Sessions:      {grand_sessions}  (+{grand_subagents} subagents)")
    print(f"  Models used:   {', '.join(sorted(all_models))}")
    print(f"  Est. cost:     ${grand_cost:.2f}")
    print()
    print(f"  Note: Cost estimated at standard Opus 4 API pricing.")
    print(f"        Actual cost depends on your plan (Pro, Teams, API).")


if __name__ == "__main__":
    main()
