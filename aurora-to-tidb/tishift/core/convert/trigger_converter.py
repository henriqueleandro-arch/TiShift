"""Trigger converter (skeleton middleware templates)."""

from __future__ import annotations

from dataclasses import dataclass

from tishift.models import TriggerInfo


@dataclass
class TriggerConversion:
    filename: str
    code: str


def convert_triggers(triggers: list[TriggerInfo]) -> list[TriggerConversion]:
    outputs: list[TriggerConversion] = []
    for trigger in triggers:
        name = trigger.trigger_name
        code = (
            f"# Auto-generated middleware for trigger {trigger.trigger_schema}.{name}\n"
            f"# Event: {trigger.action_timing} {trigger.event_manipulation} ON {trigger.event_object_table}\n\n"
            "def handle(event):\n"
            "    # TODO: translate trigger logic into application code\n"
            "    pass\n"
        )
        outputs.append(TriggerConversion(filename=f"{name}.py", code=code))
    return outputs
