"""Event converter (cron skeletons)."""

from __future__ import annotations

from dataclasses import dataclass

from tishift.models import EventInfo


@dataclass
class EventConversion:
    filename: str
    code: str


def convert_events(events: list[EventInfo]) -> list[EventConversion]:
    outputs: list[EventConversion] = []
    for event in events:
        name = event.event_name
        cron = "# TODO: translate schedule from EVENT definition"
        body = event.event_definition or ""
        code = (
            f"# {event.event_schema}.{name}\n"
            f"{cron}\n\n"
            f"# Original definition:\n{body}\n"
        )
        outputs.append(EventConversion(filename=f"{name}.cron", code=code))
    return outputs
